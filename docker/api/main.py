from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import PlainTextResponse
import requests
import time
import csv
import io
import os
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")

app = FastAPI(
    title="Green AI & SCI Telemetry API - DL380A",
    description="Middleware REST per l'estrazione delle metriche energetiche, termiche e il calcolo dello score SCI da Prometheus.",
    version="1.0.0"
)

# Modifica con http://prometheus:9090 se gira nella stessa rete Docker di Prometheus
import os
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")
MACHINE = "DL380A"
SCRAPE_INTERVAL = 15  # secondi


def query_prom_instant(promql: str, eval_time: float) -> float:
    """Esegue una instant query su Prometheus all'istante eval_time."""
    resp = requests.get(
        f"{PROMETHEUS_URL}/api/v1/query",
        params={"query": promql, "time": eval_time},
        timeout=10
    )
    resp.raise_for_status()
    data = resp.json()
    results = data.get("data", {}).get("result", [])
    if not results:
        return 0.0
    return float(results[0]["value"][1])


@app.get("/api/v1/telemetry/summary")
def get_task_summary(
    start: float = Query(..., description="Timestamp UNIX di inizio test AI (es. 1760540000)"),
    end: float = Query(default=None, description="Timestamp UNIX di fine test AI (default: ora)"),
    functional_units: float = Query(default=1.0, gt=0, description="Parametro R della formula SCI (es. numero di inferenze eseguite o 1000 token)"),
    carbon_intensity_g_kwh: float = Query(default=250.0, ge=0, description="Parametro I: Intensità di carbonio della rete elettrica in gCO2eq/kWh (default Italia ~250)")
):
    """
    Restituisce il riepilogo energetico, computazionale, termico e il calcolo SCI
    per un'esecuzione AI avvenuta tra `start` ed `end`.
    """
    if end is None:
        end = time.time()

    duration = int(end - start)
    if duration <= 0:
        raise HTTPException(status_code=400, detail="Il parametro 'end' deve essere maggiore di 'start'.")

    rng = f"{duration}s"

    try:
        # 1. Energia Totale e CPU (in Wh) tramite integrazione discreta (step 15s)
        total_energy_wh = query_prom_instant(
            f'sum(sum_over_time(ILO_PowerSupply{{machine="{MACHINE}"}}[{rng}])) * {SCRAPE_INTERVAL} / 3600', end
        )
        cpu_energy_wh = query_prom_instant(
            f'sum(sum_over_time(ILO_CPU_Power{{machine="{MACHINE}"}}[{rng}])) * {SCRAPE_INTERVAL} / 3600', end
        )

        # 2. Potenze medie e di picco (in W)
        avg_total_power_w = query_prom_instant(
            f'sum(avg_over_time(ILO_PowerSupply{{machine="{MACHINE}"}}[{rng}]))', end
        )
        avg_cpu_power_w = query_prom_instant(
            f'sum(avg_over_time(ILO_CPU_Power{{machine="{MACHINE}"}}[{rng}]))', end
        )

        # 3. Metriche Computazionali (CPU Util %, Memory Bus %, Freq MHz)
        avg_cpu_util = query_prom_instant(
            f'avg_over_time(ILO_CPU_Util{{machine="{MACHINE}"}}[{rng}])', end
        )
        max_cpu_util = query_prom_instant(
            f'max_over_time(ILO_CPU_Util{{machine="{MACHINE}"}}[{rng}])', end
        )
        avg_mem_bus_util = query_prom_instant(
            f'avg_over_time(ILO_Memory_Bus_Util{{machine="{MACHINE}"}}[{rng}])', end
        )
        avg_cpu_freq_mhz = query_prom_instant(
            f'avg_over_time(ILO_Avg_CPU_Freq{{machine="{MACHINE}", cpu="0"}}[{rng}])', end
        )

        # 4. Impatto Termico e Raffreddamento LCP
        avg_delta_t = query_prom_instant(
            f'avg_over_time(CMC_RearSensor_temperature[{rng}]) - avg_over_time(CMC_FrontSensor_temperature[{rng}])', end
        )
        avg_lcp_fans_rpm = query_prom_instant(f'avg_over_time(LCP_fans_speed[{rng}])', end)
        avg_lcp_comp_curr = query_prom_instant(f'avg_over_time(LCP_compressor_current[{rng}])', end)

        # 5. Calcolo Software Carbon Intensity (SCI) -> SCI = (O + M) / R dove O = E(kWh) * I
        energy_kwh = total_energy_wh / 1000.0
        operational_emissions_g_co2 = energy_kwh * carbon_intensity_g_kwh
        sci_score_g_co2_per_unit = operational_emissions_g_co2 / functional_units

        return {
            "metadata": {
                "machine": MACHINE,
                "start_timestamp": start,
                "end_timestamp": end,
                "duration_seconds": duration,
                "scrape_interval_seconds": SCRAPE_INTERVAL
            },
            "energy_and_power": {
                "total_energy_wh": round(total_energy_wh, 4),
                "cpu_energy_wh": round(cpu_energy_wh, 4),
                "other_components_energy_wh": round(max(0.0, total_energy_wh - cpu_energy_wh), 4),
                "avg_total_power_w": round(avg_total_power_w, 2),
                "avg_cpu_power_w": round(avg_cpu_power_w, 2),
                "avg_baseload_other_w": round(max(0.0, avg_total_power_w - avg_cpu_power_w), 2)
            },
            "compute_and_memory": {
                "avg_cpu_utilization_pct": round(avg_cpu_util, 2),
                "max_cpu_utilization_pct": round(max_cpu_util, 2),
                "avg_memory_bus_utilization_pct": round(avg_mem_bus_util, 2),
                "avg_cpu_frequency_mhz": round(avg_cpu_freq_mhz, 2)
            },
            "thermal_and_cooling": {
                "avg_server_delta_t_celsius": round(avg_delta_t, 2),
                "avg_lcp_fan_speed_rpm": round(avg_lcp_fans_rpm, 2),
                "avg_lcp_compressor_current_a": round(avg_lcp_comp_curr, 2)
            },
            "sci_framework": {
                "energy_kwh_E": round(energy_kwh, 6),
                "carbon_intensity_g_kwh_I": carbon_intensity_g_kwh,
                "operational_emissions_g_co2eq_O": round(operational_emissions_g_co2, 4),
                "embodied_emissions_M": "Excluded (Hardware lifecycle data not exposed by iLO)",
                "functional_unit_R": functional_units,
                "sci_score_g_co2eq_per_R": round(sci_score_g_co2_per_unit, 4)
            }
        }

    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Errore di comunicazione con Prometheus: {str(e)}")


@app.get("/api/v1/telemetry/timeseries")
def get_task_timeseries(
    start: float = Query(..., description="Timestamp UNIX di inizio"),
    end: float = Query(default=None, description="Timestamp UNIX di fine"),
    format: str = Query(default="json", pattern="^(json|csv)$", description="Formato di output: 'json' oppure 'csv'")
):
    """
    Estrae le serie temporali allineate (step 15s) per tutte le metriche della dashboard.
    Con `format=csv` restituisce direttamente un dataset tabellare pronto per l'analisi statistica.
    """
    if end is None:
        end = time.time()

    queries = {
        "total_power_w": f'sum(ILO_PowerSupply{{machine="{MACHINE}"}})',
        "cpu_power_w": f'sum(ILO_CPU_Power{{machine="{MACHINE}"}})',
        "cpu_util_pct": f'ILO_CPU_Util{{machine="{MACHINE}"}}',
        "mem_bus_util_pct": f'ILO_Memory_Bus_Util{{machine="{MACHINE}"}}',
        "cpu_freq_mhz": f'ILO_Avg_CPU_Freq{{machine="{MACHINE}", cpu="0"}}',
        "delta_t_celsius": 'CMC_RearSensor_temperature - CMC_FrontSensor_temperature',
        "lcp_fans_rpm": 'LCP_fans_speed',
        "lcp_compressor_a": 'LCP_compressor_current'
    }

    timeline = {}
    try:
        for metric_name, promql in queries.items():
            resp = requests.get(
                f"{PROMETHEUS_URL}/api/v1/query_range",
                params={"query": promql, "start": start, "end": end, "step": f"{SCRAPE_INTERVAL}s"},
                timeout=10
            )
            resp.raise_for_status()
            results = resp.json().get("data", {}).get("result", [])
            if results:
                for ts, val in results[0]["values"]:
                    ts_int = int(float(ts))
                    if ts_int not in timeline:
                        timeline[ts_int] = {"timestamp": ts_int}
                    timeline[ts_int][metric_name] = round(float(val), 3)

        sorted_rows = [timeline[ts] for ts in sorted(timeline.keys())]

        if format == "csv":
            output = io.StringIO()
            fieldnames = ["timestamp"] + list(queries.keys())
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            for row in sorted_rows:
                writer.writerow(row)
            return PlainTextResponse(content=output.getvalue(), media_type="text/csv")

        return {"machine": MACHINE, "step_seconds": SCRAPE_INTERVAL, "data": sorted_rows}

    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Errore di comunicazione con Prometheus: {str(e)}")