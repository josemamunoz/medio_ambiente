"""Factor de emisión oficial de la red eléctrica (CNE, vía datos.gob.cl).

Descarga el dataset "Factor de Emisión" de la Comisión Nacional de Energía
(promedio mensual en tCO2/MWh, por sistema) y calcula el promedio anual
ponderado por generación bruta. Hasta 2017 existían dos sistemas (SIC y SING);
desde 2018 el Sistema Eléctrico Nacional (SEN). Para esos años se ponderan
ambos sistemas, lo que equivale al factor del país.

tCO2/MWh es lo mismo que kgCO2/kWh, la unidad de la calculadora.

    python -m pipeline.factor_red              # descarga y actualiza
    python -m pipeline.factor_red --sin-descarga  # recalcula desde data/raw
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import requests

from . import DATA

CKAN_API = "https://datos.gob.cl/api/3/action/package_show"
DATASET = "factor-emision"
CRUDO = DATA / "raw" / "factor_emision_mensual_sen.csv"
SALIDA = DATA / "referencia" / "factor_red_sen.csv"
FUENTE = "CNE – Factor de Emisión Mensual SEN (datos.gob.cl)"


def descargar() -> Path:
    resp = requests.get(CKAN_API, params={"id": DATASET}, timeout=60)
    resp.raise_for_status()
    recursos = [r for r in resp.json()["result"]["resources"] if str(r.get("format", "")).lower() == "csv"]
    if not recursos:
        raise RuntimeError("El dataset de la CNE no trae un CSV.")
    CRUDO.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(recursos[0]["url"], timeout=120)
    r.raise_for_status()
    CRUDO.write_bytes(r.content)
    return CRUDO


def anual(ruta: Path) -> pd.DataFrame:
    """Promedio anual ponderado por generación (kgCO2/kWh)."""
    df = pd.read_csv(ruta, encoding="utf-8-sig", decimal=",")
    faltan = {"anio", "mes", "factor_emision_avg", "generacion_bruta_gwh"} - set(df.columns)
    if faltan:
        raise ValueError(f"El CSV de la CNE cambió de formato; faltan columnas {sorted(faltan)}")
    df["ponderado"] = df["factor_emision_avg"] * df["generacion_bruta_gwh"]
    g = df.groupby("anio").agg(ponderado=("ponderado", "sum"), gen=("generacion_bruta_gwh", "sum"), meses=("mes", "nunique"))
    g["factor_kgco2_kwh"] = (g["ponderado"] / g["gen"]).round(4)
    g = g[g["meses"] == 12]  # solo años completos
    return g[["factor_kgco2_kwh"]].reset_index()


def cargar() -> dict[int, float]:
    """Factor por año desde la copia versionada en data/referencia."""
    tabla = pd.read_csv(SALIDA)
    return dict(zip(tabla["anio"].astype(int), tabla["factor_kgco2_kwh"].astype(float)))


def factor_para(anio: int, tabla: dict[int, float]) -> float:
    """Factor del año; si el año no está publicado aún, el último disponible."""
    if anio in tabla:
        return tabla[anio]
    anteriores = [a for a in tabla if a <= anio]
    return tabla[max(anteriores)] if anteriores else tabla[min(tabla)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sin-descarga", action="store_true")
    args = parser.parse_args()
    ruta = CRUDO if args.sin_descarga else descargar()
    tabla = anual(ruta)
    tabla.to_csv(SALIDA, index=False)
    ultimo = tabla.iloc[-1]
    print(f"Factor de la red actualizado en {SALIDA} ({len(tabla)} años; {int(ultimo.anio)}: {ultimo.factor_kgco2_kwh} kgCO2/kWh)")


if __name__ == "__main__":
    main()
