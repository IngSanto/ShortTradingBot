#!/usr/bin/env python3
"""Cuanto pesa el mercado, con la estrategia constante.

Ejecuta el MISMO universo de precios y las MISMAS senales bajo los tres
perfiles de mercado. Como los precios no cambian, toda la diferencia de
expectativa es atribuible a costes y carry.

Es la forma de responder a "empezar por los tres" con un numero en lugar de
con una intuicion: cuantifica la ventaja estructural de cada mercado para el
lado corto, antes de tener datos reales.
"""

from __future__ import annotations

import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from shortbot.data import synthetic_ohlcv, synthetic_perp_universe  # noqa: E402
from shortbot.evaluation import evaluate_universe  # noqa: E402
from shortbot.markets import MERCADOS  # noqa: E402
from shortbot.strategies import build_all  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--assets", type=int, default=10)
    ap.add_argument("--bars", type=int, default=2500)
    ap.add_argument("--risk", type=float, default=0.01)
    args = ap.parse_args()

    # Un unico universo para los tres mercados: la unica variable es el perfil.
    universe = synthetic_perp_universe(args.assets, n=args.bars)
    benchmark = synthetic_ohlcv(n=args.bars, seed=999)["close"]

    rows = []
    for strategy in build_all():
        row = {"estrategia": strategy.name}
        trades = None
        for key, profile in MERCADOS.items():
            res = evaluate_universe(strategy, universe, benchmark,
                                    profile.config(risk_per_trade=args.risk))
            row[key] = res["expectancy_r"]
            trades = res["trades"]
        row["trades"] = trades
        rows.append(row)

    table = pd.DataFrame(rows)
    table["ventaja_cripto"] = table["cripto"] - table["acciones"]
    table = table[table["trades"] >= 30].sort_values("ventaja_cripto", ascending=False)

    print("\n" + "=" * 88)
    print("EXPECTATIVA (R) DE LA MISMA ESTRATEGIA SOBRE LOS MISMOS PRECIOS")
    print("Solo cambia el perfil de mercado: comisiones, slippage y carry.")
    print("=" * 88)
    print(table.round(3).to_string(index=False))

    diff = table["ventaja_cripto"]
    print(f"\nVentaja media de cripto sobre acciones: {diff.mean():+.3f} R por operacion")
    print(f"Rango: {diff.min():+.3f} R a {diff.max():+.3f} R")
    print("\nEl motivo es unicamente el carry: en acciones el corto paga el prestamo;")
    print("en perpetuos con funding positivo, lo cobra. La diferencia crece de forma")
    print("lineal con el tiempo en mercado, asi que castiga sobre todo a las")
    print("estrategias de tendencia, que son las que mas dias aguantan la posicion.")
    print("\nOJO: precios sinteticos. Lo que mide esto es el efecto del CARRY,")
    print("que es deterministico dado el tiempo en mercado, no un edge de precio.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
