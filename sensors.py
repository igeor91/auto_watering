import time
import threading
import statistics
from typing import Optional, Tuple

import spidev

import board
import adafruit_dht


# --- MCP3008 (SPI0, CE0) ---
_SPI_BUS = 0
_SPI_DEV = 0       # 0=CE0 (GPIO8/pin24), 1=CE1 (GPIO7/pin26)
_SPI_MAX_HZ = 1_000_000

# Tuning for stability
_SOIL_CHANNELS = (0, 1, 2)
_ADC_SAMPLES = 21          # median of 21 samples (odd number)
_ADC_SAMPLE_DELAY_S = 0.005  # 5ms between samples
_ADC_SETTLE_S = 0.002        # 2ms settle after dummy read

_spi_lock = threading.Lock()
_spi = spidev.SpiDev()
_spi.open(_SPI_BUS, _SPI_DEV)
_spi.max_speed_hz = _SPI_MAX_HZ


def _read_mcp3008_once(channel: int) -> int:
    """Μία ανάγνωση 0..1023 από MCP3008 κανάλι 0..7 (χωρίς filtering)."""
    if channel < 0 or channel > 7:
        raise ValueError("channel must be 0..7")
    with _spi_lock:
        adc = _spi.xfer2([1, (8 + channel) << 4, 0])
    return ((adc[1] & 3) << 8) | adc[2]


def read_mcp3008(channel: int) -> int:
    """
    Επιστρέφει σταθερή τιμή 0..1023 από MCP3008.
    Κάνει:
      - dummy read (για να καθαρίσει ο mux/S&H)
      - μικρό settle
      - median από πολλαπλά samples (κόβει spikes/θόρυβο)
    """
    # Dummy read + settle
    _ = _read_mcp3008_once(channel)
    time.sleep(_ADC_SETTLE_S)

    vals = []
    for _ in range(_ADC_SAMPLES):
        vals.append(_read_mcp3008_once(channel))
        time.sleep(_ADC_SAMPLE_DELAY_S)

    return int(statistics.median(vals))


def read_soil_raw() -> Tuple[int, int, int]:
    """
    Soil sensors στα CH0, CH1, CH2.
    Επιστρέφει (s1, s2, s3) raw 0..1023, με median filtering.
    """
    c1, c2, c3 = _SOIL_CHANNELS
    s1 = read_mcp3008(c1)
    s2 = read_mcp3008(c2)
    s3 = read_mcp3008(c3)
    return s1, s2, s3


# --- DHT22 on GPIO4 (pin 7) ---
_dht = adafruit_dht.DHT22(board.D4, use_pulseio=False)


def read_dht22() -> Tuple[Optional[float], Optional[float]]:
    """
    Επιστρέφει (temp_c, hum_pct) ή (None, None) αν αποτύχει.
    Κάνει 1 retry με μικρή καθυστέρηση γιατί ο DHT22 συχνά πετάει transient errors.
    """
    for attempt in range(2):
        try:
            t = _dht.temperature
            h = _dht.humidity
            if t is None or h is None:
                raise RuntimeError("DHT returned None")
            return float(t), float(h)
        except Exception:
            time.sleep(0.25 + 0.15 * attempt)

    return None, None
