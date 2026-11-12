import pandas as pd
import pytest

from pipeline import demo, factor_red, huella, observatorio


def test_calculo_simple():
    factores = huella.cargar_factores()
    consumos = pd.DataFrame(
        {"fecha": ["2025-01", "2025-01"], "sede": ["A", "A"], "fuente": ["diesel", "electricidad_sen"], "cantidad": [1000, 10000]}
    )
    em = huella.calcular_emisiones(consumos, factores)
    diesel = factores.set_index("id").loc["diesel", "factor_kgco2e"]
    red = factor_red.factor_para(2025, factor_red.cargar())
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
            "Año": [2021, 2021, 2021, 2020],
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
    assert res["ultimo_anio"] == 2021
    assert {r["anio"]: r["tco2"] for r in res["por_anio"]} == {2020: 900.0, 2021: 1200.5}
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


def test_prefiere_emision_retc_validada():
    mapa = observatorio._mapear_columnas(["año", "contaminante", "emision_total", "emision_retc"])
    assert mapa["toneladas"] == "emision_retc"


def test_anio_excluido_no_se_publica(tmp_path):
    archivo = tmp_path / "retc.csv"
    pd.DataFrame(
        {"Año": [2021, 2022], "Contaminante": ["CO2", "CO2"], "Cantidad toneladas": [10, 999]}
    ).to_csv(archivo, index=False)
    res = observatorio.procesar([archivo])
    assert [r["anio"] for r in res["por_anio"]] == [2021]
    assert res["anios_excluidos"][0]["anio"] == 2022


def test_fuente_implausible_se_excluye_y_registra(tmp_path):
    archivo = tmp_path / "retc.csv"
    pd.DataFrame(
        {
            "Año": [2024, 2024],
            "Nombre establecimiento": ["Central real", "Panadería"],
            "Contaminante": ["CO2", "CO2"],
            "Cantidad toneladas": [2_000_000, 18_500_000],
        }
    ).to_csv(archivo, index=False)
    res = observatorio.procesar([archivo])
    assert res["por_anio"] == [{"anio": 2024, "tco2": 2_000_000.0}]
    assert res["fuentes_excluidas"][0]["establecimiento"] == "Panadería"


def test_factor_red_anual_ponderado(tmp_path):
    archivo = tmp_path / "fe.csv"
    filas = ["anio,mes,sistema,factor_emision_avg,generacion_bruta_gwh,fecha_act"]
    for mes in range(1, 13):
        filas.append(f'2017,{mes},SIC,"0,2","300",2026-01-01')
        filas.append(f'2017,{mes},SING,"0,8","100",2026-01-01')
    filas.append('2018,1,SEN,"0,4","400",2026-01-01')  # año incompleto: se descarta
    archivo.write_text("\n".join(filas), encoding="utf-8-sig")
    tabla = factor_red.anual(archivo)
    assert tabla.to_dict(orient="records") == [{"anio": 2017, "factor_kgco2_kwh": 0.35}]


def test_factor_red_usa_ultimo_anio_disponible():
    tabla = {2023: 0.26, 2024: 0.21}
    assert factor_red.factor_para(2024, tabla) == 0.21
    assert factor_red.factor_para(2026, tabla) == 0.21
    assert factor_red.factor_para(2010, tabla) == 0.26


def test_electricidad_usa_factor_del_anio():
    red = factor_red.cargar()
    consumos = pd.DataFrame(
        {"fecha": ["2023-05", "2024-05"], "sede": ["A", "A"], "fuente": ["electricidad_sen"] * 2, "cantidad": [1000, 1000]}
    )
    em = huella.calcular_emisiones(consumos, huella.cargar_factores())
    assert em["tco2e"].tolist() == pytest.approx([red[2023], red[2024]])


def test_mapa_y_zona_norte(tmp_path):
    archivo = tmp_path / "retc.csv"
    pd.DataFrame(
        {
            "Año": [2024, 2024, 2024, 2023, 2024],
            "Nombre establecimiento": ["Central Angamos", "Central Angamos", "Panadería", "Central Angamos", "Planta sin coordenadas"],
            "Comuna": ["Mejillones", "Mejillones", "Santiago", "Mejillones", "Tocopilla"],
            "Rubro": ["Termoeléctricas"] * 2 + ["Otras industrias manufactureras", "Termoeléctricas", "Minería"],
            "Latitud": ["-23,0686", "-23,0686", "-33,45", "-23,0686", ""],
            "Longitud": ["-70,3688", "-70,3688", "-70,66", "-70,3688", ""],
            "Contaminante": ["CO2"] * 5,
            "Cantidad toneladas": ["1500000", "500000", "200", "2100000", "5000"],
        }
    ).to_csv(archivo, index=False, sep=";")
    res = observatorio.procesar([archivo])
    # El mapa suma por establecimiento, exige coordenadas válidas y el umbral mínimo.
    assert len(res["mapa"]) == 1
    punto = res["mapa"][0]
    assert punto["tco2"] == 2_000_000.0 and punto["grupo"] == "Termoeléctricas"
    assert (punto["lat"], punto["lon"]) == (-23.0686, -70.3688)
    # La zona norte incluye todos los años y a Tocopilla aunque no tenga coordenadas.
    zona = {r["anio"]: r for r in res["zona_norte"]["por_anio"]}
    assert zona[2023]["Mejillones"] == 2_100_000.0
    assert zona[2024]["Tocopilla"] == 5000.0
    assert res["zona_norte"]["top"][0]["establecimiento"] == "Central Angamos"


def test_grupo_rubro():
    assert observatorio.grupo_rubro("Termoeléctricas") == "Termoeléctricas"
    assert observatorio.grupo_rubro("Industria del papel y celulosa") == "Celulosa y papel"
    assert observatorio.grupo_rubro("Minería") == "Minería"
    assert observatorio.grupo_rubro("Pesca y acuicultura") == "Otros"
