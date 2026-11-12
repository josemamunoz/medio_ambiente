# Sustentabilidad Chile · Dashboards de huella de carbono y emisiones

Dashboards web de sustentabilidad para empresas en Chile, construidos con **Python + HTML** como alternativa a Power BI:
sin licencias, publicados gratis en GitHub Pages y actualizados automáticamente.

| Módulo | Qué muestra | Datos |
|---|---|---|
| **Huella de carbono corporativa** (`site/huella.html`) | Emisiones de alcance 1, 2 y 3 (GHG Protocol) por mes, sede y fuente. Permite cargar un CSV propio y recalcula en el navegador. | Empresa ficticia de demo + factores de emisión en `data/referencia/` |
| **Observatorio RETC** (`site/observatorio.html`) | Emisiones de CO₂ de la industria chilena por año, región, rubro y establecimiento; mapa interactivo y foco en Mejillones, Tocopilla y Antofagasta. | RETC – *Emisiones al aire de fuentes puntuales* (MMA), vía datos.gob.cl |

Sitio publicado: **https://josemamunoz.github.io/medio_ambiente/**

## Para quién

- Proveedores de la minería a los que sus clientes piden informar su huella de carbono.
- Empresas que reportan sostenibilidad a la CMF (NCG 461).
- Pymes que postulan al programa HuellaChile del Ministerio del Medio Ambiente.

## Estructura

```
pipeline/                  Python: cálculos y descarga de datos
  huella.py                cálculo consumo × factor, por alcance
  demo.py                  genera los consumos de la empresa ficticia
  observatorio.py          descarga y procesa el RETC (totales, mapa, zona norte)
  factor_red.py            factor de emisión oficial de la red (CNE)
  build.py                 genera los JSON que lee el sitio
data/
  referencia/factores_emision.csv   factores de emisión (editar aquí)
  referencia/factor_red_sen.csv     factor anual oficial de la red eléctrica (CNE)
  demo/consumos_demo.csv            consumos de la empresa demo
  plantilla/plantilla_consumos.csv  formato para cargar datos reales
site/                      sitio estático (HTML + CSS + JS; ECharts y Leaflet incluidos)
tests/                     pruebas con pytest
.github/workflows/pages.yml  actualiza datos y publica el sitio cada mes
```

## Uso local

```bash
pip install -r requirements.txt
python -m pipeline.build                 # factores + demo de huella
python -m pipeline.observatorio          # descarga el RETC (requiere internet)
python -m pipeline.huella data/demo/consumos_demo.csv   # resumen en consola
pytest -q
python -m http.server -d site 8000       # abrir http://localhost:8000
```

### Formato de consumos

CSV con columnas `fecha` (AAAA-MM), `sede`, `fuente` y `cantidad`. Los valores de `fuente` son los `id` de
`data/referencia/factores_emision.csv` (por ejemplo `diesel`, `electricidad_sen` o `vuelos_nacionales`).
Se aceptan archivos separados por coma o por punto y coma (Excel en español).

## Publicación

1. En GitHub: *Settings → Pages → Source: GitHub Actions*.
2. Cada push a `main` (y el día 3 de cada mes) el Action corre los tests, regenera los datos, descarga el RETC y publica `site/`.
   Si el portal del Estado no responde, el sitio se publica igual y el observatorio muestra un aviso.

## Metodología y limitaciones

- **Emisiones = consumo × factor de emisión**, agrupadas por alcance según el GHG Protocol.
- Los factores de combustibles usan los valores por defecto del IPCC 2006 (solo CO₂; CH₄ y N₂O no se incluyen todavía).
- **Electricidad (alcance 2):** factor oficial de la CNE (*Factor de Emisión Mensual SEN*, datos.gob.cl), promediado por año y
  ponderado por generación. Cada consumo usa el factor de su año (0,26 kgCO₂/kWh en 2023, 0,21 en 2024, 0,25 en 2025).
  El Action lo actualiza cada mes.
- Los factores de alcance 3 (vuelos y residuos) son órdenes de magnitud basados en DEFRA/DESNZ; hay que verificar la versión vigente.
- La empresa de la demo es ficticia.
- El parser del RETC reconoce las columnas por patrones, porque sus nombres (y hasta el idioma) cambian entre años.
  Si un archivo nuevo no se reconoce, el script imprime sus columnas para ajustar `COLUMNAS` en `pipeline/observatorio.py`.

### Calidad de los datos del RETC

Los archivos del RETC traen errores de declaración evidentes: en 2024 un horno de panadería declara 18,5 Mt de CO₂,
seis veces lo que emite la central más grande del país. Sumar todo sin filtrar da totales mayores que el inventario
nacional completo de Chile. Por eso el observatorio:

1. Usa la columna `emision_retc` (valor validado por el RETC) cuando existe, desde 2023.
2. Excluye toda fuente que declare más de 4 Mt de CO₂ al año (la central más grande, Cochrane, declara ~3,1 Mt) y la lista en la página.
3. No publica 2022: ese archivo no trae el valor validado y su total (113 Mt) casi duplica el de 2021.

Resultado (Mt de CO₂ de fuentes puntuales): 2020: 62 · 2021: 67 · 2023: 54 · 2024: 49 · 2025: 47.

## Próximos pasos

- [x] Factor de emisión oficial del SEN (CNE), actualizado automáticamente.
- [x] Observatorio: mapa de establecimientos y foco en Mejillones, Tocopilla y Antofagasta.
- [ ] Agregar CH₄ y N₂O a los factores de combustión.
- [ ] Observatorio: impuesto verde por establecimiento.
- [ ] Huella: metas de reducción y trayectoria hacia carbono neutralidad.
- [ ] Exportar un reporte en PDF para el cliente.
