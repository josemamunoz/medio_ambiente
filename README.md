# Sustentabilidad Chile · Dashboards de huella de carbono y emisiones

Dashboards web de sustentabilidad para empresas en Chile, construidos con **Python + HTML** como alternativa a Power BI:
sin licencias, publicados gratis en GitHub Pages y actualizados automáticamente.

| Módulo | Qué muestra | Datos |
|---|---|---|
| **Huella de carbono corporativa** (`site/huella.html`) | Emisiones de alcance 1, 2 y 3 (GHG Protocol) por mes, sede y fuente. Permite cargar un CSV propio y recalcula en el navegador. | Empresa ficticia de demo + factores de emisión en `data/referencia/` |
| **Observatorio RETC** (`site/observatorio.html`) | Emisiones de CO₂ de la industria chilena por año, región, rubro y establecimiento. | RETC – *Emisiones al aire de fuentes puntuales* (MMA), vía datos.gob.cl |

## Para quién

- Proveedores de la minería a los que sus clientes piden informar su huella de carbono.
- Empresas que reportan sostenibilidad a la CMF (NCG 461).
- Pymes que postulan al programa HuellaChile del Ministerio del Medio Ambiente.

## Estructura

```
pipeline/                  Python: cálculos y descarga de datos
  huella.py                cálculo consumo × factor, por alcance
  demo.py                  genera los consumos de la empresa ficticia
  observatorio.py          descarga y procesa el RETC
  build.py                 genera los JSON que lee el sitio
data/
  referencia/factores_emision.csv   factores de emisión (editar aquí)
  demo/consumos_demo.csv            consumos de la empresa demo
  plantilla/plantilla_consumos.csv  formato para cargar datos reales
site/                      sitio estático (HTML + CSS + JS + ECharts incluido)
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
- **El factor de la red eléctrica (0,30 kgCO₂/kWh) es un valor de demo.** Antes de cualquier reporte real hay que reemplazarlo por el
  promedio anual del dataset *Factor de Emisión – Promedio Mensual* de la CNE (Energía Abierta).
- Los factores de alcance 3 (vuelos y residuos) son órdenes de magnitud basados en DEFRA/DESNZ; hay que verificar la versión vigente.
- La empresa de la demo es ficticia.
- El parser del RETC reconoce las columnas por patrones, porque sus nombres cambian entre años. Si un archivo nuevo
  no se reconoce, el script indica qué columnas encontró para ajustar `COLUMNAS` en `pipeline/observatorio.py`.

## Próximos pasos

- [ ] Descargar automáticamente el factor de emisión del SEN desde Energía Abierta (CNE).
- [ ] Agregar CH₄ y N₂O a los factores de combustión.
- [ ] Observatorio: mapa por comuna y foco en Mejillones, Tocopilla y Antofagasta.
- [ ] Observatorio: impuesto verde por establecimiento.
- [ ] Huella: metas de reducción y trayectoria hacia carbono neutralidad.
- [ ] Exportar un reporte en PDF para el cliente.
