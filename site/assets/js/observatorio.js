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
  const graficos = { anios: grafico("g-anios"), region: grafico("g-region"), rubro: grafico("g-rubro"), norte: grafico("g-norte") };

  // ---------- Mapa (Leaflet) ----------
  const GRUPOS = [
    { nombre: "Termoeléctricas", color: () => css("--series-1") },
    { nombre: "Celulosa y papel", color: () => css("--series-2") },
    { nombre: "Minería", color: () => css("--series-3") },
    { nombre: "Otros", color: () => css("--axis-muted") },
  ];
  const colorGrupo = (g) => (GRUPOS.find((x) => x.nombre === g) || GRUPOS[3]).color();
  const ZONAS = {
    chile: { bounds: [[-56, -76], [-17.5, -66]] },
    "antofagasta-region": { centro: [-23.4, -69.9], zoom: 7 },
    mejillones: { centro: [-23.09, -70.42], zoom: 12 },
    tocopilla: { centro: [-22.09, -70.2], zoom: 12 },
    antofagasta: { centro: [-23.62, -70.39], zoom: 11 },
  };
  let mapa = null, capaBase = null, capaPuntos = null;

  function temaOscuro() {
    const t = document.documentElement.dataset.theme;
    return t ? t === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  }

  function renderMapa() {
    const puntos = datos.mapa || [];
    if (!window.L || !puntos.length) {
      $("mapa").textContent = "No hay coordenadas disponibles para dibujar el mapa.";
      return;
    }
    if (!mapa) {
      mapa = L.map("mapa", { scrollWheelZoom: false, zoomSnap: 0.5 });
      mapa.fitBounds(ZONAS.chile.bounds);
      document.querySelectorAll(".mapa-controles .boton").forEach((b) =>
        b.addEventListener("click", () => {
          document.querySelectorAll(".mapa-controles .boton").forEach((x) => x.classList.toggle("activo", x === b));
          const z = ZONAS[b.dataset.zona];
          z.bounds ? mapa.flyToBounds(z.bounds, { duration: 0.8 }) : mapa.flyTo(z.centro, z.zoom, { duration: 0.8 });
        })
      );
    }
    if (capaBase) capaBase.remove();
    capaBase = L.tileLayer(
      `https://{s}.basemaps.cartocdn.com/${temaOscuro() ? "dark_all" : "light_all"}/{z}/{x}/{y}{r}.png`,
      { attribution: "© OpenStreetMap contributors © CARTO", subdomains: "abcd", maxZoom: 18 }
    ).addTo(mapa);

    if (capaPuntos) capaPuntos.remove();
    const max = puntos[0].tco2;
    const borde = css("--surface");
    capaPuntos = L.layerGroup(
      // De mayor a menor, para que los círculos chicos queden encima y se puedan tocar.
      puntos.map((p) =>
        L.circleMarker([p.lat, p.lon], {
          radius: Math.max(3, 22 * Math.sqrt(p.tco2 / max)),
          color: borde, weight: 1, fillColor: colorGrupo(p.grupo), fillOpacity: 0.75,
        }).bindPopup(
          `<strong>${escapar(p.establecimiento)}</strong><br>${escapar(p.razon_social)}<br>` +
          `${escapar(p.rubro)} · ${escapar(p.comuna)}<br><strong>${fmt(p.tco2, 0)} tCO₂</strong> en ${datos.ultimo_anio}`
        )
      )
    ).addTo(mapa);

    $("mapa-nota").textContent =
      `${fmt(puntos.length, 0)} establecimientos con más de ${fmt(datos.min_t_mapa || 0, 0)} tCO₂ en ${datos.ultimo_anio}. ` +
      "El tamaño del círculo es proporcional a sus emisiones; toca uno para ver el detalle.";
    $("mapa-leyenda").innerHTML = GRUPOS.map(
      (g) => `<span><span class="punto" style="background:${g.color()}"></span>${g.nombre}</span>`
    ).join("");
  }

  // ---------- Foco zona norte ----------
  function renderNorte() {
    const z = datos.zona_norte;
    if (!z) return;
    const b = base();
    const surface = css("--surface");
    graficos.norte.setOption(
      {
        textStyle: b.textStyle, grid: { ...b.grid, top: 16 },
        tooltip: {
          ...b.tooltip, trigger: "axis", axisPointer: { type: "shadow" },
          formatter: (ps) => `<strong>${ps[0].axisValue}</strong><br>` +
            ps.map((p) => `${p.marker}${p.seriesName}: ${fmt(p.value, 2)} Mt`).join("<br>"),
        },
        xAxis: { type: "category", data: z.por_anio.map((r) => String(r.anio)), ...b.ejeCategoria },
        yAxis: { type: "value", ...b.ejeValor, axisLabel: { ...b.ejeValor.axisLabel, formatter: (v) => fmt(v, 1) } },
        series: z.comunas.map((c, i) => ({
          name: c, type: "bar", barMaxWidth: 18, barGap: "10%",
          itemStyle: { color: css(`--series-${i + 1}`), borderColor: surface, borderWidth: 1, borderRadius: [4, 4, 0, 0] },
          data: z.por_anio.map((r) => r[c] / M),
        })),
      },
      true
    );
    $("tabla-norte").innerHTML = z.top
      .map((e, i) => `<tr><td>${i + 1}</td><td>${escapar(e.establecimiento)}</td><td>${escapar(e.comuna)}</td>
        <td>${escapar(e.rubro)}</td><td class="num">${fmt(e.tco2, 0)}</td></tr>`)
      .join("");
  }

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

  alCambiarTema(() => { render(); renderNorte(); renderMapa(); });
  render();
  renderNorte();
  renderMapa();
})();
