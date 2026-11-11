// Utilidades compartidas: tema claro/oscuro, formato es-CL y estilo base de ECharts.

const Comun = (() => {
  const CLAVE_TEMA = "tema";

  function leerTemaGuardado() {
    try { return localStorage.getItem(CLAVE_TEMA); } catch { return null; }
  }
  function temaEfectivo() {
    const forzado = document.documentElement.dataset.theme;
    if (forzado) return forzado;
    return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  const guardado = leerTemaGuardado();
  if (guardado) document.documentElement.dataset.theme = guardado;

  const oyentesTema = [];
  function alCambiarTema(fn) { oyentesTema.push(fn); }
  function notificarTema() { oyentesTema.forEach((fn) => fn()); }
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", notificarTema);

  document.addEventListener("DOMContentLoaded", () => {
    const boton = document.querySelector(".boton-tema");
    if (!boton) return;
    const pintar = () => { boton.textContent = temaEfectivo() === "dark" ? "Modo claro" : "Modo oscuro"; };
    pintar();
    boton.addEventListener("click", () => {
      const nuevo = temaEfectivo() === "dark" ? "light" : "dark";
      document.documentElement.dataset.theme = nuevo;
      try { localStorage.setItem(CLAVE_TEMA, nuevo); } catch { /* sin almacenamiento */ }
      pintar();
      notificarTema();
    });
  });

  const css = (nombre) => getComputedStyle(document.documentElement).getPropertyValue(nombre).trim();

  const fmt = (v, dec = 1) =>
    Number(v).toLocaleString("es-CL", { minimumFractionDigits: dec, maximumFractionDigits: dec });
  const fmtPct = (v) => `${v > 0 ? "+" : ""}${fmt(v * 100, 1)}%`;

  // Opciones base para cualquier gráfico: grilla tenue, ejes recesivos, tooltip legible.
  function base() {
    const ejeTexto = { color: css("--axis-muted"), fontSize: 12 };
    return {
      textStyle: { fontFamily: 'system-ui, -apple-system, "Segoe UI", sans-serif', color: css("--text-secondary") },
      grid: { left: 8, right: 16, top: 16, bottom: 8, containLabel: true },
      tooltip: {
        backgroundColor: css("--surface"),
        borderColor: css("--border"),
        textStyle: { color: css("--text-primary"), fontSize: 13 },
        extraCssText: "box-shadow: 0 4px 16px rgba(0,0,0,.12); border-radius: 8px;",
      },
      ejeCategoria: {
        axisLine: { lineStyle: { color: css("--baseline") } },
        axisTick: { show: false },
        axisLabel: ejeTexto,
      },
      ejeValor: {
        splitLine: { lineStyle: { color: css("--grid") } },
        axisLabel: { ...ejeTexto, formatter: (v) => fmt(v, 0) },
      },
    };
  }

  function grafico(id) {
    const el = document.getElementById(id);
    const chart = echarts.init(el, null, { renderer: "svg" });
    new ResizeObserver(() => chart.resize()).observe(el);
    return chart;
  }

  const escapar = (s) =>
    String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

  return { css, fmt, fmtPct, base, grafico, alCambiarTema, escapar };
})();
