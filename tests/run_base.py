import json
import requests
import time

API_URL = "http://localhost:8000/api/v1/telemetry"
TEST_NAME = "idle"
FUNCTIONAL_UNITS_R = 1
DURATA = 300

print(f"[*] Avvio test: {TEST_NAME}...")
time.sleep(15)  # Margine di stabilizzazione

start_ts = time.time()

time.sleep(DURATA)  # Simulazione durata test (5 min)

end_ts = time.time()
print("start: ", start_ts, "end: ", end_ts)

# 1. Download Riepilogo SCI (JSON)
summary = requests.get(f"{API_URL}/summary", params={
    "start": start_ts,
    "end": end_ts,
    "functional_units": FUNCTIONAL_UNITS_R
}).json()

with open(f"summary_{TEST_NAME}.json", "w") as f:
    json.dump(summary, f, indent=4)

# 2. Download Serie Storica allineata (CSV per Python)
csv_data = requests.get(f"{API_URL}/timeseries", params={
    "start": start_ts,
    "end": end_ts,
    "format": "csv"
}).text

with open(f"timeseries_{TEST_NAME}.csv", "w") as f:
    f.write(csv_data)

print(f"[+] Test completati. Salvati: summary_{TEST_NAME}.json e timeseries_{TEST_NAME}.csv")
print("[+] SCI Score ottenuto:", summary.get("sci_framework", {}).get("sci_score_g_co2eq_per_R"))