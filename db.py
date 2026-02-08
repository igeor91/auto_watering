import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

DB_PATH = BASE_DIR / "db" / "data.db"
SCHEMA_PATH = BASE_DIR / "db" / "schema.sql"


def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    """Δημιουργεί πίνακες/indices αν δεν υπάρχουν, εκτελώντας το db/schema.sql."""
    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(f"Missing schema file: {SCHEMA_PATH}")
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")

    with get_conn() as con:
        con.executescript(schema_sql)
        con.commit()


def clear_sensor_readings():
    """Εκκαθάριση μετρήσεων (κρατάει τα υπόλοιπα tables)."""
    with get_conn() as con:
        con.execute("DELETE FROM sensor_readings;")
        con.execute("VACUUM;")
        con.commit()


def insert_sensor_reading(
    ts: int,
    soil1_raw: int | None,
    soil2_raw: int | None,
    soil3_raw: int | None,
    soil1_pct: float | None,
    soil2_pct: float | None,
    soil3_pct: float | None,
    temp_c: float | None,
    hum_pct: float | None,
    vin_v: float | None = None,
    flags: int = 0,
    notes: str | None = None,
):
    with get_conn() as con:
        con.execute(
            """
            INSERT INTO sensor_readings
            (ts, soil1_raw, soil2_raw, soil3_raw,
             soil1_pct, soil2_pct, soil3_pct,
             temp_c, hum_pct,
             vin_v, flags, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ts, soil1_raw, soil2_raw, soil3_raw,
                soil1_pct, soil2_pct, soil3_pct,
                temp_c, hum_pct,
                vin_v, flags, notes
            )
        )
        con.commit()

def insert_sensor_readings_batch(con, rows: list[tuple]):
    """
    Batch insert για sensor_readings.
    Συμβατό με collector.py: insert_sensor_readings_batch(con, buffer)
    όπου buffer είναι list[tuple] με σειρά:
      (ts,
       soil1_raw, soil2_raw, soil3_raw,
       soil1_pct, soil2_pct, soil3_pct,
       temp_c, hum_pct,
       vin_v, flags, notes)
    """
    if not rows:
        return

    con.executemany(
        """
        INSERT INTO sensor_readings
        (ts, soil1_raw, soil2_raw, soil3_raw,
         soil1_pct, soil2_pct, soil3_pct,
         temp_c, hum_pct,
         vin_v, flags, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows
    )




def fetch_history(hours: int = 24, limit: int = 5000):
    """
    Φέρνει μετρήσεις από τις τελευταίες `hours` ώρες.
    limit: safety για να μην τραβάμε άπειρα rows.
    """
    hours = max(1, min(hours, 7 * 24))  # clamp 1h..7days
    limit = max(100, min(limit, 20000))

    with get_conn() as con:
        rows = con.execute(
            """
            SELECT ts, soil1_raw, soil2_raw, soil3_raw,
                   soil1_pct, soil2_pct, soil3_pct,
                   temp_c, hum_pct
            FROM sensor_readings
            WHERE ts >= (strftime('%s','now') - ?)
            ORDER BY ts ASC
            LIMIT ?
            """,
            (hours * 3600, limit)
        ).fetchall()

    return rows


def fetch_watering_events(hours: int = 24, limit: int = 2000):
    """Φέρνει watering cycles (ποτίσματα) από watering_events."""
    hours = max(1, min(hours, 7 * 24))
    limit = max(50, min(limit, 20000))

    with get_conn() as con:
        rows = con.execute(
            """
            SELECT ts_start, ts_end, duration_s,
                   estimated_ml, trigger_pot,
                   trigger_value_pct, threshold_pct,
                   result
            FROM watering_events
            WHERE ts_start >= (strftime('%s','now') - ?)
            ORDER BY ts_start ASC
            LIMIT ?
            """,
            (hours * 3600, limit)
        ).fetchall()

    return rows


def fetch_system_events(hours: int = 24, limit: int = 2000, code: str | None = None):
    """Φέρνει system events (useful for debug / manual watering markers)."""
    hours = max(1, min(hours, 7 * 24))
    limit = max(50, min(limit, 20000))

    q = """
        SELECT ts, level, code, message
        FROM system_events
        WHERE ts >= (strftime('%s','now') - ?)
    """
    params = [hours * 3600]

    if code is not None:
        q += " AND code = ?"
        params.append(code)

    q += " ORDER BY ts ASC LIMIT ?"
    params.append(limit)

    with get_conn() as con:
        rows = con.execute(q, tuple(params)).fetchall()

    return rows
