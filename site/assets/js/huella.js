// Dashboard de huella de carbono. Calcula en el navegador: consumo × factor.
// La misma lógica está en pipeline/huella.py (fuente de verdad para reportes).

(async () => {
  const { css, fmt, fmtPct, base, grafico, alCambiarTema, escapar } = Comun;
  const $ = (id) => document.getElementById(id);
  const MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];
  const ALCANCES = [1, 2, 3];
  const colorAlcance = (a) => css(`--series-${a}`);

  const [factoresLista, demo] = await Promise.all([
    fetch("data/factores.json").then((r) => r.json()),
    fetch("data/demo.json").then((r) => r.json()),
  ]);
  const factores = Object.fromEntries(factoresLista.map((f) => [f.id, f]));

  const estado = { empresa: demo.empresa, filas: [], anio: null, sede: "Todas" };

  const graficos = { mensual: grafico("g-mensual"), anual: grafico("g-anual"), fuentes: grafico("g-fuentes") };

  // ---------- Datos ----------
  function enriquecer(consumos) {
    return consumos.map((c) => {
      const f = factores[c.fuente];
      return {
        ...c,
        anio: Number(c.fecha.slice(0, 4)),
        mes: Number(c.fecha.slice(5, 7)),
        alcance: f.alcance,
        nombre: f.nombre,
        unidad: f.unidad,
        factor: f.factor_kgco2e,
        tco2e: (c.cantidad * f.factor_kgco2e) / 1000,
      };
    });
  }

  function cargarDatos(empresa, consumos) {
    estado.empresa = empresa;
    estado.filas = enriquecer(consumos);
    const anios = [...new Set(estado.filas.map((f) => f.anio))].sort();
    const sedes = [...new Set(estado.filas.map((f) => f.sede))].sort();
    estado.anio = anios[anios.length - 1];
    estado.sede = "Todas";
    $("filtro-anio").innerHTML = anios.map((a) => `<option>${a}</option>`).join("");
    $("filtro-anio").value = estado.anio;
    $("filtro-sede").innerHTML = ["Todas", ...sedes].map((s) => `<option>${escapar(s)}</option>`).join("");
    $("empresa").textContent = empresa;
    render();
  }

  const porSede = () => estado.filas.filter((f) => estado.sede === "Todas" || f.sede === estado.sede);
  const suma = (filas) => filas.reduce((acc, f) => acc + f.tco2e, 0);

  // ---------- Render ----------
  function render() {
    const filas = porSede();
    const delAnio = filas.filter((f) => f.anio === estado.anio);
    const anterior = filas.filter((f) => f.anio === estado.anio - 1);
    const total = suma(delAnio);

    $("kpi-total").innerHTML = `${fmt(total, 0)}<small>tCO₂e</small>`;
    if (anterior.length) {
      const delta = total / suma(anterior) - 1;
      const clase = delta <= 0 ? "delta-bueno" : "delta-malo";
      const flecha = delta <= 0 ? "▼" : "▲";
      $("kpi-total-delta").innerHTML = `<span class="${clase}">${flecha} ${fmtPct(delta)}</span> vs ${estado.anio - 1}`;
    } else {
      $("kpi-total-delta").textContent = "Sin año anterior para comparar";
    }
    for (const a of ALCANCES) {
      const v = suma(delAnio.filter((f) => f.alcance === a));
      $(`kpi-a${a}`).innerHTML = `${fmt(v, 0)}<small>tCO₂e</small>`;
      $(`kpi-a${a}-det`).textContent = total ? `${fmt((v / total) * 100, 0)}% del total` : "";
    }

    renderMensual(delAnio);
    renderAnual(filas);
    renderFuentes(delAnio, total);
  }

  function renderMensual(delAnio) {
    const b = base();
    const surface = css("--surface");
    const series = ALCANCES.map((a) => ({
      name: `Alcance ${a}`,
      type: "bar",
      stack: "total",
      barMaxWidth: 28,
      itemStyle: { color: colorAlcance(a), borderColor: surface, borderWidth: 1 },
      emphasis: { focus: "series" },
      data: MESES.map((_, i) => suma(delAnio.filter((f) => f.alcance === a && f.mes === i + 1))),
    }));
    graficos.mensual.setOption(
      {
        textStyle: b.textStyle, grid: b.grid,
        tooltip: {
          ...b.tooltip, trigger: "axis", axisPointer: { type: "shadow" },
          formatter: (ps) => {
            const tot = ps.reduce((s, p) => s + p.value, 0);
            return `<strong>${ps[0].axisValue} ${estado.anio}</strong><br>` +
              ps.map((p) => `${p.marker}${p.seriesName}: ${fmt(p.value)} t`).join("<br>") +
              `<br><strong>Total: ${fmt(tot)} tCO₂e</strong>`;
          },
        },
        xAxis: { type: "category", data: MESES, ...b.ejeCategoria },
        yAxis: { type: "value", ...b.ejeValor },
        series,
      },
      true
    );
  }

  function renderAnual(filas) {
    const b = base();
    const anios = [...new Set(filas.map((f) => f.anio))].sort();
    graficos.anual.setOption(
      {
        textStyle: b.textStyle, grid: { ...b.grid, top: 28 },
        tooltip: { ...b.tooltip, trigger: "item", formatter: (p) => `<strong>${p.name}</strong><br>${fmt(p.value)} tCO₂e` },
        xAxis: { type: "category", data: anios.map(String), ...b.ejeCategoria },
        yAxis: { type: "value", ...b.ejeValor },
        series: [{
          type: "bar",
          barMaxWidth: 44,
          data: anios.map((a) => ({
            value: suma(filas.filter((f) => f.anio === a)),
            itemStyle: { color: a === estado.anio ? css("--series-1") : css("--bar-muted"), borderRadius: [4, 4, 0, 0] },
          })),
          label: { show: true, position: "top", color: css("--text-secondary"), formatter: (p) => fmt(p.value, 0) },
        }],
      },
      true
    );
  }

  function renderFuentes(delAnio, total) {
    const b = base();
    const agrupado = {};
    for (const f of delAnio) {
      const g = (agrupado[f.fuente] ??= { nombre: f.nombre, alcance: f.alcance, unidad: f.unidad, factor: f.factor, cantidad: 0, tco2e: 0 });
      g.cantidad += f.cantidad;
      g.tco2e += f.tco2e;
    }
    const lista = Object.values(agrupado).sort((x, y) => y.tco2e - x.tco2e);
    const asc = [...lista].reverse();

    graficos.fuentes.setOption(
      {
        textStyle: b.textStyle, grid: { ...b.grid, right: 64 },
        tooltip: {
          ...b.tooltip, trigger: "item",
          formatter: (p) => {
            const g = asc[p.dataIndex];
            return `<strong>${escapar(g.nombre)}</strong><br>Alcance ${g.alcance}<br>${fmt(g.tco2e)} tCO₂e (${fmt((g.tco2e / total) * 100, 1)}%)`;
          },
        },
        // Cada barra lleva su valor; el eje numérico se omite para no saturar.
        xAxis: { type: "value", ...b.ejeValor, axisLabel: { show: false } },
        yAxis: { type: "category", data: asc.map((g) => g.nombre), ...b.ejeCategoria, axisLabel: { ...b.ejeCategoria.axisLabel, color: css("--text-secondary") } },
        series: [{
          type: "bar",
          barMaxWidth: 22,
          data: asc.map((g) => ({ value: g.tco2e, itemStyle: { color: colorAlcance(g.alcance), borderRadius: [0, 4, 4, 0] } })),
          label: { show: true, position: "right", color: css("--text-secondary"), formatter: (p) => fmt(p.value, 0) },
        }],
      },
      true
    );
    graficos.fuentes.getDom().style.height = `${Math.max(220, lista.length * 38 + 40)}px`;
    graficos.fuentes.resize();

    $("tabla-fuentes").innerHTML = lista
      .map((g) => `<tr><td>${escapar(g.nombre)}</td><td>${g.alcance}</td><td class="num">${fmt(g.cantidad, 0)}</td>
        <td>${escapar(g.unidad)}</td><td class="num">${fmt(g.factor, 2)}</td><td class="num">${fmt(g.tco2e)}</td>
        <td class="num">${fmt((g.tco2e / total) * 100, 1)}%</td></tr>`)
      .join("");
  }

  // ---------- Carga de CSV del usuario ----------
  function parsearCSV(texto) {
    const lineas = texto.replace(/^﻿/, "").split(/\r?\n/).filter((l) => l.trim());
    const sep = (lineas[0].match(/;/g) || []).length > (lineas[0].match(/,/g) || []).length ? ";" : ",";
    const cab = lineas[0].split(sep).map((c) => c.trim().toLowerCase());
    const faltan = ["fecha", "sede", "fuente", "cantidad"].filter((c) => !cab.includes(c));
    if (faltan.length) throw new Error(`Faltan columnas: ${faltan.join(", ")}. Usa la plantilla.`);
    const idx = Object.fromEntries(cab.map((c, i) => [c, i]));
    return lineas.slice(1).map((l, n) => {
      const v = l.split(sep).map((x) => x.trim());
      const cantidadTexto = String(v[idx.cantidad] ?? "");
      const fila = {
        fecha: v[idx.fecha],
        sede: v[idx.sede],
        fuente: v[idx.fuente],
        // En CSV con ";" (Excel en español) la coma es separador decimal.
        cantidad: Number(sep === ";" ? cantidadTexto.replace(",", ".") : cantidadTexto),
      };
      if (!/^\d{4}-\d{2}$/.test(fila.fecha)) throw new Error(`Fila ${n + 2}: la fecha debe tener formato AAAA-MM.`);
      if (!factores[fila.fuente]) throw new Error(`Fila ${n + 2}: fuente desconocida "${fila.fuente}". Válidas: ${Object.keys(factores).join(", ")}.`);
      if (!Number.isFinite(fila.cantidad)) throw new Error(`Fila ${n + 2}: cantidad no numérica.`);
      return fila;
    });
  }

  function mostrarMensaje(texto, error = false) {
    const el = $("mensaje");
    el.textContent = texto;
    el.classList.toggle("error", error);
    el.classList.remove("oculto");
  }

  $("archivo").addEventListener("change", async (e) => {
    const archivo = e.target.files[0];
    if (!archivo) return;
    try {
      const consumos = parsearCSV(await archivo.text());
      cargarDatos(archivo.name.replace(/\.csv$/i, ""), consumos);
      mostrarMensaje(`Se cargaron ${consumos.length} registros. Los datos no salen de tu navegador.`);
      $("volver-demo").classList.remove("oculto");
    } catch (err) {
      mostrarMensaje(err.message, true);
    }
    e.target.value = "";
  });
  $("volver-demo").addEventListener("click", () => {
    cargarDatos(demo.empresa, demo.consumos);
    $("mensaje").classList.add("oculto");
    $("volver-demo").classList.add("oculto");
  });

  $("filtro-anio").addEventListener("change", (e) => { estado.anio = Number(e.target.value); render(); });
  $("filtro-sede").addEventListener("change", (e) => { estado.sede = e.target.value; render(); });
  alCambiarTema(render);

  cargarDatos(demo.empresa, demo.consumos);
})();
