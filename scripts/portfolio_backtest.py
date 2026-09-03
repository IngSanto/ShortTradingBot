#!/usr/bin/env python3
"""Rendimiento anual REAL de la cartera. Lo que E[R] por operacion no dice.

Hasta ahora todo el catalogo se ha medido en expectativa por operacion, y de
ahi no sale un rendimiento anual: hacen falta tres cosas mas que solo existen
a nivel de cartera -cuantas operaciones caben en un año, que varias posiciones
comparten el mismo capital, y que el tamaño de cada una depende del equity que
haya en ese momento (o sea, compone).

Multiplicar E[R] por operaciones al año, que es como se estimo antes, ignora
las tres. Aqui se simula la cartera entera dia a dia.

**No se reimplementan las reglas.** Se conducen las del motor de paper
trading (`PaperBroker`), que ya son identicas a las del backtest, pero
recorriendo las fechas en orden cronologico y cruzando todos los activos, en
vez de un activo entero y luego el siguiente. Esa es justo la diferencia que
convierte N backtests independientes en una cartera: el equity es uno solo y
se actualiza en el orden en que pasaron las cosas.

    python scripts/portfolio_backtest.py --conjunto diseno
    python scripts/portfolio_backtest.py --filtro-eventos --riesgo 0.01
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import replace
from datetime import datetime, timezone

import numpy as np
import pandas as pd

RAIZ = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(RAIZ, "src"))

from shortbot.data import load_csv  # noqa: E402
from shortbot.markets import get_market  # noqa: E402
from shortbot.paper import EstadoPapel, PaperBroker  # noqa: E402
from shortbot.risk_filters import aplicar_veto, veto_evento_macro  # noqa: E402
from shortbot.strategies import build  # noqa: E402

CALENDARIO = os.path.join(RAIZ, "data", "eventos", "calendario_macro.csv")
VENTANA_ADOPTADA = (1, 0)  # V1 {T-1, T} -- docs/10, seccion 5.5


def cargar(conjunto: str) -> dict[str, pd.DataFrame]:
    split = json.load(open(os.path.join(RAIZ, "config", "holdout_split.json")))
    simbolos = split["diseno"] + split["reserva"] if conjunto == "todo" else split[conjunto]
    return {s: load_csv(os.path.join(RAIZ, "data", "cripto", f"{s}_1d.csv")) for s in simbolos}


def simular(universo: dict, estrategias: list[str], cfg, filtro_eventos: bool) -> EstadoPapel:
    """Recorre las fechas en orden y avanza todos los activos en cada una."""
    fechas = pd.DatetimeIndex([])
    for df in universo.values():
        fechas = fechas.union(df.index)

    veto_fechas = list(pd.read_csv(CALENDARIO)["fecha"]) if filtro_eventos else None

    trabajo = []
    for nombre in estrategias:
        for simbolo, df in universo.items():
            sig = build(nombre).generate_signals(df, None)
            if filtro_eventos:
                veto = veto_evento_macro(df.index, veto_fechas, *VENTANA_ADOPTADA,
                                         retraso_entrada=cfg.entry_delay_bars)
                sig = aplicar_veto(sig, df, veto)
            trabajo.append((f"{nombre}|{simbolo}", df, sig))

    estado = EstadoPapel(creado=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                         equity_inicial=cfg.initial_equity, equity=cfg.initial_equity)
    broker = PaperBroker(cfg)
    log: list[str] = []

    for ts in fechas:
        for clave, df, sig in trabajo:
            if ts not in df.index:
                continue
            i = df.index.get_loc(ts)
            # Mismo orden intrabarra que paper.py: entradas pendientes, luego
            # salidas, luego señales nuevas. Cambiarlo permitiria cerrar y
            # reabrir en la misma barra, que el backtest no permite.
            broker._entradas_pendientes(estado, clave, df, i, log)
            broker._salidas(estado, clave, df, i, log)
            broker._nuevas_senales(estado, clave, sig, df, i, log)
        estado.registrar_snapshot(str(ts))
    return estado


def metricas(estado: EstadoPapel) -> dict:
    hist = pd.DataFrame(estado.historial)
    hist["fecha"] = pd.to_datetime(hist["fecha"])
    equity = hist.set_index("fecha")["equity"]

    años = (equity.index[-1] - equity.index[0]).days / 365.25
    total = equity.iloc[-1] / equity.iloc[0] - 1
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1 / años) - 1

    pico = equity.cummax()
    dd = (equity - pico) / pico
    ops = pd.DataFrame(estado.cerradas)
    r = ops["r_multiple"].dropna() if not ops.empty else pd.Series(dtype=float)

    # Sharpe sobre retornos diarios del equity, anualizado a 365 (cripto opera
    # todos los dias, no 252).
    diario = equity.pct_change().dropna()
    sharpe = (diario.mean() / diario.std() * np.sqrt(365)) if diario.std() > 0 else float("nan")

    return {
        "años": años, "equity_final": equity.iloc[-1], "retorno_total": total,
        "cagr": cagr, "max_drawdown": dd.min(), "sharpe": sharpe,
        "operaciones": len(ops), "ops_por_año": len(ops) / años,
        "expectancy_r": r.mean() if len(r) else float("nan"),
        "acierto": (ops["pnl"] > 0).mean() if not ops.empty else float("nan"),
        "equity": equity,
    }


def informe(nombre: str, m: dict) -> None:
    print(f"\n{nombre}")
    print(f"  CAGR              {m['cagr']:+.1%}      (retorno total {m['retorno_total']:+.1%} "
          f"en {m['años']:.1f} años)")
    print(f"  Max drawdown      {m['max_drawdown']:+.1%}")
    print(f"  Sharpe            {m['sharpe']:.2f}")
    print(f"  Operaciones       {m['operaciones']:,} ({m['ops_por_año']:.0f}/año)  "
          f"E[R]={m['expectancy_r']:+.3f}  acierto={m['acierto']:.1%}")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--conjunto", choices=["diseno", "reserva", "todo"], default="diseno")
    p.add_argument("--riesgo", type=float, default=0.01)
    p.add_argument("--retraso", type=int, default=0)
    p.add_argument("--filtro-eventos", action="store_true")
    p.add_argument("--estrategias", nargs="+",
                   default=["pullback_to_ema_short", "squeeze_breakdown"])
    args = p.parse_args()

    universo = cargar(args.conjunto)
    cfg = get_market("cripto").config(risk_per_trade=args.riesgo,
                                      entry_delay_bars=args.retraso)
    print(f"Cartera: {len(universo)} activos | riesgo {args.riesgo:.2%}/operacion | "
          f"retraso {args.retraso} | filtro de eventos: {'SI' if args.filtro_eventos else 'no'}")

    for estrategia in args.estrategias:
        m = metricas(simular(universo, [estrategia], cfg, args.filtro_eventos))
        informe(f"[solo] {estrategia}", m)

    if len(args.estrategias) > 1:
        m = metricas(simular(universo, args.estrategias, cfg, args.filtro_eventos))
        informe(f"[CARTERA] {' + '.join(args.estrategias)}", m)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
