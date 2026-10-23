import json
import sys
import time
import requests

API_URL = "http://localhost:8000/api/v1/telemetry"
TEST_NAME = sys.argv[1]   # es. ai_distilbert
DURATA = 300

print(f"[*] Avvio test: {TEST_NAME}...")
time.sleep(15)

start_ts = time.time()
print("[*] >>> LANCIA ORA: premi INVIO sulla VM <<<")
time.sleep(DURATA)
end_ts = time.time()
print("start:", start_ts, "end:", end_ts)

while True:
    try:
        R = float(input("Inferenze eseguite (da infer.py): "))
        break
    except ValueError:
        print("Scrivi solo il numero, es. 3520")

summary = requests.get(f"{API_URL}/summary", params={
    "start": start_ts, "end": end_ts, "functional_units": R
}).json()
with open(f"summary_{TEST_NAME}.json", "w") as f:
    json.dump(summary, f, indent=4)

csv_data = requests.get(f"{API_URL}/timeseries", params={
    "start": start_ts, "end": end_ts, "format": "csv"
}).text
with open(f"timeseries_{TEST_NAME}.csv", "w") as f:
    f.write(csv_data)

print(f"[+] Salvati: summary_{TEST_NAME}.json e timeseries_{TEST_NAME}.csv")
print("[+] SCI:", summary.get("sci_framework", {}).get("sci_score_g_co2eq_per_R"))