#!/usr/bin/env python3
import time
import sqlite3
from pathlib import Path
from gpiozero import OutputDevice

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "db" / "data.db"

RELAY_PIN = 19
relay = OutputDevice(RELAY_PIN, active_high=True, initial_value=False)  # OFF

POT = 2
ML_PER_SEC = 20.0

# Soft-start pulses (seconds) + pauses (seconds) after each pulse except last
PULSES = [1.0, 1.0, 1.5, 2.0, 2.0]      # ~20 + 20 + 30 + 40 + 40 = 150ml
PAUSES = [15, 30, 60, 60]              # pauses between pulses

def log_system(code: str, message: str, level: str = "info"):
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "INSERT INTO system_events(ts, level, code, message) VALUES (?, ?, ?, ?)",
        (int(time.time()), level, code, message),
    )
    con.commit()
    con.close()

def insert_watering_event(ts_start: int, ts_end: int, duration_s: float, est_ml: float):
    con = sqlite3.connect(DB_PATH)
    con.execute(
        """
        INSERT INTO watering_events
        (ts_start, ts_end, duration_s, estimated_ml, trigger_pot, result)
        VALUES (?, ?, ?, ?, ?, 'ok')
        """,
        (ts_start, ts_end, int(round(duration_s)), float(est_ml), POT),
    )
    con.commit()
    con.close()

def main():
    total_on = sum(PULSES)
    est_ml = total_on * ML_PER_SEC

    ts_start = int(time.time())
    log_system("pump_cycle_start", f"Pump cycle start pot={POT}, plan={PULSES}s, est_ml={est_ml:.1f}")

    try:
        for i, on_s in enumerate(PULSES, start=1):
            # pulse on
            log_system("pump_pulse_on", f"Pulse {i}/{len(PULSES)} ON {on_s:.2f}s (~{on_s*ML_PER_SEC:.1f}ml)")
            relay.on()
            time.sleep(on_s)
            relay.off()

            # pause
            if i <= len(PAUSES):
                time.sleep(PAUSES[i-1])

        ts_end = int(time.time())
        insert_watering_event(ts_start, ts_end, total_on, est_ml)
        log_system("pump_cycle_end", f"Pump cycle end pot={POT}, total_on={total_on:.2f}s, est_ml={est_ml:.1f}")

    except KeyboardInterrupt:
        relay.off()
        log_system("pump_cycle_abort", "Pump cycle aborted by user", level="warn")
        raise
    except Exception as e:
        relay.off()
        log_system("pump_cycle_error", f"Pump cycle error: {e}", level="error")
        raise
    finally:
        relay.off()

if __name__ == "__main__":
    main()
