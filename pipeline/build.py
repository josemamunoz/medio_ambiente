"""Construye los JSON que consume el sitio (site/data/).

    python -m pipeline.build                  # factores + demo de huella
    python -m pipeline.build --observatorio   # además descarga y procesa el RETC
"""

from __future__ import annotations

import argparse
import json

from . import SITE_DATA, demo, factor_red, huella


def escribir_json(nombre: str, contenido) -> None:
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    (SITE_DATA / nombre).write_text(json.dumps(contenido, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  site/data/{nombre}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--observatorio", action="store_true", help="descargar y procesar datos del RETC")
    args = parser.parse_args()

    if not demo.ARCHIVO.exists():
        demo.main()
    factores = huella.cargar_factores()
    consumos = huella.cargar_consumos(demo.ARCHIVO)
    huella.calcular_emisiones(consumos, factores)  # valida que todas las fuentes tengan factor

    print("Escribiendo datos del sitio:")
    escribir_json("factores.json", factores.to_dict(orient="records"))
    red = factor_red.cargar()
    escribir_json(
        "factor_red.json",
        {"fuente": factor_red.FUENTE, "anios": [{"anio": a, "factor": f} for a, f in sorted(red.items())]},
    )
    escribir_json("demo.json", {"empresa": demo.EMPRESA, "consumos": consumos.to_dict(orient="records")})

    if args.observatorio:
        from . import observatorio

        observatorio.ejecutar()


if __name__ == "__main__":
    main()
