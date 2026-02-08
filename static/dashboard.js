let soilChart = null, envChart = null;

/**
 * Plugin: draws vertical event lines.
 * IMPORTANT: markers are stored as {idx, text} (NOT pixels), so they remain correct
 * across resize, refresh, dropdown changes, and re-layout.
 */
const eventLinesPlugin = {
  id: "eventLines",
  afterDraw(chart) {
    const markers = chart?.config?.data?.eventMarkers || [];
    if (!markers.length) return;

    const { ctx, chartArea, scales } = chart;
    const xScale = scales.x;
    if (!xScale) return;

    ctx.save();
    ctx.globalAlpha = 0.75;
    ctx.lineWidth = 2.5;
    ctx.setLineDash([4, 5]);
    ctx.font = "11px system-ui, Arial";

    for (const m of markers) {
      if (m.idx === undefined || m.idx === null) continue;

      const x = xScale.getPixelForValue(m.idx);
      if (x < chartArea.left || x > chartArea.right) continue;

      ctx.beginPath();
      ctx.moveTo(x, chartArea.top);
      ctx.lineTo(x, chartArea.bottom);
      ctx.stroke();

      if (m.text) {
        ctx.fillText(m.text, x + 6, chartArea.top + 14);
      }
    }

    ctx.setLineDash([]);
    ctx.globalAlpha = 1;
    ctx.restore();
  }
};

Chart.register(eventLinesPlugin);

function getSelectedHours() {
  return parseInt(document.getElementById("hoursSelect").value, 10);
}

function fmt(ts, withDate = false) {
  const d = new Date(ts * 1000);
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  if (!withDate) return `${hh}:${mm}`;
  const dd = String(d.getDate()).padStart(2, "0");
  const mo = String(d.getMonth() + 1).padStart(2, "0");
  return `${dd}/${mo} ${hh}:${mm}`;
}

function downsample(timestamps, seriesList, maxPoints = 600) {
  const n = timestamps.length;
  if (n <= maxPoints) return { timestamps, seriesList };

  const step = Math.ceil(n / maxPoints);
  const ts2 = [];
  const series2 = seriesList.map(() => []);

  for (let i = 0; i < n; i += step) {
    ts2.push(timestamps[i]);
    for (let s = 0; s < seriesList.length; s++) {
      series2[s].push(seriesList[s][i]);
    }
  }
  return { timestamps: ts2, seriesList: series2 };
}

function nearestIndex(timestamps, tsEvent) {
  // timestamps assumed sorted ascending
  let lo = 0, hi = timestamps.length - 1;
  if (hi < 0) return 0;
  if (tsEvent <= timestamps[0]) return 0;
  if (tsEvent >= timestamps[hi]) return hi;

  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (timestamps[mid] < tsEvent) lo = mid + 1;
    else hi = mid - 1;
  }
  return Math.min(lo, timestamps.length - 1);
}

function autoRange(values, pad = 1.0, hardMin = null, hardMax = null) {
  const clean = (values || []).filter(v => v !== null && v !== undefined && !Number.isNaN(v));
  if (clean.length < 2) return { min: hardMin ?? 0, max: hardMax ?? 1 };

  let vmin = Math.min(...clean);
  let vmax = Math.max(...clean);
  if (vmax === vmin) { vmin -= 1; vmax += 1; }

  vmin -= pad;
  vmax += pad;

  if (hardMin !== null) vmin = Math.max(hardMin, vmin);
  if (hardMax !== null) vmax = Math.min(hardMax, vmax);

  return { min: vmin, max: vmax };
}

function buildView(data, hours) {
  // 1) downsample everything consistently
  const originalTs = data.timestamps || [];
  const { timestamps: ts, seriesList } = downsample(
    originalTs,
    [data.soil1, data.soil2, data.soil3, data.temp, data.hum],
    600
  );

  const view = {
    hours,
    ts,
    labels: ts.map(t => fmt(t, hours >= 24)),
    soil: {
      s1: seriesList[0],
      s2: seriesList[1],
      s3: seriesList[2],
    },
    env: {
      temp: seriesList[3],
      hum: seriesList[4],
    },
    events: [] // {idx, text}
  };

  // 2) compute ranges (smart zoom)
  const soilAll = [...view.soil.s1, ...view.soil.s2, ...view.soil.s3];
  view.ranges = {
    soil: autoRange(soilAll, 0.8, 0, 100),
    temp: autoRange(view.env.temp, 0.5, -10, 60),
    hum:  autoRange(view.env.hum,  2.0, 0, 100),
  };

  // 3) build markers as idxs on *downsampled timestamps*
  const watering = data.watering || [];
  for (const w of watering) {
    const idx = nearestIndex(view.ts, w.ts);
    const pot = w.pot ?? "";
    view.events.push({ idx, text: `P${pot}` }); // e.g. P2
  }

  const manual = data.manual || [];
  for (const e of manual) {
    const idx = nearestIndex(view.ts, e.ts);
    view.events.push({ idx, text: "Μ" });
  }

  return view;
}

function ensureSoilChart(view) {
  const soilCtx = document.getElementById("soilChart").getContext("2d");

  const soilDatasets = [
    { label:"Γλάστρα 1 (%)", data: view.soil.s1, pointRadius:0, pointHitRadius:8, borderWidth:2, tension:0.25 },
    { label:"Γλάστρα 2 (%)", data: view.soil.s2, pointRadius:0, pointHitRadius:8, borderWidth:2, tension:0.25 },
    { label:"Γλάστρα 3 (%)", data: view.soil.s3, pointRadius:0, pointHitRadius:8, borderWidth:2, tension:0.25 },
  ];

  if (!soilChart) {
    soilChart = new Chart(soilCtx, {
      type: "line",
      data: { labels: view.labels, datasets: soilDatasets, eventMarkers: [] },
      options: {
        animation: false,
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        scales: {
          x: { ticks: { autoSkip: true, maxTicksLimit: 12 } },
          y: { min: view.ranges.soil.min, max: view.ranges.soil.max }
        }
      },
    });
  } else {
    soilChart.data.labels = view.labels;
    soilChart.data.datasets.forEach((ds, i) => {
      ds.data = soilDatasets[i].data;
    });
    soilChart.options.scales.y.min = view.ranges.soil.min;
    soilChart.options.scales.y.max = view.ranges.soil.max;
  }

  // store markers as idx (NOT pixels)
  soilChart.config.data.eventMarkers = view.events;

  // single update call
  soilChart.update("none");
}

function ensureEnvChart(view) {
  const envCtx = document.getElementById("envChart").getContext("2d");

  if (!envChart) {
    envChart = new Chart(envCtx, {
      type: "line",
      data: {
        labels: view.labels,
        datasets: [
          { label:"Θερμοκρασία (°C)", data: view.env.temp, yAxisID:"y",  pointRadius:0, pointHitRadius:8, borderWidth:2, tension:0.25 },
          { label:"Υγρασία (%)",      data: view.env.hum,  yAxisID:"y1", pointRadius:0, pointHitRadius:8, borderWidth:2, tension:0.25 },
        ]
      },
      options: {
        animation:false,
        responsive:true,
        maintainAspectRatio:false,
        interaction:{ mode:"index", intersect:false },
        scales:{
          x:  { ticks: { autoSkip: true, maxTicksLimit: 12 } },
          y:  { type:"linear", position:"left",  min: view.ranges.temp.min, max: view.ranges.temp.max },
          y1: { type:"linear", position:"right", min: view.ranges.hum.min,  max: view.ranges.hum.max, grid:{ drawOnChartArea:false } }
        }
      }
    });
  } else {
    envChart.data.labels = view.labels;
    envChart.data.datasets[0].data = view.env.temp;
    envChart.data.datasets[1].data = view.env.hum;

    envChart.options.scales.y.min  = view.ranges.temp.min;
    envChart.options.scales.y.max  = view.ranges.temp.max;
    envChart.options.scales.y1.min = view.ranges.hum.min;
    envChart.options.scales.y1.max = view.ranges.hum.max;

    envChart.update("none");
  }
}

async function refresh() {
  const hours = getSelectedHours();
  const r = await fetch(`/api/history?hours=${hours}`);
  const data = await r.json();

  const view = buildView(data, hours);
  ensureSoilChart(view);
  ensureEnvChart(view);
}

document.addEventListener("DOMContentLoaded", () => {
  const sel = document.getElementById("hoursSelect");
  const btn = document.getElementById("refreshBtn");

  sel.addEventListener("change", refresh);
  btn.addEventListener("click", refresh);

  refresh();
  setInterval(refresh, 5000); //5s για demo
});
