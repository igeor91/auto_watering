from flask import Flask, jsonify, render_template, request
from db import fetch_history, fetch_watering_events, fetch_system_events

app = Flask(__name__)

@app.route("/")
def dashboard():
    return render_template("dashboard.html")

@app.route("/api/history")
def api_history():
    hours = request.args.get("hours", default=24, type=int)

    rows = fetch_history(hours=hours)
    watering = fetch_watering_events(hours=hours)
    manual = fetch_system_events(hours=hours, code="manual_water_start")

    return jsonify({
        "timestamps": [r["ts"] for r in rows],
        "soil1_raw":  [r["soil1_raw"] for r in rows],
        "soil2_raw":  [r["soil2_raw"] for r in rows],
        "soil3_raw":  [r["soil3_raw"] for r in rows],
        "soil1":      [r["soil1_pct"] for r in rows],
        "soil2":      [r["soil2_pct"] for r in rows],
        "soil3":      [r["soil3_pct"] for r in rows],
        "temp":       [r["temp_c"] for r in rows],
        "hum":        [r["hum_pct"] for r in rows],

        # clean watering events for markers
        "watering": [{
            "ts": w["ts_start"],
            "pot": w["trigger_pot"],
            "ml": w["estimated_ml"],
            "result": w["result"],
        } for w in watering],

        # manual markers (until we also write them as watering_events)
        "manual": [{
            "ts": e["ts"],
            "code": e["code"],
        } for e in manual],
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
