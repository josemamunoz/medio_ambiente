"""Genera datos de consumo de una empresa FICTICIA para la demo del dashboard.

"Proveedor Minero Demo SpA": servicios de mantención para la minería con
taller en Antofagasta y bodega en Mejillones, 2023-2025. Los números son
inventados pero tienen órdenes de magnitud plausibles, con estacionalidad y
una tendencia de reducción del diésel (electrificación parcial de la flota).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import DATA

EMPRESA = "Proveedor Minero Demo SpA (empresa ficticia)"
ARCHIVO = DATA / "demo" / "consumos_demo.csv"

# (sede, fuente) -> (cantidad mensual base, tendencia anual, amplitud estacional)
PERFIL = {
    ("Antofagasta", "diesel"): (18_000, -0.08, 0.10),
    ("Antofagasta", "gasolina"): (2_200, -0.03, 0.05),
    ("Antofagasta", "electricidad_sen"): (42_000, 0.06, 0.08),
    ("Antofagasta", "glp"): (350, 0.00, 0.30),
    ("Antofagasta", "vuelos_nacionales"): (28_000, 0.02, 0.25),
    ("Antofagasta", "residuos_relleno"): (6.5, -0.10, 0.05),
    ("Mejillones", "diesel"): (7_500, -0.05, 0.08),
    ("Mejillones", "electricidad_sen"): (15_000, 0.03, 0.05),
    ("Mejillones", "residuos_relleno"): (2.8, -0.06, 0.05),
}
# Fugas de refrigerante: eventos puntuales (sede, mes, kg)
FUGAS = [("Antofagasta", "2023-07", 4.0), ("Mejillones", "2024-02", 2.5), ("Antofagasta", "2025-11", 1.5)]


def generar(seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    meses = pd.period_range("2023-01", "2025-12", freq="M")
    filas = []
    for (sede, fuente), (base, tendencia, estacional) in PERFIL.items():
        for i, mes in enumerate(meses):
            factor_tendencia = (1 + tendencia) ** (i / 12)
            factor_estacional = 1 + estacional * np.cos(2 * np.pi * (mes.month - 7) / 12)
            ruido = rng.normal(1, 0.04)
            cantidad = base * factor_tendencia * factor_estacional * ruido
            filas.append((str(mes), sede, fuente, round(cantidad, 2)))
    for sede, mes, kg in FUGAS:
        filas.append((mes, sede, "refrigerante_r410a", kg))
    df = pd.DataFrame(filas, columns=["fecha", "sede", "fuente", "cantidad"])
    return df.sort_values(["fecha", "sede", "fuente"]).reset_index(drop=True)


def main() -> None:
    ARCHIVO.parent.mkdir(parents=True, exist_ok=True)
    generar().to_csv(ARCHIVO, index=False)
    print(f"Datos demo escritos en {ARCHIVO}")


if __name__ == "__main__":
    main()
