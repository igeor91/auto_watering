#!/usr/bin/env python3
import time
import sqlite3
from pathlib import Path
from typing import Optional, Dict

from gpiozero import LED

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "db" / "data.db"

LED_PIN = 17
led = LED(LED_PIN)

# Defaults (αν δεν υπάρχουν στη settings_history)
DEFAULTS = {
    "soil1_led_pct": 88.0,     # Αγλαόνημα: πιο “υγρό” γενικά
    "soil3_led_pct": 82.0,     # Δράκαινα: πιο ανθεκτική
    "led_poll_sec": 20,        # ταιριάζει με collector=90s, δεν είναι συχνό
}

# Hysteresis για να μην τρεμοπαίζει (on κάτω από start, off πάνω από stop)
HYST = 1.0  # 1%

def _conn():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def get_latest_setting(key: str) -> Optional[str]:
    with _conn() as con:
        row = con.execute(
            "SELECT value FROM settings_history WHERE key=? ORDER BY ts DESC LIMIT 1",
            (key,),
        ).fetchone()
    return row["value"] if row else None

def get_float(key: str, default: float) -> float:
    v = get_latest_setting(key)
    if v is None:
        return default
    try:
        return float(v)
    except Exception:
        return default

def get_int(key: str, default: int) -> int:
    v = get_latest_setting(key)
    if v is None:
        return default
    try:
        return int(float(v))
    except Exception:
        return default

def log_system(level: str, code: str, message: str):
    with _conn() as con:
        con.execute(
            "INSERT INTO system_events(ts, level, code, message) VALUES (?, ?, ?, ?)",
            (int(time.time()), level, code, message),
        )
        con.commit()

def get_latest_pcts() -> Optional[Dict[int, Optional[float]]]:
    with _conn() as con:
        row = con.execute(
            "SELECT ts, soil1_pct, soil2_pct, soil3_pct FROM sensor_readings ORDER BY ts DESC LIMIT 1"
        ).fetchone()
    if not row:
        return None
    return {
        -1: row["ts"],
        1: row["soil1_pct"],
        2: row["soil2_pct"],
        3: row["soil3_pct"],
    }

def main():
    led.off()
    log_system("info", "led_start", f"LED indicator start on GPIO{LED_PIN}")

    led_state = False  # what we currently show
    last_reason = ""

    while True:
        th1 = get_float("soil1_led_pct", DEFAULTS["soil1_led_pct"])
        th3 = get_float("soil3_led_pct", DEFAULTS["soil3_led_pct"])
        poll = get_int("led_poll_sec", DEFAULTS["led_poll_sec"])

        pcts = get_latest_pcts()
        if not pcts:
            time.sleep(poll)
            continue

        s1 = pcts.get(1)
        s3 = pcts.get(3)

        # Determine desired state with hysteresis:
        # turn ON if <= threshold
        # turn OFF only if >= threshold + HYST (for both)
        want_on = False
        reason_parts = []

        if s1 is not None and s1 <= th1:
            want_on = True
            reason_parts.append(f"soil1={s1:.2f}<=th1={th1:.2f}")
        if s3 is not None and s3 <= th3:
            want_on = True
            reason_parts.append(f"soil3={s3:.2f}<=th3={th3:.2f}")

        if led_state:
            # currently ON -> keep ON unless both are safely above (threshold + hyst)
            safe1 = (s1 is None) or (s1 >= th1 + HYST)
            safe3 = (s3 is None) or (s3 >= th3 + HYST)
            if safe1 and safe3:
                want_on = False

        # Apply change only on transitions (no spam)
        if want_on != led_state:
            led_state = want_on
            if led_state:
                led.on()
                last_reason = ", ".join(reason_parts) if reason_parts else "threshold"
                log_system("info", "led_on", f"LED ON: {last_reason}")
            else:
                led.off()
                log_system("info", "led_off", "LED OFF")

        time.sleep(poll)

if __name__ == "__main__":
    main()
