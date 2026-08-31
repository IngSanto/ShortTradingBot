#!/usr/bin/env python3
"""Prueba de la teoria propia sobre el conjunto de DISEÑO.

La reserva no se toca aqui. Ver docs/04-teoria-propia.md, apartado 4.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from shortbot.data import load_csv  # noqa: E402
from shortbot.evaluation import evaluate_universe  # noqa: E402
from shortbot.markets import get_market  # noqa: E402
from shortbot.strategies import build  # noqa: E402

RAIZ = os.path.join(os.path.dirname(__file__), "..")


def cargar(conjunto: str) -> dict[str, pd.DataFrame]:
    split = json.load(open(os.path.join(RAIZ, "config", "holdout_split.json")))
    return {s: load_csv(os.path.join(RAIZ, "data", "cripto", f"{s}_1d.csv"))
            for s in split[conjunto]}


def fila(nombre_visible, est, uni, cfg):
    r = evaluate_universe(est, uni, None, cfg)
    return {"variante": nombre_visible, "n": r["trades"], "E[R]": r["expectancy_r"],
            "t": r["t_stat"], "acierto": r["win_rate"], "PF": r["profit_factor"],
            "activos+": r["assets_positive"], "barras": r["avg_bars"]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--conjunto", default="diseno", choices=["diseno", "reserva"])
    args = ap.parse_args()

    if args.conjunto == "reserva":
        print("\n*** RESERVA: esta medicion solo es valida UNA vez. ***\n")

    uni = cargar(args.conjunto)
    cfg = get_market("cripto").config()
    print(f"Conjunto {args.conjunto}: {len(uni)} activos, "
          f"{sum(len(d) for d in uni.values()):,} barras\n")

    filas = [
        fila("CBRC (completa)", build("cbrc_short"), uni, cfg),
        fila("CBRC sin veto de funding",
             build("cbrc_short", usar_veto_funding=False), uni, cfg),
        fila("CBRC sin filtro de estructura",
             build("cbrc_short", fast_ema=1, slow_ema=2), uni, cfg),
        fila("CBRC sin compresion",
             build("cbrc_short", width_pctile=1.0), uni, cfg),
        fila("[ref] squeeze_breakdown", build("squeeze_breakdown"), uni, cfg),
        fila("[ref] pullback_to_ema_short", build("pullback_to_ema_short"), uni, cfg),
    ]
    t = pd.DataFrame(filas)
    num = t.select_dtypes("number")
    t[num.columns] = num.round(3)
    print("=" * 96)
    print("TEORIA PROPIA - CBRC")
    print("=" * 96)
    print(t.to_string(index=False))

    c = t[t.variante == "CBRC (completa)"].iloc[0]
    sq = t[t.variante == "[ref] squeeze_breakdown"].iloc[0]
    sinf = t[t.variante == "CBRC sin veto de funding"].iloc[0]
    print("\nContraste con las predicciones declaradas:")
    print(f"  1. ¿CBRC bate a squeeze_breakdown?  {c['E[R]']:+.3f} vs {sq['E[R]']:+.3f}"
          f"  -> {'SI' if c['E[R]'] > sq['E[R]'] else 'NO'}")
    print(f"  2. ¿El veto de funding aporta?      {c['E[R]']:+.3f} vs {sinf['E[R]']:+.3f} sin el"
          f"  -> {'SI' if c['E[R]'] > sinf['E[R]'] else 'NO'}")
    print(f"  3. ¿Opera menos y mejor?            {int(c['n'])} ops vs {int(sq['n'])} de squeeze")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
