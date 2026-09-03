#!/usr/bin/env python3
"""Cartera multi-mercado y bidireccional: las tres palancas de docs/11 a la vez.

`docs/11` dejo medido que el techo del sistema (18% anual) no viene de las
estrategias sino de la estructura: 40 activos de un solo mercado, con
correlacion 0,56, son 1,7 apuestas independientes, y el crecimiento maximo
alcanzable es S²/2 con S = 0,56.

Este script permite mover las tres variables que ese documento identifico:

  mercados     cripto, acciones, futuros -o los tres a la vez. Cada uno con su
               propio perfil de costes: mezclar comisiones de cripto con
               acciones daria un numero que no existe en ningun sitio.
  direccion    largo y corto en la misma cartera. No añade apuestas: añade un
               flujo que gana cuando el otro pierde, que es distinto y es
               justo lo que sube el Sharpe.
  estrategias  cualquier combinacion del registro.

El equity es UNO solo y compartido, como en `portfolio_backtest.py`, porque
esa es la unica forma de que el numero signifique algo. Se conducen las
reglas del motor de paper trading, no una copia.

    python scripts/portfolio_multi.py --mercados cripto
    python scripts/portfolio_multi.py --mercados cripto acciones futuros \\
        --estrategias pullback_to_ema_short pullback_to_ema_long
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

RAIZ = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(RAIZ, "src"))
sys.path.insert(0, os.path.dirname(__file__))

from shortbot.data import load_csv  # noqa: E402
from shortbot.markets import get_market  # noqa: E402
from shortbot.paper import EstadoPapel, PaperBroker  # noqa: E402
from shortbot.strategies import build  # noqa: E402

from portfolio_backtest import metricas  # noqa: E402

# La direccion es una propiedad de la estrategia, no del backtest. Se declara
# explicitamente en vez de deducirla del sufijo del nombre: un nombre es una
# convencion y esto decide el signo del P&L.
LARGAS = {"pullback_to_ema_long", "squeeze_breakout_long"}

CARPETA = {"cripto": "data/cripto/*_1d.csv",
           "acciones": "data/acciones/*.csv",
           "futuros": "data/futuros/*.csv",
           "diversificado": "data/diversificado/*.csv"}

# El universo diversificado son ETF cotizados en EEUU: usan el mismo perfil de
# costes que las acciones. Inventarle uno propio seria fingir precision.
PERFIL_COSTES = {"diversificado": "acciones"}


def cargar_mercado(mercado: str, conjunto: str, desde: str | None = None) -> dict[str, pd.DataFrame]:
    rutas = sorted(glob.glob(os.path.join(RAIZ, CARPETA[mercado])))
    activos = {}
    for r in rutas:
        s = os.path.basename(r).replace("_1d.csv", "").replace(".csv", "")
        d = load_csv(r)
        activos[s] = d.loc[desde:] if desde else d
    if mercado == "cripto" and conjunto != "todo":
        split = json.load(open(os.path.join(RAIZ, "config", "holdout_split.json")))
        activos = {s: d for s, d in activos.items() if s in set(split[conjunto])}
    return activos


def simular(mercados: list[str], estrategias: list[str], conjunto: str,
            riesgo: float, retraso: int, desde: str | None = None) -> tuple[EstadoPapel, dict]:
    trabajo, brokers, fechas = [], {}, pd.DatetimeIndex([])
    for mercado in mercados:
        cfg = get_market(PERFIL_COSTES.get(mercado, mercado)).config(risk_per_trade=riesgo, entry_delay_bars=retraso)
        brokers[mercado] = PaperBroker(cfg)
        for simbolo, df in cargar_mercado(mercado, conjunto, desde).items():
            fechas = fechas.union(df.index)
            for nombre in estrategias:
                sig = build(nombre).generate_signals(df, None)
                if not sig["entry"].any():
                    continue
                direccion = +1 if nombre in LARGAS else -1
                trabajo.append((f"{nombre}|{mercado}:{simbolo}", mercado, df, sig, direccion))

    estado = EstadoPapel(creado=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                         equity_inicial=100_000.0, equity=100_000.0)
    log: list[str] = []
    for ts in fechas:
        for clave, mercado, df, sig, direccion in trabajo:
            if ts not in df.index:
                continue
            i = df.index.get_loc(ts)
            b = brokers[mercado]
            b._entradas_pendientes(estado, clave, df, i, log)
            b._salidas(estado, clave, df, i, log)
            b._nuevas_senales(estado, clave, sig, df, i, log, direccion)
        estado.registrar_snapshot(str(ts))
    return estado, {"pares": len(trabajo), "fechas": len(fechas)}


def informe(titulo: str, m: dict, extra: dict | None = None) -> None:
    print(f"\n{titulo}")
    if extra:
        print(f"  {extra['pares']} pares (estrategia x activo), {extra['fechas']} fechas")
    print(f"  CAGR              {m['cagr']:+.1%}   (total {m['retorno_total']:+.1%} "
          f"en {m['años']:.1f} años)")
    print(f"  Max drawdown      {m['max_drawdown']:+.1%}")
    techo = (f"techo de Kelly {m['sharpe']**2/2:.1%} anual" if m["sharpe"] > 0
             else "sin techo que calcular: con Sharpe negativo no hay tamaño que salve la cartera")
    print(f"  Sharpe            {m['sharpe']:.2f}   -> {techo}")
    print(f"  Operaciones       {m['operaciones']:,} ({m['ops_por_año']:.0f}/año)  "
          f"E[R]={m['expectancy_r']:+.3f}  acierto={m['acierto']:.1%}")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--mercados", nargs="+", default=["cripto"],
                   choices=["cripto", "acciones", "futuros", "diversificado"])
    p.add_argument("--estrategias", nargs="+",
                   default=["pullback_to_ema_short", "squeeze_breakdown"])
    p.add_argument("--conjunto", choices=["diseno", "reserva", "todo"], default="todo")
    p.add_argument("--riesgo", type=float, default=0.01)
    p.add_argument("--retraso", type=int, default=0)
    p.add_argument("--desde", default=None,
                   help="recorta el histórico: sin esto, cripto (2020-) y acciones "
                        "(2010-) cubren periodos distintos y no son comparables")
    p.add_argument("--por-separado", action="store_true",
                   help="ademas de la cartera, cada estrategia en solitario")
    args = p.parse_args()

    largas = [e for e in args.estrategias if e in LARGAS]
    print(f"Mercados: {', '.join(args.mercados)} | riesgo {args.riesgo:.2%} | "
          f"retraso {args.retraso}\nEstrategias: {', '.join(args.estrategias)}"
          f"  ({len(largas)} largas, {len(args.estrategias)-len(largas)} cortas)")

    if args.por_separado:
        for e in args.estrategias:
            estado, extra = simular(args.mercados, [e], args.conjunto, args.riesgo,
                                    args.retraso, args.desde)
            informe(f"[solo] {e}", metricas(estado), extra)

    estado, extra = simular(args.mercados, args.estrategias, args.conjunto,
                            args.riesgo, args.retraso, args.desde)
    informe(f"[CARTERA] {len(args.estrategias)} estrategias x {len(args.mercados)} mercados",
            metricas(estado), extra)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
