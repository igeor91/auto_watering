#!/usr/bin/env python3
import time
import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any

from gpiozero import OutputDevice

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "db" / "data.db"

# GPIO19 relay, confirmed active_high=True on your setup
RELAY_PIN = 19
relay = OutputDevice(RELAY_PIN, active_high=True, initial_value=False)  # OFF

# Only pot 2 is watered by pump
PUMP_POT = 2

# Pump calibration
ML_PER_SEC_DEFAULT = 20.0

# Watering plan (same as your controlled_watering.py)
PULSES_DEFAULT = [1.0, 1.0, 1.5, 2.0, 2.0]  # total 7.5s => ~150ml
PAUSES_DEFAULT = [15, 15, 25, 25]

# Defaults (used if settings_history not set)
START_PCT_DEFAULT = 60.0
STOP_PCT_DEFAULT = 75.0
COOLDOWN_SEC_DEFAULT = 3 * 3600  # 3 hours

POLL_SEC = 20  # check DB every 90s


def _db_conn():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def log_system(level: str, code: str, message: str):
    with _db_conn() as con:
        con.execute(
            "INSERT INTO system_events(ts, level, code, message) VALUES (?, ?, ?, ?)",
            (int(time.time()), level, code, message),
        )
        con.commit()


def get_latest_setting(key: str) -> Optional[str]:
    with _db_conn() as con:
        row = con.execute(
            "SELECT value FROM settings_history WHERE key=? ORDER BY ts DESC LIMIT 1",
            (key,),
        ).fetchone()
    return row["value"] if row else None


def get_float_setting(key: str, default: float) -> float:
    v = get_latest_setting(key)
    if v is None:
        return default
    try:
        return float(v)
    except Exception:
        return default


def get_int_setting(key: str, default: int) -> int:
    v = get_latest_setting(key)
    if v is None:
        return default
    try:
        return int(float(v))
    except Exception:
        return default


def get_latest_pct() -> Optional[Dict[int, Optional[float]]]:
    with _db_conn() as con:
        row = con.execute(
            "SELECT ts, soil1_pct, soil2_pct, soil3_pct FROM sensor_readings ORDER BY ts DESC LIMIT 1"
        ).fetchone()
    if not row:
        return None
    return {
        1: row["soil1_pct"],
        2: row["soil2_pct"],
        3: row["soil3_pct"],
        -1: row["ts"],  # stash ts
    }


def insert_watering_event(
    ts_start: int,
    ts_end: int,
    duration_s: float,
    estimated_ml: float,
    trigger_value_pct: Optional[float],
    threshold_pct: float,
    result: str = "ok",
    error_code: Optional[str] = None,
    error_msg: Optional[str] = None,
):
    with _db_conn() as con:
        con.execute(
            """
            INSERT INTO watering_events
            (ts_start, ts_end, duration_s, estimated_ml,
             trigger_pot, trigger_value_pct, threshold_pct,
             result, error_code, error_msg)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ts_start, ts_end, int(round(duration_s)), float(estimated_ml),
                PUMP_POT, trigger_value_pct, threshold_pct,
                result, error_code, error_msg
            ),
        )
        con.commit()


def pump_cycle(pulses, pauses, ml_per_sec, trigger_pct, start_threshold):
    total_on = float(sum(pulses))
    est_ml = total_on * float(ml_per_sec)

    ts_start = int(time.time())
    log_system(
        "info",
        "pump_cycle_start",
        f"Pump cycle start pot={PUMP_POT}, pulses={pulses}s, pauses={pauses}s, "
        f"trigger_pct={trigger_pct}, start_th={start_threshold}, est_ml={est_ml:.1f}",
    )

    try:
        for i, on_s in enumerate(pulses, start=1):
            log_system("info", "pump_pulse_on", f"Pulse {i}/{len(pulses)} ON {on_s:.2f}s (~{on_s*ml_per_sec:.1f}ml)")
            relay.on()
            time.sleep(float(on_s))
            relay.off()

            if i <= len(pauses):
                time.sleep(float(pauses[i - 1]))

        ts_end = int(time.time())
        insert_watering_event(
            ts_start=ts_start,
            ts_end=ts_end,
            duration_s=total_on,
            estimated_ml=est_ml,
            trigger_value_pct=trigger_pct,
            threshold_pct=start_threshold,
            result="ok",
        )
        log_system("info", "pump_cycle_end", f"Pump cycle end pot={PUMP_POT}, total_on={total_on:.2f}s, est_ml={est_ml:.1f}")

    except Exception as e:
        relay.off()
        ts_end = int(time.time())
        insert_watering_event(
            ts_start=ts_start,
            ts_end=ts_end,
            duration_s=total_on,
            estimated_ml=est_ml,
            trigger_value_pct=trigger_pct,
            threshold_pct=start_threshold,
            result="error",
            error_code="exception",
            error_msg=str(e),
        )
        log_system("error", "pump_cycle_error", f"Pump cycle error: {e}")
        raise
    finally:
        relay.off()


def main():
    relay.off()

    log_system(
        "info",
        "controller_start",
        f"Controller started. Pump pot={PUMP_POT}. Settings keys: soil2_start_pct, soil2_stop_pct, pump_cooldown_sec, ml_per_sec",

    )

    last_cycle_end = 0.0

    while True:
        # Load settings live (no restart needed)
        start_pct = get_float_setting("soil2_start_pct", START_PCT_DEFAULT)
        stop_pct = get_float_setting("soil2_stop_pct", STOP_PCT_DEFAULT)
        cooldown_sec = get_int_setting("pump_cooldown_sec", COOLDOWN_SEC_DEFAULT)
        ml_per_sec = get_float_setting("ml_per_sec", ML_PER_SEC_DEFAULT)

        # (optional) pulses/pauses could also be loaded from DB later; keep stable for now
        pulses = PULSES_DEFAULT
        pauses = PAUSES_DEFAULT

        latest = get_latest_pct()
        if not latest:
            time.sleep(POLL_SEC)
            continue

        v = latest.get(PUMP_POT)
        if v is None:
            time.sleep(POLL_SEC)
            continue

        now = time.time()

        # Cooldown safety
        if last_cycle_end and (now - last_cycle_end) < cooldown_sec:
            time.sleep(POLL_SEC)
            continue

        # Skip if already wet enough
        if v >= stop_pct:
            time.sleep(POLL_SEC)
            continue

        # Trigger condition
        if v <= start_pct:
            log_system("info", "pump_trigger", f"Trigger: soil{PUMP_POT}_pct={v:.2f} <= {start_pct} (stop={stop_pct}, cooldown={cooldown_sec}s)")

            pump_cycle(pulses, pauses, ml_per_sec, trigger_pct=float(v), start_threshold=float(start_pct))
            last_cycle_end = time.time()

        time.sleep(POLL_SEC)


if __name__ == "__main__":
    main()
