import time
from db import init_db, get_conn

init_db()
ts = int(time.time())

vals = {
  "soil1_dry": "25",  "soil1_wet": "742",
  "soil2_dry": "25",  "soil2_wet": "742",
  "soil3_dry": "25",  "soil3_wet": "742",
}

with get_conn() as con:
  for k, v in vals.items():
    con.execute(
      "INSERT INTO settings_history (ts, key, value, source, comment) VALUES (?, ?, ?, 'manual', 'calibration')",
      (ts, k, v),
    )
  con.commit()

print("OK saved calibration")
