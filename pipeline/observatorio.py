"""Observatorio: emisiones de CO2 de fuentes puntuales en Chile (RETC, MMA).

Descarga los archivos anuales del dataset "Emisiones al aire de fuentes
puntuales" publicado en datos.gob.cl, filtra el CO2 y genera agregados por
año, región, rubro y establecimiento para el dashboard.

Requiere acceso a internet hacia datos.gob.cl y datosretc.mma.gob.cl
(el GitHub Action lo tiene). Uso:
    python -m pipeline.observatorio            # descarga + procesa
    python -m pipeline.observatorio --sin-descarga   # solo procesa data/raw/retc
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
import unicodedata
from pathlib import Path

import pandas as pd
import requests

from . import DATA, SITE_DATA

CKAN_API = "https://datos.gob.cl/api/3/action/package_show"
DATASET = "emisiones-al-aire-de-fuente-puntuales"
CARPETA_RAW = DATA / "raw" / "retc"
SALIDA = SITE_DATA / "observatorio.json"
MAX_ANIOS = 6  # cada archivo anual pesa decenas de MB

# Años que no se publican porque sus cifras no son confiables. Desde 2023 los
# archivos traen "emision_retc" (valor validado por el RETC) y se usa ese; el
# archivo 2022 no lo trae y su "cantidad_toneladas" incluye declaraciones
# imposibles (p. ej. hornos de una fundición con varios Mt de CO2 cada uno).
ANIOS_EXCLUIDOS = {
    2022: "El archivo 2022 no incluye el valor validado por el RETC y contiene declaraciones "
    "imposibles; su total (113 Mt) casi duplica al de 2021.",
}

# Nombre lógico -> patrones posibles en el encabezado (ya normalizado).
# El RETC ha cambiado nombres de columnas entre años, por eso se buscan por patrón.
COLUMNAS = {
    "anio": [r"^ano$", r"^anio$", r"^periodo$", r"^ano_", r"^year$", r"^year_"],
    "establecimiento": [r"nombre_establecimiento", r"^establecimiento", r"nombre_fuente", r"facility", r"establishment"],
    "razon_social": [r"razon_social", r"raz_social", r"company", r"business_name", r"legal_name"],
    "region": [r"^region$", r"^region_", r"nombre_region"],
    "comuna": [r"^comuna$", r"^comuna_", r"nombre_comuna", r"commune", r"municipality"],
    "rubro": [r"rubro", r"ciiu.*glosa", r"glosa_ciiu", r"sector", r"actividad", r"industry", r"activity"],
    "contaminante": [r"contaminante", r"pollutant", r"contaminant", r"substance"],
    "toneladas": [r"^emision_retc$", r"cantidad_toneladas", r"toneladas", r"emision_total", r"^emision$", r"emision", r"cantidad", r"tonnes", r"tons", r"quantity", r"amount"],
}


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", texto.lower()).strip("_")


def _mapear_columnas(columnas: list[str]) -> dict[str, str]:
    normalizadas = {_normalizar(c): c for c in columnas}
    # Las columnas de código ("contaminante_id") van al final: se prefiere el nombre legible.
    orden = sorted(normalizadas.items(), key=lambda kv: kv[0].endswith("_id") or kv[0].startswith("id_"))
    mapa = {}
    for logico, patrones in COLUMNAS.items():
        for patron in patrones:
            hit = next((orig for norm, orig in orden if re.search(patron, norm)), None)
            if hit is not None and hit not in mapa.values():
                mapa[logico] = hit
                break
    return mapa


def listar_recursos() -> list[dict]:
    resp = requests.get(CKAN_API, params={"id": DATASET}, timeout=60)
    resp.raise_for_status()
    recursos = resp.json()["result"]["resources"]
    return [r for r in recursos if str(r.get("format", "")).lower() in {"csv", "xlsx", "xls"} and r.get("url")]


def _anio_recurso(recurso: dict) -> int:
    hallado = re.findall(r"(?:19|20)\d{2}", f"{recurso.get('name', '')} {recurso.get('url', '')}")
    return int(hallado[0]) if hallado else 0


REINTENTABLES = {429, 500, 502, 503, 504}  # servidor saturado o caído momentáneamente


class ServidorOcupado(Exception):
    def __init__(self, codigo: int, espera: float | None):
        super().__init__(f"HTTP {codigo}")
        self.espera = espera


def descargar_archivo(url: str, destino: Path, intentos: int = 6, espera: float = 5.0) -> None:
    """Descarga con reintentos ante cortes de conexión y respuestas 429/5xx.
    Si la conexión se corta, retoma desde el byte donde quedó (cabecera Range)
    cuando el servidor lo permite. Escribe en un .part y solo lo renombra al
    terminar, para no dejar archivos a medias."""
    parcial = destino.with_name(destino.name + ".part")
    for intento in range(1, intentos + 1):
        ya = parcial.stat().st_size if parcial.exists() else 0
        cabeceras = {"Range": f"bytes={ya}-"} if ya else {}
        try:
            with requests.get(url, timeout=300, stream=True, headers=cabeceras) as r:
                if r.status_code in REINTENTABLES:
                    retry_after = r.headers.get("Retry-After", "")
                    raise ServidorOcupado(r.status_code, float(retry_after) if retry_after.isdigit() else None)
                r.raise_for_status()
                modo = "ab" if ya and r.status_code == 206 else "wb"  # 200 = el servidor reenvía todo
                with open(parcial, modo) as f:
                    for bloque in r.iter_content(1 << 16):
                        f.write(bloque)
            parcial.replace(destino)
            return
        except (ServidorOcupado, requests.ConnectionError, requests.Timeout, requests.exceptions.ChunkedEncodingError) as error:
            if intento == intentos:
                if isinstance(error, ServidorOcupado):
                    raise requests.HTTPError(f"{error} tras {intentos} intentos: {url}") from error
                raise
            pausa = min(getattr(error, "espera", None) or espera * 2 ** (intento - 1), 120)
            motivo = str(error) if isinstance(error, ServidorOcupado) else error.__class__.__name__
            print(f"  {motivo}; reintento {intento}/{intentos - 1} en {pausa:.0f}s")
            time.sleep(pausa)


def descargar(max_anios: int = MAX_ANIOS, pausa_entre: float = 5.0) -> list[Path]:
    CARPETA_RAW.mkdir(parents=True, exist_ok=True)
    recursos = sorted(listar_recursos(), key=_anio_recurso, reverse=True)[:max_anios]
    rutas, faltantes = [], []
    for i, recurso in enumerate(recursos):
        url = recurso["url"]
        destino = CARPETA_RAW / url.rsplit("/", 1)[-1]
        if not destino.exists():
            if i:
                time.sleep(pausa_entre)  # no saturar el servidor del MMA
            print(f"Descargando {recurso.get('name')} …")
            try:
                descargar_archivo(url, destino)
            except requests.RequestException as error:
                # Un año que no baja no debe impedir publicar los demás.
                print(f"AVISO: no se pudo descargar {recurso.get('name')}: {error}")
                faltantes.append(recurso.get("name", url))
                continue
        rutas.append(destino)
    if faltantes and os.environ.get("GITHUB_ACTIONS"):
        # Anotación visible en el resumen del Action, aunque el paso termine en verde.
        print(f"::warning title=RETC incompleto::No se descargaron {len(faltantes)} archivo(s): {'; '.join(faltantes)}")
    return rutas


def _fila_encabezado(muestra: pd.DataFrame) -> int:
    """Algunos Excel del RETC traen filas de título antes de los encabezados.
    Devuelve la primera fila que contiene las columnas obligatorias."""
    for i, fila in muestra.iterrows():
        mapa = _mapear_columnas([str(v) for v in fila.dropna().tolist()])
        if {"anio", "contaminante", "toneladas"} <= mapa.keys():
            return int(i)
    return 0


def _fila_encabezado_o_none(muestra: pd.DataFrame) -> int | None:
    fila = _fila_encabezado(muestra)
    if fila or {"anio", "contaminante", "toneladas"} <= _mapear_columnas(
        [str(v) for v in muestra.iloc[0].dropna().tolist()] if len(muestra) else []
    ).keys():
        return fila
    return None


def _leer(ruta: Path) -> pd.DataFrame:
    if ruta.suffix.lower() == ".csv":
        for enc in ("utf-8", "latin-1"):
            try:
                return pd.read_csv(ruta, sep=None, engine="python", encoding=enc)
            except UnicodeDecodeError:
                continue
    # Busca la hoja y la fila donde están los encabezados (algunos archivos traen
    # portada, notas o filas de título antes de la tabla).
    hojas = pd.read_excel(ruta, sheet_name=None, header=None, nrows=60)
    for nombre, muestra in hojas.items():
        fila = _fila_encabezado_o_none(muestra)
        if fila is not None:
            return pd.read_excel(ruta, sheet_name=nombre, header=fila)
    for nombre, muestra in hojas.items():
        print(f"  {ruta.name} · hoja '{nombre}': primeras filas no vacías:")
        for _, f in muestra.dropna(how="all").head(6).iterrows():
            print("    ", [str(v)[:40] for v in f.dropna().tolist()[:14]])
    return pd.read_excel(ruta)


def _a_numero(serie: pd.Series) -> pd.Series:
    """Convierte cantidades que pueden venir como 1234.5, '1234,5' o '1.234,5'."""
    if pd.api.types.is_numeric_dtype(serie):
        return serie
    texto = serie.astype(str).str.strip()
    formato_es = texto.str.contains(",", regex=False)
    texto = texto.where(~formato_es, texto.str.replace(".", "", regex=False).str.replace(",", ".", regex=False))
    return pd.to_numeric(texto, errors="coerce")


def leer_archivo(ruta: Path) -> pd.DataFrame:
    crudo = _leer(ruta)
    mapa = _mapear_columnas(list(crudo.columns))
    obligatorias = {"anio", "contaminante", "toneladas"}
    if not obligatorias <= mapa.keys():
        raise ValueError(
            f"{ruta.name}: no se reconocen las columnas {sorted(obligatorias - mapa.keys())}. "
            f"Columnas disponibles: {list(crudo.columns)}. Ajusta COLUMNAS en observatorio.py."
        )
    df = crudo[list(mapa.values())].rename(columns={v: k for k, v in mapa.items()})
    for faltante in COLUMNAS.keys() - mapa.keys():
        df[faltante] = "Sin dato"
    df["toneladas"] = _a_numero(df["toneladas"])
    df["anio"] = pd.to_numeric(df["anio"], errors="coerce")
    df = df.dropna(subset=["anio", "toneladas"])
    co2 = df[df["contaminante"].astype(str).map(es_co2)]
    # Diagnóstico en el registro del Action: permite ver qué entendió el script de cada archivo.
    print(
        f"  {ruta.name}: {len(df):,} filas, años {sorted(df['anio'].astype(int).unique().tolist())}, "
        f"{len(co2):,} filas de CO2 ({co2['toneladas'].sum():,.0f} t). Columnas usadas: {mapa}"
    )
    if co2.empty:
        print(f"  {ruta.name}: contaminantes más frecuentes: {df['contaminante'].value_counts().head(8).to_dict()}")
    if not co2.empty:
        # Diagnóstico de calidad: fuentes individuales con emisiones implausibles.
        grandes = co2[co2["toneladas"] > 1e6].sort_values("toneladas", ascending=False)
        tope = co2[co2["toneladas"] <= 4e6]["toneladas"].sum() / 1e6
        print(f"  {ruta.name}: total {co2['toneladas'].sum() / 1e6:.1f} Mt; sin fuentes > 4 Mt: {tope:.1f} Mt")
        if "emision_retc" in crudo.columns:
            retc = _a_numero(crudo.loc[co2.index, "emision_retc"]).sum() / 1e6
            print(f"  {ruta.name}: suma de emision_retc: {retc:.1f} Mt")
        for col in ("tipo_dato_retc", "sistema", "origen_data"):
            if col in crudo.columns:
                tabla = co2.groupby(crudo.loc[co2.index, col].astype(str))["toneladas"].sum() / 1e6
                print(f"  {ruta.name}: CO2 por {col} (Mt): {tabla.round(1).to_dict()}")
        tipo = "tipo_fuente" if "tipo_fuente" in crudo.columns else None
        for i, fila in grandes.head(12).iterrows():
            print(
                f"    > 1 Mt: {fila['toneladas'] / 1e6:6.2f} Mt | {str(fila['establecimiento'])[:40]} | "
                f"{str(fila['rubro'])[:30]} | {str(crudo.at[i, tipo])[:30] if tipo else ''}"
            )
    return df


def es_co2(contaminante: str) -> bool:
    norm = _normalizar(contaminante)
    return norm in {"co2", "dioxido_de_carbono", "dioxido_de_carbono_co2", "carbon_dioxide"} or (
        ("dioxido_de_carbono" in norm or "carbon_dioxide" in norm) and "mono" not in norm
    )


def procesar(rutas: list[Path]) -> dict:
    tablas = []
    for ruta in rutas:
        try:
            tablas.append(leer_archivo(ruta))
        except Exception as error:  # un archivo con formato raro no debe botar todo
            print(f"AVISO: se omite {ruta.name}: {error}")
    if not tablas:
        raise RuntimeError("No se pudo leer ningún archivo del RETC.")
    df = pd.concat(tablas, ignore_index=True)
    df = df[df["contaminante"].astype(str).map(es_co2)].copy()
    df["anio"] = df["anio"].astype(int)
    excluidos = {a: m for a, m in ANIOS_EXCLUIDOS.items() if a in set(df["anio"])}
    df = df[~df["anio"].isin(excluidos)]
    ultimo = int(df["anio"].max())
    actual = df[df["anio"] == ultimo]

    def top(columna: str, n: int = 10) -> list[dict]:
        serie = actual.groupby(columna)["toneladas"].sum().nlargest(n)
        return [{"nombre": str(k), "tco2": round(float(v), 1)} for k, v in serie.items()]

    por_anio = df.groupby("anio")["toneladas"].sum()
    establecimientos = (
        actual.groupby(["establecimiento", "razon_social", "region", "rubro"])["toneladas"]
        .sum()
        .nlargest(15)
        .reset_index()
    )
    return {
        "fuente": "RETC – Emisiones al aire de fuentes puntuales (MMA), vía datos.gob.cl",
        "ultimo_anio": ultimo,
        "anios_excluidos": [{"anio": a, "motivo": m} for a, m in sorted(excluidos.items())],
        "por_anio": [{"anio": int(a), "tco2": round(float(t), 1)} for a, t in por_anio.items()],
        "por_region": top("region", 16),
        "por_rubro": top("rubro"),
        "establecimientos": [
            {
                "establecimiento": str(r.establecimiento),
                "razon_social": str(r.razon_social),
                "region": str(r.region),
                "rubro": str(r.rubro),
                "tco2": round(float(r.toneladas), 1),
            }
            for r in establecimientos.itertuples()
        ],
    }


def ejecutar(sin_descarga: bool = False) -> None:
    rutas = sorted(r for r in CARPETA_RAW.glob("*") if r.suffix != ".part") if sin_descarga else descargar()
    resultado = procesar(rutas)
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Observatorio escrito en {SALIDA} (último año: {resultado['ultimo_anio']})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sin-descarga", action="store_true", help="usar solo archivos ya presentes en data/raw/retc")
    ejecutar(parser.parse_args().sin_descarga)


if __name__ == "__main__":
    main()
