import pandas as pd
import pytest

from pipeline import demo, huella, observatorio


def test_calculo_simple():
    factores = huella.cargar_factores()
    consumos = pd.DataFrame(
        {"fecha": ["2025-01", "2025-01"], "sede": ["A", "A"], "fuente": ["diesel", "electricidad_sen"], "cantidad": [1000, 10000]}
    )
    em = huella.calcular_emisiones(consumos, factores)
    diesel = factores.set_index("id").loc["diesel", "factor_kgco2e"]
    red = factores.set_index("id").loc["electricidad_sen", "factor_kgco2e"]
    assert em["tco2e"].sum() == pytest.approx((1000 * diesel + 10000 * red) / 1000)
    assert set(em["alcance"]) == {1, 2}


def test_fuente_desconocida_falla():
    consumos = pd.DataFrame({"fecha": ["2025-01"], "sede": ["A"], "fuente": ["carbon"], "cantidad": [1]})
    with pytest.raises(ValueError, match="carbon"):
        huella.calcular_emisiones(consumos, huella.cargar_factores())


def test_demo_completa_y_reproducible():
    a, b = demo.generar(), demo.generar()
    pd.testing.assert_frame_equal(a, b)
    em = huella.calcular_emisiones(a, huella.cargar_factores())
    assert em["fecha"].nunique() == 36
    assert (em["tco2e"] > 0).all()


def test_plantilla_valida():
    consumos = huella.cargar_consumos(huella.DATA / "plantilla" / "plantilla_consumos.csv")
    huella.calcular_emisiones(consumos, huella.cargar_factores())


def test_observatorio_columnas_variables(tmp_path):
    archivo = tmp_path / "retc.csv"
    pd.DataFrame(
        {
            "Año": [2023, 2023, 2023, 2022],
            "Nombre establecimiento": ["Central A", "Central A", "Fundición B", "Central A"],
            "Razón social": ["Gen SA", "Gen SA", "Min SA", "Gen SA"],
            "Región": ["Antofagasta", "Antofagasta", "Atacama", "Antofagasta"],
            "Comuna": ["Mejillones", "Mejillones", "Copiapó", "Mejillones"],
            "Rubro": ["Energía", "Energía", "Minería", "Energía"],
            "Contaminante": ["Dióxido de carbono (CO2)", "Material particulado", "Dióxido de carbono (CO2)", "CO2"],
            "Cantidad toneladas": ["1000,5", "3", "200", "900"],
        }
    ).to_csv(archivo, index=False, sep=";")
    res = observatorio.procesar([archivo])
    assert res["ultimo_anio"] == 2023
    assert {r["anio"]: r["tco2"] for r in res["por_anio"]} == {2022: 900.0, 2023: 1200.5}
    assert res["por_rubro"][0] == {"nombre": "Energía", "tco2": 1000.5}


def test_es_co2():
    assert observatorio.es_co2("Dióxido de carbono")
    assert observatorio.es_co2("CO2")
    assert not observatorio.es_co2("Monóxido de carbono")


def test_descarga_retoma_tras_corte(tmp_path):
    """Servidor local que corta la primera conexión a la mitad y respeta Range."""
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    contenido = bytes(range(256)) * 4096  # 1 MiB
    estado = {"peticiones": 0, "rangos": []}

    class Manejador(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            estado["peticiones"] += 1
            inicio = 0
            rango = self.headers.get("Range")
            estado["rangos"].append(rango)
            if rango:
                inicio = int(rango.split("=")[1].rstrip("-"))
                self.send_response(206)
            else:
                self.send_response(200)
            cuerpo = contenido[inicio:]
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            if estado["peticiones"] == 1:
                self.wfile.write(cuerpo[: len(cuerpo) // 2])  # corte a la mitad
                self.wfile.flush()
                self.connection.close()
                return
            self.wfile.write(cuerpo)

    servidor = ThreadingHTTPServer(("127.0.0.1", 0), Manejador)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    try:
        destino = tmp_path / "retc.xlsx"
        observatorio.descargar_archivo(f"http://127.0.0.1:{servidor.server_port}/x", destino, espera=0)
    finally:
        servidor.shutdown()
    assert destino.read_bytes() == contenido
    assert not (tmp_path / "retc.xlsx.part").exists()
    assert estado["peticiones"] == 2
    retomado = int(estado["rangos"][1].split("=")[1].rstrip("-"))  # el reintento pidió solo lo que faltaba
    assert 0 < retomado <= len(contenido) // 2


def test_descarga_reintenta_503(tmp_path):
    """El servidor responde 503 dos veces (como el del MMA saturado) y luego entrega el archivo."""
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    estado = {"peticiones": 0}

    class Manejador(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            estado["peticiones"] += 1
            if estado["peticiones"] <= 2:
                self.send_response(503)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Length", "5")
            self.end_headers()
            self.wfile.write(b"hola!")

    servidor = ThreadingHTTPServer(("127.0.0.1", 0), Manejador)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    try:
        destino = tmp_path / "x.csv"
        observatorio.descargar_archivo(f"http://127.0.0.1:{servidor.server_port}/x", destino, espera=0)
    finally:
        servidor.shutdown()
    assert destino.read_bytes() == b"hola!"
    assert estado["peticiones"] == 3


def test_excel_con_filas_de_titulo(tmp_path):
    """Los Excel 2023-2024 del RETC traen títulos antes de los encabezados."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["Registro de Emisiones y Transferencias de Contaminantes"])
    ws.append(["Emisiones al aire de fuentes puntuales 2024"])
    ws.append([])
    ws.append(["Año", "Nombre establecimiento", "Región", "Contaminante", "Cantidad toneladas"])
    ws.append([2024, "Central A", "Antofagasta", "Dióxido de carbono (CO2)", 1500.5])
    ws.append([2024, "Central A", "Antofagasta", "Material particulado", 2])
    archivo = tmp_path / "retc_2024.xlsx"
    wb.save(archivo)
    res = observatorio.procesar([archivo])
    assert res["por_anio"] == [{"anio": 2024, "tco2": 1500.5}]


def test_numeros_formato_chileno():
    serie = pd.Series(["1.234,5", "10,25", "7", "abc"])
    assert observatorio._a_numero(serie).tolist()[:3] == [1234.5, 10.25, 7.0]
    assert pd.isna(observatorio._a_numero(serie).iloc[3])


def test_excel_en_ingles_en_segunda_hoja(tmp_path):
    """Archivo con portada en la primera hoja y la tabla en inglés en la segunda."""
    from openpyxl import Workbook

    wb = Workbook()
    wb.active.title = "Notas"
    wb.active.append(["Este archivo contiene las emisiones declaradas"])
    ws = wb.create_sheet("Datos")
    ws.append([])
    ws.append(["year", "facility_name", "region", "pollutant", "amount_tonnes"])
    ws.append([2025, "Central A", "Antofagasta", "Carbon dioxide", 900])
    ws.append([2025, "Central A", "Antofagasta", "Carbon monoxide", 5])
    archivo = tmp_path / "retc_2025.xlsx"
    wb.save(archivo)
    res = observatorio.procesar([archivo])
    assert res["por_anio"] == [{"anio": 2025, "tco2": 900.0}]


def test_es_co2_en_ingles():
    assert observatorio.es_co2("Carbon dioxide")
    assert not observatorio.es_co2("Carbon monoxide")


def test_prefiere_nombre_legible_sobre_codigo():
    mapa = observatorio._mapear_columnas(["año", "contaminante_id", "contaminante", "emision_combustible_primario", "emision_total"])
    assert mapa["contaminante"] == "contaminante"
    assert mapa["toneladas"] == "emision_total"
