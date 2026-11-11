// Observatorio RETC: lee site/data/observatorio.json generado por pipeline/observatorio.py.

(async () => {
  const { css, fmt, fmtPct, base, grafico, alCambiarTema, escapar } = Comun;
  const $ = (id) => document.getElementById(id);

  let datos;
  try {
    const resp = await fetch("data/observatorio.json");
    if (!resp.ok) throw new Error(resp.status);
    datos = await resp.json();
  } catch {
    $("sin-datos").classList.remove("oculto");
    return;
  }
  $("contenido").classList.remove("oculto");

  const M = 1e6;
  const graficos = { anios: grafico("g-anios"), region: grafico("g-region"), rubro: grafico("g-rubro") };

  function kpis() {
    const ult = datos.por_anio.at(-1);
    const prev = datos.por_anio.at(-2);
    $("kpi-anio").textContent = ult.anio;
    $("kpi-total").innerHTML = `${fmt(ult.tco2 / M, 1)}<small>MtCO₂</small>`;
    if (prev) {
      const d = ult.tco2 / prev.tco2 - 1;
      $("kpi-delta").innerHTML = `<span class="${d <= 0 ? "delta-bueno" : "delta-malo"}">${d <= 0 ? "▼" : "▲"} ${fmtPct(d)}</span> vs ${prev.anio}`;
    }
    const total = ult.tco2;
    const [r] = datos.por_region, [ru] = datos.por_rubro;
    $("kpi-region").textContent = r.nombre;
    $("kpi-region-det").textContent = `${fmt((r.tco2 / total) * 100, 0)}% del total nacional`;
    $("kpi-rubro").textContent = ru.nombre;
    $("kpi-rubro-det").textContent = `${fmt((ru.tco2 / total) * 100, 0)}% del total nacional`;
  }

  function barrasH(chart, lista) {
    const b = base();
    const asc = [...lista].reverse();
    chart.setOption(
      {
        textStyle: b.textStyle, grid: { ...b.grid, right: 48 },
        tooltip: { ...b.tooltip, trigger: "item", formatter: (p) => `<strong>${escapar(p.name)}</strong><br>${fmt(p.value * M, 0)} tCO₂` },
        xAxis: { type: "value", ...b.ejeValor, axisLabel: { show: false } },
        yAxis: {
          type: "category", data: asc.map((d) => d.nombre), ...b.ejeCategoria,
          axisLabel: { ...b.ejeCategoria.axisLabel, color: css("--text-secondary"), width: innerWidth < 600 ? 110 : 170, overflow: "truncate" },
        },
        series: [{
          type: "bar", barMaxWidth: 18,
          itemStyle: { color: css("--series-1"), borderRadius: [0, 4, 4, 0] },
          data: asc.map((d) => d.tco2 / M),
          label: { show: true, position: "right", color: css("--text-secondary"), formatter: (p) => fmt(p.value, 1) },
        }],
      },
      true
    );
  }

  function render() {
    kpis();
    const b = base();
    graficos.anios.setOption(
      {
        textStyle: b.textStyle, grid: { ...b.grid, top: 28 },
        tooltip: { ...b.tooltip, trigger: "item", formatter: (p) => `<strong>${p.name}</strong><br>${fmt(p.value * M, 0)} tCO₂` },
        xAxis: { type: "category", data: datos.por_anio.map((d) => String(d.anio)), ...b.ejeCategoria },
        yAxis: { type: "value", ...b.ejeValor },
        series: [{
          type: "bar", barMaxWidth: 40,
          itemStyle: { color: css("--series-1"), borderRadius: [4, 4, 0, 0] },
          data: datos.por_anio.map((d) => d.tco2 / M),
          label: { show: true, position: "top", color: css("--text-secondary"), formatter: (p) => fmt(p.value, 1) },
        }],
      },
      true
    );
    barrasH(graficos.region, datos.por_region);
    barrasH(graficos.rubro, datos.por_rubro);
    $("tabla-top").innerHTML = datos.establecimientos
      .map((e, i) => `<tr><td>${i + 1}</td><td>${escapar(e.establecimiento)}</td><td>${escapar(e.razon_social)}</td>
        <td>${escapar(e.region)}</td><td>${escapar(e.rubro)}</td><td class="num">${fmt(e.tco2, 0)}</td></tr>`)
      .join("");
    $("fuente").textContent = datos.fuente;
    const malas = datos.fuentes_excluidas || [];
    $("calidad").hidden = malas.length === 0;
    $("calidad-nota").textContent =
      `Fuentes que declaran más de ${fmt((datos.tope_por_fuente_t || 0) / M, 0)} millones de toneladas al año, ` +
      "más que la central termoeléctrica más grande de Chile. Son errores de declaración y no se suman a los totales.";
    $("tabla-calidad").innerHTML = malas
      .map((e) => `<tr><td>${e.anio}</td><td>${escapar(e.establecimiento)}</td><td>${escapar(e.rubro)}</td>
        <td class="num">${fmt(e.tco2, 0)}</td></tr>`)
      .join("");
    const excl = datos.anios_excluidos || [];
    $("excluidos").hidden = excl.length === 0;
    $("excluidos").replaceChildren(
      ...excl.flatMap((e) => {
        const b = document.createElement("strong");
        b.textContent = `${e.anio} no se muestra. `;
        return [b, document.createTextNode(e.motivo + " "), document.createElement("br")];
      })
    );
  }

  alCambiarTema(render);
  render();
})();
