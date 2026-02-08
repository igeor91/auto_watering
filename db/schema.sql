PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS sensor_readings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts INTEGER NOT NULL,

  soil1_raw INTEGER,
  soil2_raw INTEGER,
  soil3_raw INTEGER,

  soil1_pct REAL,
  soil2_pct REAL,
  soil3_pct REAL,

  temp_c REAL,
  hum_pct REAL,

  vin_v REAL,
  flags INTEGER DEFAULT 0,
  notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_sensor_readings_ts
ON sensor_readings(ts);

CREATE TABLE IF NOT EXISTS watering_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts_start INTEGER NOT NULL,
  ts_end INTEGER,
  duration_s INTEGER NOT NULL,

  estimated_ml REAL,

  trigger_pot INTEGER,
  trigger_value_raw INTEGER,
  trigger_value_pct REAL,
  threshold_pct REAL,

  result TEXT NOT NULL DEFAULT 'ok',
  error_code TEXT,
  error_msg TEXT
);

CREATE INDEX IF NOT EXISTS idx_watering_events_ts_start
ON watering_events(ts_start);

CREATE TABLE IF NOT EXISTS settings_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts INTEGER NOT NULL,
  key TEXT NOT NULL,
  value TEXT NOT NULL,
  source TEXT DEFAULT 'manual',
  comment TEXT
);

CREATE INDEX IF NOT EXISTS idx_settings_history_ts
ON settings_history(key, ts DESC);

CREATE TABLE IF NOT EXISTS system_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts INTEGER NOT NULL,
  level TEXT NOT NULL,
  code TEXT,
  message TEXT
);

CREATE INDEX IF NOT EXISTS idx_system_events_ts
ON system_events(ts);
