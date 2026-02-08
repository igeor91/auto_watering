import time
from db import init_db, get_conn, insert_sensor_readings_batch
from sensors import read_soil_raw, read_dht22

INTERVAL_SEC = 15          # sampling
FLUSH_EVERY_SEC = 15      # commit every 15 sec
MAX_BUFFER_ROWS = 5       # safety

def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def load_calibration(con):
    keys = ["soil1_dry","soil1_wet","soil2_dry","soil2_wet","soil3_dry","soil3_wet"]
    latest = {}

    for k in keys:
        row = con.execute(
            "SELECT value FROM settings_history WHERE key=? ORDER BY ts DESC LIMIT 1",
            (k,),
        ).fetchone()
        if row is not None:
            try:
                latest[k] = float(row["value"])
            except Exception:
                pass

    cal = {}
    for pot in (1, 2, 3):
        cal[pot] = {
            "dry": latest.get(f"soil{pot}_dry"),
            "wet": latest.get(f"soil{pot}_wet"),
        }
    return cal

def raw_to_pct(pot: int, raw: int, cal: dict) -> float | None:
    dry = cal[pot]["dry"]
    wet = cal[pot]["wet"]
    if dry is None or wet is None or dry == wet:
        return None
    pct = (raw - dry) / (wet - dry) * 100.0
    return float(clamp(pct, 0.0, 100.0))

def main():
    init_db()
    print(f"[collector] started, interval={INTERVAL_SEC}s")

    con = get_conn()
    buffer: list[tuple] = []
    last_flush = time.time()

    # cache calibration, refresh periodically (so we don't SELECT every 30s)
    cal = load_calibration(con)
    last_cal_refresh = time.time()
    CAL_REFRESH_SEC = 600  # 10 minutes

    try:
        while True:
            ts = int(time.time())

            # refresh calibration occasionally
            if time.time() - last_cal_refresh >= CAL_REFRESH_SEC:
                try:
                    cal = load_calibration(con)
                except Exception as e:
                    print("[collector] calibration load error:", e)
                last_cal_refresh = time.time()

            s1_raw = s2_raw = s3_raw = None
            s1_pct = s2_pct = s3_pct = None

            try:
                s1_raw, s2_raw, s3_raw = read_soil_raw()
                s1_pct = raw_to_pct(1, s1_raw, cal) if s1_raw is not None else None
                s2_pct = raw_to_pct(2, s2_raw, cal) if s2_raw is not None else None
                s3_pct = raw_to_pct(3, s3_raw, cal) if s3_raw is not None else None
            except Exception as e:
                print("[collector] soil read error:", e)

            try:
                temp_c, hum_pct = read_dht22()
            except Exception as e:
                print("[collector] dht22 read error:", e)
                temp_c, hum_pct = None, None

            row = (
                ts,
                s1_raw, s2_raw, s3_raw,
                s1_pct, s2_pct, s3_pct,
                temp_c, hum_pct,
                None,  # vin_v
                0,     # flags
                None,  # notes
            )
            buffer.append(row)

            print(f"[{ts}] raw=({s1_raw},{s2_raw},{s3_raw}) pct=({s1_pct},{s2_pct},{s3_pct}) T/H=({temp_c},{hum_pct})")

            now = time.time()
            should_flush = (now - last_flush >= FLUSH_EVERY_SEC) or (len(buffer) >= MAX_BUFFER_ROWS)

            if should_flush and buffer:
                try:
                    insert_sensor_readings_batch(con, buffer)
                    con.commit()
                    buffer.clear()
                    last_flush = now
                except Exception as e:
                    print("[collector] DB flush error:", e)
                    # try to recover: rollback and keep buffer (don't lose data)
                    try:
                        con.rollback()
                    except Exception:
                        pass

            time.sleep(INTERVAL_SEC)

    finally:
        # final flush on exit
        try:
            if buffer:
                insert_sensor_readings_batch(con, buffer)
                con.commit()
        except Exception:
            pass
        con.close()

if __name__ == "__main__":
    main()
