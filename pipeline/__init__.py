"""Pipeline de datos del proyecto de sustentabilidad (huella de carbono + observatorio)."""

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATA = RAIZ / "data"
SITE_DATA = RAIZ / "site" / "data"
