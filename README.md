# 🌿 Green AI & SCI Telemetry System — Nodo HPE DL380A

Progetto per il corso di **Architetture e Sistemi Software Distribuiti**. 
Questo repository raccoglie l'infrastruttura di osservabilità e il middleware per il monitoraggio energetico, computazionale e termico, finalizzato al calcolo dello score **Software Carbon Intensity (SCI)** secondo le specifiche della *Green Software Foundation*, applicato a carichi di lavoro AI sul nodo hardware HPE ProLiant DL380A.

---

## 🏗️ Architettura del Sistema e Componenti

L'infrastruttura è containerizzata tramite Docker Compose e si compone di tre layer principali:

1. **Prometheus (Time-Series Database):** 
   Esegue lo scraping periodico (con intervallo fisso a **15 secondi**) delle metriche esposte dai sensori hardware iLO del server, dalle sonde ambientali e dall'unità di raffreddamento a liquido (LCP).
2. **Grafana (Visualization Layer):** 
   Piattaforma di dashboarding per l'analisi in tempo reale del consumo energetico (Potenza istantanea in W, Energia cumulativa in Wh), del carico di CPU e Memory Bus, della frequenza operativa (DVFS) e del gradiente termico ($\Delta T$).
3. **Telemetry REST API (FastAPI Middleware):** 
   Un microservizio sviluppato in Python che astrae la complessità di Prometheus. Agisce da livello di transazione esponendo endpoint REST per calcolare l'energia consumata e le emissioni operative in base a finestre temporali personalizzate, esportando dataset puliti in formato JSON o CSV.

---

## 🔌 Come è fatta l'API REST

L'API è esposta sulla porta `8000` (documentazione interattiva Swagger disponibile su `http://localhost:8000/docs`). 

Espone principalmente due endpoint:

* **`GET /api/v1/telemetry/summary`**
  * **Cosa fa:** Riceve un intervallo temporale (`start` ed `end` in timestamp UNIX), calcola l'energia totale del server ($E$ in Wh) e della CPU tramite integrazione discreta sui campionamenti a 15s, estrae le medie di utilizzo e temperatura, e calcola lo score **SCI** normalizzato rispetto alle unità funzionali $R$ fornite ($SCI = \frac{E \times I}{R}$).
  * **Parametri principali:** `start`, `end`, `functional_units` ($R$), `carbon_intensity_g_kwh` ($I$, default Italia ~250 gCO2eq/kWh).

* **`GET /api/v1/telemetry/timeseries`**
  * **Cosa fa:** Estrae le serie storiche allineate a passo 15s di tutte le metriche della dashboard.
  * **Parametri principali:** `start`, `end`, `format` (impostabile su `json` oppure `csv`). Restituisce un dataset tabellare pronto per essere importato in script R o Python per analisi statistiche, matrici di correlazione o PCA.

---

## 🚀 Guida Rapida per i Compagni (Setup e Test)

### 1. Avvio dell'Infrastruttura
Assicuratevi di essere connessi alla VPN universitaria (per raggiungere i sensori hardware) e di avere Docker attivo. Nella cartella `docker/` eseguite:

```bash
docker compose up -d --build
```

Servizi attivi:
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (Importate il file dashboard_grafana.json per visualizzare la dashboard configurata).
- API Middleware: http://localhost:8000/docs.
 
### 2. Regole Metodologiche per i Test AI sulla VM
Per evitare errori di misurazione dovuti alla granularità di campionamento dello scraper:
* **Durata della Run ($\ge 3\text{--}5$ minuti)**: Non lanciate script di durata inferiore a 60 secondi. Fate girare l'inferenza o il training in batch continui (es. elaborazione di un dataset di test con $N \ge 1000$ campioni) per catturare un numero statisticamente rilevante di campionamenti a 15s.
* **Gruppo di Controllo (Baseline Idle)**: Prima di ogni test, registrate una finestra di 5-10 minuti a macchina scarica (usando il file baseline_idle_dl380a.csv come riferimento) per isolare il consumo di baseload (~252 W fissi) dal carico computazionale dinamico dell'AI.

### 3. Script Python per Automatizzare il Test e Salvare i Risultati
Durante l'esecuzione del vostro modello sulla VM, potete incapsulare il test con questo script Python per interrogare l'API e salvare in automatico il riepilogo SCI e la serie storica in CSV:Pythonimport time

```python
import json
import requests

API_URL = "http://localhost:8000/api/v1/telemetry"
TEST_NAME = "modello_ai_test_1"
FUNCTIONAL_UNITS_R = 1000  # Es. numero di inferenze o token generati

print(f"[*] Avvio test: {TEST_NAME}...")
time.sleep(15)  # Margine di stabilizzazione

start_ts = time.time()

# ==========================================
# INSERITE QUI IL VOSTRO CODICE DI INFERENZA
# (Assicuratevi che duri almeno 3-5 minuti)
# ==========================================
time.sleep(180)  # Simulazione durata test (3 min)

end_ts = time.time()

# 1. Download Riepilogo SCI (JSON)
summary = requests.get(f"{API_URL}/summary", params={
    "start": start_ts,
    "end": end_ts,
    "functional_units": FUNCTIONAL_UNITS_R
}).json()

with open(f"summary_{TEST_NAME}.json", "w") as f:
    json.dump(summary, f, indent=4)

# 2. Download Serie Storica allineata (CSV per R / Python)
csv_data = requests.get(f"{API_URL}/timeseries", params={
    "start": start_ts,
    "end": end_ts,
    "format": "csv"
}).text

with open(f"timeseries_{TEST_NAME}.csv", "w") as f:
    f.write(csv_data)

print(f"[+] Test completati. Salvati: summary_{TEST_NAME}.json e timeseries_{TEST_NAME}.csv")
print("[+] SCI Score ottenuto:", summary.get("sci_framework", {}).get("sci_score_g_co2eq_per_R"))
```
