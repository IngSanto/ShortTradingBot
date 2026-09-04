#!/usr/bin/env python3
"""Genera el dashboard estático del paper trading (docs/index.html).

Lee config/catalogo.json y state/paper.json y escribe una página HTML
autocontenida (sin CDN, sin JS de terceros) para publicar en GitHub Pages. El
workflow diario la ejecuta después de avanzar el paper trading, así que el
dashboard se actualiza solo, sin que nadie tenga que abrir Claude para verlo.

    python scripts/build_dashboard.py

Paleta y especificaciones de marcas tomadas de la skill dataviz (categórica
validada por CVD, hero figure, stat tiles, línea de una sola serie sin caja
de leyenda). Sin librerías: todo el gráfico es SVG inline generado a mano.
"""

from __future__ import annotations

import html
import json
import math
import os
import sys
from datetime import datetime, timezone

import pandas as pd

RAIZ = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(RAIZ, "src"))

from shortbot.paper import EstadoPapel, resumen  # noqa: E402

ESTADO_PATH = os.path.join(RAIZ, "state", "paper.json")
CATALOGO_PATH = os.path.join(RAIZ, "config", "catalogo.json")
SALIDA = os.path.join(RAIZ, "docs", "index.html")

MIN_OPERACIONES = 50
MIN_SESIONES = 60


def _f(x, nd=3, signo=False):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "—"
    fmt = f"{{:+.{nd}f}}" if signo else f"{{:.{nd}f}}"
    return fmt.format(x)


def _pct(x, nd=2, signo=True):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "—"
    fmt = f"{{:+.{nd}%}}" if signo else f"{{:.{nd}%}}"
    return fmt.format(x)


def _fecha_corta(iso: str) -> str:
    try:
        return pd.Timestamp(iso).strftime("%Y-%m-%d")
    except Exception:
        return iso[:10]


def stat_tile(label: str, value: str, sub: str = "", tono: str = "normal") -> str:
    clase = {"good": "tile-good", "bad": "tile-bad", "normal": ""}[tono]
    sub_html = f'<div class="tile-sub">{html.escape(sub)}</div>' if sub else ""
    return f"""
    <div class="tile {clase}">
      <div class="tile-label">{html.escape(label)}</div>
      <div class="tile-value">{html.escape(value)}</div>
      {sub_html}
    </div>"""


def _paso_agradable(rango: float) -> float:
    """El primer 1/2/5 x 10^n que da entre 3 y 6 escalones en el rango."""
    import math
    if rango <= 0:
        return 1.0
    crudo = rango / 4
    exp = 10 ** math.floor(math.log10(crudo))
    for m in (1, 2, 5, 10):
        if m * exp >= crudo:
            return m * exp
    return 10 * exp


def curva_equity_svg(historial: list[dict], equity_inicial: float) -> str:
    """Línea de una sola serie: sin caja de leyenda (el título ya la nombra)."""
    W, H, PAD_L, PAD_R, PAD_T, PAD_B = 720, 220, 56, 16, 16, 28
    if len(historial) < 2:
        return ('<div class="empty-chart">Aún no hay suficientes días para '
                'dibujar la curva. Vuelve cuando haya al menos 2 sesiones.</div>')

    # `equity_mercado` incluye el valor de lo que sigue abierto; `equity` solo
    # lo cobrado. Mirar la segunda es como leer el saldo del banco ignorando lo
    # que tienes invertido: no se mueve en dias con 20 posiciones vivas.
    # Se usa la primera cuando existe (estados anteriores no la tienen).
    def _valor(p):
        return p.get("equity_mercado", p["equity"])

    valores = [_valor(p) for p in historial]
    lo, hi = min(valores + [equity_inicial]), max(valores + [equity_inicial])
    margen = max((hi - lo) * 0.1, hi * 0.01, 1.0)
    lo, hi = lo - margen, hi + margen

    def x_de(i):
        return PAD_L + (W - PAD_L - PAD_R) * (i / (len(historial) - 1))

    def y_de(v):
        return PAD_T + (H - PAD_T - PAD_B) * (1 - (v - lo) / (hi - lo))

    puntos = [(x_de(i), y_de(_valor(p))) for i, p in enumerate(historial)]
    linea = " ".join(f"{x:.1f},{y:.1f}" for x, y in puntos)
    area = f"{PAD_L:.1f},{y_de(lo):.1f} " + linea + f" {puntos[-1][0]:.1f},{y_de(lo):.1f}"
    y_base = y_de(equity_inicial)

    # Solo se etiquetan el inicio, el final y el eje: nunca un valor por punto.
    ultimo = historial[-1]
    fin_x, fin_y = puntos[-1]
    etiqueta_fin = f"{_valor(ultimo):,.0f}"

    # Ticks en numeros redondos (0/500/1.000...), no en los limites exactos
    # calculados: un eje con "106.909" no se lee de un vistazo.
    paso = _paso_agradable(hi - lo)
    primer_tick = math.ceil(lo / paso) * paso
    ticks = ""
    v = primer_tick
    while v <= hi:
        y = y_de(v)
        ticks += (f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{W-PAD_R}" y2="{y:.1f}" '
                  f'class="grid"/>'
                  f'<text x="{PAD_L-8}" y="{y+4:.1f}" class="axis-label" '
                  f'text-anchor="end">{v:,.0f}</text>')
        v += paso

    return f"""
    <svg viewBox="0 0 {W} {H}" class="equity-chart" role="img"
         aria-label="Curva de equity del paper trading">
      {ticks}
      <line x1="{PAD_L}" y1="{y_base:.1f}" x2="{W-PAD_R}" y2="{y_base:.1f}"
            class="baseline-inicial"/>
      <polygon points="{area}" class="area-fill"/>
      <polyline points="{linea}" class="line-main"/>
      <circle cx="{fin_x:.1f}" cy="{fin_y:.1f}" r="4.5" class="end-dot"/>
      <text x="{fin_x-6:.1f}" y="{fin_y-10:.1f}" class="end-label"
            text-anchor="end">{etiqueta_fin}</text>
    </svg>"""


def fila_operacion(op: dict) -> str:
    ganadora = op["pnl"] > 0
    tono = "good" if ganadora else "bad"
    signo_r = _f(op.get("r_multiple"), 2, signo=True)
    icono = "▲" if ganadora else "▼"
    return f"""
      <tr>
        <td>{_fecha_corta(op['fecha_salida'])}</td>
        <td class="mono">{html.escape(op['simbolo'])}</td>
        <td>{html.escape(op['estrategia'])}</td>
        <td>{html.escape(op['motivo'])}</td>
        <td class="num">{op['barras']}</td>
        <td class="num badge-{tono}">{icono} {signo_r} R</td>
      </tr>"""


def fila_abierta(op: dict) -> str:
    return f"""
      <tr>
        <td>{_fecha_corta(op['fecha_entrada'])}</td>
        <td class="mono">{html.escape(op['simbolo'])}</td>
        <td>{html.escape(op['estrategia'])}</td>
        <td class="num">{op['precio_entrada']:.4f}</td>
        <td class="num">{op['stop']:.4f}</td>
        <td class="num">{op['barras']}/{op['max_barras']}</td>
      </tr>"""


def fila_pendiente(p: dict) -> str:
    return f"""
      <tr>
        <td>{_fecha_corta(p['fecha_senal'])}</td>
        <td class="mono">{html.escape(p['simbolo'])}</td>
        <td>{html.escape(p['estrategia'])}</td>
        <td>stop {p['stop_atr']}×ATR / obj {p['target_atr']}×ATR</td>
      </tr>"""


def main() -> int:
    catalogo = json.load(open(CATALOGO_PATH))
    estado = EstadoPapel.cargar(ESTADO_PATH)
    r = resumen(estado)

    dias_corriendo = max(1, (datetime.now(timezone.utc)
                             - datetime.fromisoformat(estado.creado)).days)
    prog_ops = min(1.0, r["operaciones"] / MIN_OPERACIONES)
    prog_dias = min(1.0, dias_corriendo / MIN_SESIONES)
    listo_puerta4 = r["operaciones"] >= MIN_OPERACIONES or dias_corriendo >= MIN_SESIONES

    aprobadas = {e["id"]: e for e in catalogo["aprobadas_para_paper"]}
    ops = pd.DataFrame(estado.cerradas)
    contraste_html = ""
    if not ops.empty:
        filas = []
        for est_id, g in ops.groupby("estrategia"):
            ev = aprobadas.get(est_id, {}).get("evidencia", {})
            esperado = ev.get("retraso_1_barra", {}).get("expectancy_r", ev.get("expectancy_r"))
            real = float(g["r_multiple"].mean())
            n = len(g)
            if n < 20:
                estado_txt, tono = f"muestra corta (n={n})", ""
            elif esperado is None:
                estado_txt, tono = "sin referencia", ""
            elif real >= 0.5 * esperado:
                estado_txt, tono = "dentro de lo esperado", "good"
            else:
                estado_txt, tono = "por debajo de lo esperado", "bad"
            filas.append(f"""
            <tr>
              <td>{html.escape(est_id)}</td>
              <td class="num">{n}</td>
              <td class="num">{_f(real, 3, signo=True)} R</td>
              <td class="num">{_f(esperado, 3, signo=True) if esperado is not None else '—'} R</td>
              <td class="badge-{tono}">{estado_txt}</td>
            </tr>""")
        contraste_html = f"""
        <table class="tabla">
          <thead><tr><th>Estrategia</th><th class="num">n</th><th class="num">E[R] real</th>
          <th class="num">E[R] esperado*</th><th>Estado</th></tr></thead>
          <tbody>{"".join(filas)}</tbody>
        </table>
        <p class="caption">* del backtest, con el mismo retraso de ejecución (1 barra) que usa el paper.</p>"""
    else:
        contraste_html = ('<p class="muted">Sin operaciones cerradas todavía: '
                          'nada que contrastar contra el backtest.</p>')

    recientes = sorted(estado.cerradas, key=lambda o: o["fecha_salida"], reverse=True)[:25]
    bitacora_cerradas = ("".join(fila_operacion(o) for o in recientes) if recientes
                         else '<tr><td colspan="6" class="muted">Sin operaciones cerradas todavía.</td></tr>')
    bitacora_abiertas = ("".join(fila_abierta(o) for o in estado.abiertas) if estado.abiertas
                         else '<tr><td colspan="6" class="muted">Ninguna posición abierta ahora mismo.</td></tr>')
    bitacora_pendientes = ("".join(fila_pendiente(p) for p in estado.pendientes) if estado.pendientes
                           else '<tr><td colspan="4" class="muted">Ninguna señal a la espera de ejecutarse.</td></tr>')

    tiles = "".join([
        stat_tile("Equity", f"${r['equity']:,.0f}", _pct(r["retorno"]),
                  "good" if r["retorno"] > 0 else ("bad" if r["retorno"] < 0 else "normal")),
        stat_tile("Operaciones cerradas", f"{r['operaciones']}",
                  f"objetivo: {MIN_OPERACIONES}"),
        stat_tile("Expectativa", f"{_f(r.get('expectancy_r'), 3, signo=True)} R",
                  "por operación" if r["operaciones"] else "aún sin datos",
                  "good" if r.get("expectancy_r", 0) and r["expectancy_r"] > 0 else "normal"),
        stat_tile("Acierto", _pct(r.get("acierto"), 1, signo=False) if r["operaciones"] else "—",
                  f"profit factor {_f(r.get('profit_factor'), 2)}" if r["operaciones"] else ""),
        stat_tile("Peor operación", f"{_f(r.get('peor_r'), 2, signo=True)} R" if r["operaciones"] else "—"),
        stat_tile("Posiciones abiertas", f"{r['abiertas']}", f"{r['pendientes']} señal(es) pendiente(s)"),
        stat_tile("Días corriendo", f"{dias_corriendo}",
                  f"desde {_fecha_corta(estado.creado)}"),
        stat_tile("Progreso puerta 4", f"{max(prog_ops, prog_dias):.0%}",
                  "lista para decidir" if listo_puerta4 else "en curso",
                  "good" if listo_puerta4 else "normal"),
    ])

    generado = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    mercados_aprobados = ", ".join(sorted({e["mercado"] for e in catalogo["aprobadas_para_paper"]}))

    html_out = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ShortTradingBot — Paper trading</title>
<style>
  :root {{
    color-scheme: light;
    --surface-1:  #fcfcfb;
    --page:       #f9f9f7;
    --text-1:     #0b0b0b;
    --text-2:     #52514e;
    --muted:      #898781;
    --grid:       #e1e0d9;
    --baseline:   #c3c2b7;
    --border:     rgba(11,11,11,0.10);
    --blue:       #2a78d6;
    --good-text:  #006300;
    --good-bg:    #e6f4e6;
    --bad-text:   #b3221f;
    --bad-bg:     #fbe9e8;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      color-scheme: dark;
      --surface-1:  #1a1a19;
      --page:       #0d0d0d;
      --text-1:     #ffffff;
      --text-2:     #c3c2b7;
      --muted:      #898781;
      --grid:       #2c2c2a;
      --baseline:   #383835;
      --border:     rgba(255,255,255,0.10);
      --blue:       #3987e5;
      --good-text:  #0ca30c;
      --good-bg:    #123312;
      --bad-text:   #e66767;
      --bad-bg:     #3a1a19;
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; background: var(--page); color: var(--text-1);
    font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif;
  }}
  .wrap {{ max-width: 1040px; margin: 0 auto; padding: 28px 20px 64px; }}
  header {{ margin-bottom: 24px; }}
  h1 {{ font-size: 22px; margin: 0 0 4px; }}
  .subtitle {{ color: var(--text-2); font-size: 14px; }}
  .badge-mercado {{
    display: inline-block; padding: 2px 9px; border-radius: 999px;
    background: var(--surface-1); border: 1px solid var(--border);
    font-size: 12px; color: var(--text-2); margin-left: 8px;
  }}
  .updated {{ color: var(--muted); font-size: 12.5px; margin-top: 6px; }}
  h2 {{ font-size: 16px; margin: 32px 0 12px; }}
  .card {{
    background: var(--surface-1); border: 1px solid var(--border);
    border-radius: 10px; padding: 18px;
  }}
  .tiles {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }}
  @media (max-width: 720px) {{ .tiles {{ grid-template-columns: repeat(2, 1fr); }} }}
  .tile {{
    background: var(--surface-1); border: 1px solid var(--border);
    border-radius: 10px; padding: 14px 16px;
  }}
  .tile-label {{ font-size: 12.5px; color: var(--text-2); }}
  .tile-value {{ font-size: 24px; font-weight: 600; margin-top: 2px; }}
  .tile-sub {{ font-size: 12px; color: var(--muted); margin-top: 2px; }}
  .tile-good .tile-value {{ color: var(--good-text); }}
  .tile-bad .tile-value {{ color: var(--bad-text); }}
  .equity-chart {{ width: 100%; height: auto; }}
  .grid {{ stroke: var(--grid); stroke-width: 1; }}
  .baseline-inicial {{ stroke: var(--baseline); stroke-width: 1; stroke-dasharray: 3 3; }}
  .axis-label {{ font-size: 10px; fill: var(--muted); font-family: system-ui, sans-serif; }}
  .area-fill {{ fill: var(--blue); opacity: 0.10; stroke: none; }}
  .line-main {{ fill: none; stroke: var(--blue); stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }}
  .end-dot {{ fill: var(--blue); stroke: var(--surface-1); stroke-width: 2; }}
  .end-label {{ font-size: 12px; fill: var(--text-1); font-weight: 600; font-family: system-ui, sans-serif; }}
  .empty-chart {{ color: var(--muted); font-size: 13.5px; padding: 40px 0; text-align: center; }}
  table.tabla {{ width: 100%; border-collapse: collapse; font-size: 13.5px; }}
  table.tabla th {{
    text-align: left; font-weight: 600; color: var(--text-2);
    font-size: 12px; text-transform: uppercase; letter-spacing: .02em;
    padding: 6px 10px; border-bottom: 1px solid var(--border);
  }}
  table.tabla td {{ padding: 7px 10px; border-bottom: 1px solid var(--grid); }}
  table.tabla tr:last-child td {{ border-bottom: none; }}
  td.num, th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  td.mono {{ font-family: ui-monospace, "SF Mono", monospace; font-size: 13px; }}
  .muted {{ color: var(--muted); }}
  .caption {{ color: var(--muted); font-size: 12px; margin: 6px 2px 0; }}
  .badge-good, .badge-bad {{
    display: inline-block; padding: 1px 8px; border-radius: 999px; font-size: 12.5px;
    font-variant-numeric: tabular-nums;
  }}
  .badge-good {{ color: var(--good-text); background: var(--good-bg); }}
  .badge-bad {{ color: var(--bad-text); background: var(--bad-bg); }}
  .table-scroll {{ overflow-x: auto; }}
  footer {{ margin-top: 40px; color: var(--muted); font-size: 12.5px; line-height: 1.6; }}
  footer a {{ color: var(--text-2); }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>ShortTradingBot — Paper trading
      <span class="badge-mercado">{html.escape(mercados_aprobados)}</span>
    </h1>
    <div class="subtitle">Puerta 4 de la validación: papel, sin dinero real, mínimo {MIN_OPERACIONES} operaciones o {MIN_SESIONES} sesiones.</div>
    <div class="updated">Última actualización: {generado} · generado automáticamente, sin intervención de Claude</div>
  </header>

  <section class="tiles">{tiles}</section>

  <h2>Curva de equity</h2>
  <div class="card">
    {curva_equity_svg(estado.historial, estado.equity_inicial)}
  </div>

  <h2>Paper vs. lo que prometía el backtest</h2>
  <div class="card table-scroll">{contraste_html}</div>

  <h2>Bitácora — operaciones cerradas recientes</h2>
  <div class="card table-scroll">
    <table class="tabla">
      <thead><tr><th>Salida</th><th>Activo</th><th>Estrategia</th><th>Motivo</th><th class="num">Barras</th><th class="num">Resultado</th></tr></thead>
      <tbody>{bitacora_cerradas}</tbody>
    </table>
  </div>

  <h2>Posiciones abiertas ahora</h2>
  <div class="card table-scroll">
    <table class="tabla">
      <thead><tr><th>Entrada</th><th>Activo</th><th>Estrategia</th><th class="num">Precio entrada</th><th class="num">Stop</th><th class="num">Barras</th></tr></thead>
      <tbody>{bitacora_abiertas}</tbody>
    </table>
  </div>

  <h2>Señales pendientes de ejecutar</h2>
  <div class="card table-scroll">
    <table class="tabla">
      <thead><tr><th>Señal</th><th>Activo</th><th>Estrategia</th><th>Parámetros de riesgo</th></tr></thead>
      <tbody>{bitacora_pendientes}</tbody>
    </table>
  </div>

  <footer>
    Dinero simulado. Nada en esta página es asesoramiento financiero.
    Metodología completa en <a href="https://github.com/IngSanto/ShortTradingBot/blob/main/docs/02-metodologia-validacion.md">docs/02-metodologia-validacion.md</a>
    y el catálogo de estrategias en <a href="https://github.com/IngSanto/ShortTradingBot/blob/main/config/catalogo.json">config/catalogo.json</a>.
  </footer>
</div>
</body>
</html>
"""

    os.makedirs(os.path.dirname(SALIDA), exist_ok=True)
    open(SALIDA, "w").write(html_out)
    print(f"Dashboard escrito en {os.path.relpath(SALIDA, RAIZ)} "
          f"({len(html_out):,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
