# Auto Watering System (Raspberry Pi)

Αυτό το project υλοποιεί ένα σύστημα αυτόματου ποτίσματος για 3 γλάστρες με Raspberry Pi, αισθητήρες υγρασίας εδάφους, αισθητήρα θερμοκρασίας/υγρασίας (DHT22), αντλία νερού μέσω relay και web dashboard (Flask) για παρακολούθηση ιστορικού και συμβάντων.

## Χαρακτηριστικά
- **3 γλάστρες / 3 αισθητήρες υγρασίας εδάφους** (μέσω ADC MCP3008).
- **DHT22** για θερμοκρασία/υγρασία περιβάλλοντος.
- **Αντλία νερού** μέσω relay (GPIO control).
- **Πότισμα μόνο για τη Γλάστρα 2** (σύμφωνα με το υπάρχον setup).
- **Συλλογή μετρήσεων** σε σταθερό διάστημα και αποθήκευση σε **SQLite** (WAL).
- **Flask dashboard / API** για ιστορικό μετρήσεων και system events.

## Hardware
- Raspberry Pi (δοκιμασμένο σε Raspberry Pi 5 OS)
- MCP3008 (ADC 10-bit) σε SPI
- 3x Soil moisture sensors (analog)
- DHT22 (temp/humidity)
- Relay module + DC pump
- Σωληνάκια/διακλαδωτές για νερό
- Breadboard / καλωδίωση

## Wiring / GPIO (σύνοψη)
- **MCP3008** μέσω SPI (SPI0)
  - Channels: **CH0, CH1, CH2** για τις 3 γλάστρες
- **DHT22**: GPIO4
- **Relay/Pump**: GPIO19 (active_high=True)

> Σημείωση: Το ακριβές pinout/καλωδίωση πρέπει να ταιριάζει με το δικό σου breadboard setup.

## Project Structure (ενδεικτικά)
- `app.py` : Flask web server + API endpoint `/api/history`
- `collector.py` : δειγματοληψία αισθητήρων και flush σε SQLite
- `controlled_watering.py` : ελεγχόμενο πότισμα (pulses) για Γλάστρα 2
- `sensors.py` : ανάγνωση MCP3008 (median filtering) + DHT22
- `db.py` : SQLite helpers, inserts/fetch (WAL)
- `db/` : (τοπικά) βάση δεδομένων SQLite (ΔΕΝ ανεβαίνει στο GitHub)

## Sampling / Storage
- Δειγματοληψία κάθε **90s**
- Buffer & flush στη βάση περίπου κάθε **5 min**
- SQLite σε **WAL mode**
- Το endpoint `GET /api/history?hours=<N>` επιστρέφει:
  - `timestamps`, `soil1`, `soil2`, `soil3`, `temp`, `humidity` (ανάλογα την υλοποίηση)
  - `system_events` (π.χ. watering events, threshold changes κλπ.)

## Watering Logic (Pump Calibration)
- Pump pot: **2**
- GPIO relay: **GPIO19**
- `ML_PER_SEC = 20` (calibration)
- Pulses: `[1.0, 1.0, 1.5, 2.0, 2.0]` (σύνολο 7.5s)

## Setup (Python / venv)
### 1) Clone
```bash
git clone <YOUR_REPO_URL>
cd auto_watering
