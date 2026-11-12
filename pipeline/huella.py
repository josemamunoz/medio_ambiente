"""Cálculo de huella de carbono corporativa (alcances 1, 2 y 3, GHG Protocol).

Entrada: archivo de consumos en formato largo con columnas
    fecha (AAAA-MM), sede, fuente, cantidad
donde `fuente` corresponde a un `id` de data/referencia/factores_emision.csv.

Uso por línea de comandos:
    python -m pipeline.huella data/demo/consumos_demo.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from . import DATA, factor_red

COLUMNAS_CONSUMO = ["fecha", "sede", "fuente", "cantidad"]
ARCHIVO_FACTORES = DATA / "referencia" / "factores_emision.csv"
FUENTE_RED = "electricidad_sen"


def cargar_factores(ruta: Path = ARCHIVO_FACTORES) -> pd.DataFrame:
    factores = pd.read_csv(ruta)
    if factores["id"].duplicated().any():
        raise ValueError("Hay ids de factor duplicados en " + str(ruta))
    return factores


def cargar_consumos(ruta: Path) -> pd.DataFrame:
    consumos = pd.read_csv(ruta)
    faltantes = set(COLUMNAS_CONSUMO) - set(consumos.columns)
    if faltantes:
        raise ValueError(f"Faltan columnas en {ruta}: {sorted(faltantes)}")
    consumos = consumos[COLUMNAS_CONSUMO].copy()
    consumos["fecha"] = pd.to_datetime(consumos["fecha"], format="%Y-%m").dt.strftime("%Y-%m")
    consumos["cantidad"] = pd.to_numeric(consumos["cantidad"], errors="raise")
    return consumos


def calcular_emisiones(consumos: pd.DataFrame, factores: pd.DataFrame) -> pd.DataFrame:
    """Une consumos con factores y agrega la columna tco2e."""
    desconocidas = set(consumos["fuente"]) - set(factores["id"])
    if desconocidas:
        raise ValueError(f"Fuentes sin factor de emisión: {sorted(desconocidas)}")
    df = consumos.merge(
        factores[["id", "nombre", "alcance", "categoria", "unidad", "factor_kgco2e"]],
        left_on="fuente",
        right_on="id",
        how="left",
    ).drop(columns="id")
    df["anio"] = df["fecha"].str[:4].astype(int)
    # La electricidad usa el factor oficial de la CNE del año de cada consumo.
    red = factor_red.cargar()
    es_red = df["fuente"] == FUENTE_RED
    df.loc[es_red, "factor_kgco2e"] = df.loc[es_red, "anio"].map(lambda a: factor_red.factor_para(a, red))
    df["tco2e"] = df["cantidad"] * df["factor_kgco2e"] / 1000
    return df


def resumen_anual(emisiones: pd.DataFrame) -> pd.DataFrame:
    tabla = emisiones.pivot_table(
        index="anio", columns="alcance", values="tco2e", aggfunc="sum", fill_value=0
    ).rename(columns=lambda a: f"alcance_{a}")
    tabla["total"] = tabla.sum(axis=1)
    return tabla.round(2)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("consumos", type=Path, help="CSV de consumos (fecha, sede, fuente, cantidad)")
    args = parser.parse_args()
    emisiones = calcular_emisiones(cargar_consumos(args.consumos), cargar_factores())
    print("Emisiones por año (tCO2e)")
    print(resumen_anual(emisiones).to_string())


if __name__ == "__main__":
    main()
