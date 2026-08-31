#!/usr/bin/env python3
"""Dependencia del regimen: cuanto del resultado viene de que el mercado caiga.

Un sistema corto que solo gana en mercado bajista es un **seguro**, no alfa.
Es legitimo, pero se dimensiona distinto y se comunica distinto. Esta prueba
separa una cosa de la otra.

    python scripts/regime_test.py --data "data/cripto/*_1d.csv"

AVISO METODOLOGICO, aprendido a base de equivocarse: NO se puede trocear la
serie por periodos y ejecutar la estrategia en cada trozo. Cada trozo empieza
sin historia, asi que una EMA(200) no genera ninguna señal hasta 200 barras
despues, y el recuento sale disparatado (en una prueba real, un año con 241
operaciones aparecia con 1). Lo correcto es ejecutar sobre la serie COMPLETA y
despues etiquetar cada operacion por el regimen que habia el dia de entrada.
"""

from __future__ import annotations

import argparse
import glob
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from shortbot import indicators as ind  # noqa: E402
from shortbot.data import load_csv  # noqa: E402
from shortbot.evaluation import run_strategy  # noqa: E402
from shortbot.markets import get_market  # noqa: E402
from shortbot.strategies import STRATEGY_REGISTRY, build  # noqa: E402


def t_stat(s: pd.Series) -> float:
    if len(s) < 2 or s.std(ddof=1) == 0:
        return float("nan")
    return float(s.mean() / (s.std(ddof=1) / np.sqrt(len(s))))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", nargs="+", required=True)
    ap.add_argument("--market", default="cripto")
    ap.add_argument("--reference", default="BTCUSDT", help="Activo que define el regimen")
    ap.add_argument("--sma", type=int, default=200)
    ap.add_argument("--strategies", nargs="*", default=None)
    args = ap.parse_args()

    uni = {}
    for patron in args.data:
        for p in sorted(glob.glob(patron)):
            uni[os.path.basename(p).split("_")[0]] = load_csv(p)
    if args.reference not in uni:
        raise SystemExit(f"Falta el activo de referencia {args.reference}")

    cfg = get_market(args.market).config()
    ref = uni[args.reference]["close"]
    regimen = (ref > ind.sma(ref, args.sma)).map({True: "alcista", False: "bajista"})
    print(f"\nRegimen definido por {args.reference} frente a su SMA({args.sma}): "
          f"{regimen.value_counts().to_dict()}\n")

    nombres = args.strategies or list(STRATEGY_REGISTRY)
    filas = []
    for nombre in nombres:
        trozos = []
        for d in uni.values():
            # Serie COMPLETA: nunca trocear antes de ejecutar.
            r = run_strategy(build(nombre), d, None, cfg)
            if not r.trades.empty:
                t = r.trades.copy()
                t["regimen"] = regimen.reindex(t["entry_date"]).to_numpy()
                trozos.append(t[["regimen", "r_multiple"]])
        if not trozos:
            continue
        allt = pd.concat(trozos, ignore_index=True).dropna(subset=["regimen"])
        alc = allt[allt.regimen == "alcista"]["r_multiple"]
        baj = allt[allt.regimen == "bajista"]["r_multiple"]
        if len(alc) < 20 or len(baj) < 20:
            continue
        filas.append({
            "estrategia": nombre,
            "n alcista": len(alc), "E[R] alcista": alc.mean(), "t alcista": t_stat(alc),
            "n bajista": len(baj), "E[R] bajista": baj.mean(), "t bajista": t_stat(baj),
            "dependencia": baj.mean() - alc.mean(),
        })

    tabla = pd.DataFrame(filas).sort_values("E[R] alcista", ascending=False)
    num = tabla.select_dtypes("number")
    tabla[num.columns] = num.round(3)
    print("=" * 108)
    print("DEPENDENCIA DEL REGIMEN")
    print("=" * 108)
    print(tabla.to_string(index=False))

    print("\nLectura:")
    print("  E[R] alcista > 0 con t > 2  -> hay alfa, no solo cobertura.")
    print("  Solo positiva en bajista    -> es un seguro: dimensionar como tal.")
    print("  'dependencia' alta          -> el resultado depende de que el mercado caiga.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
