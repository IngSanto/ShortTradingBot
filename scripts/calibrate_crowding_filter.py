#!/usr/bin/env python3
"""Calibra el filtro de aglomeracion (docs/07-filtro-aglomeracion.md).

Corre la rejilla COMPLETA de {percentil} x {ventana} sobre las dos estrategias
aprobadas, en el conjunto de DISENO. Reporta todos los puntos, no el mejor:
un filtro de riesgo se adopta si una region amplia de la rejilla cumple el
criterio, no si un punto aislado se ve bien.

    python scripts/calibrate_crowding_filter.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

RAIZ = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(RAIZ, "src"))

from shortbot.backtest import ShortBacktester  # noqa: E402
from shortbot.data import load_csv  # noqa: E402
from shortbot.markets import get_market  # noqa: E402
from shortbot.risk_filters import aplicar_veto, veto_funding_crowding  # noqa: E402
from shortbot.strategies import build  # noqa: E402

PERCENTILES = [0.05, 0.10, 0.15, 0.20]
VENTANAS = [60, 90, 120]
ESTRATEGIAS = ["squeeze_breakdown", "pullback_to_ema_short"]

MIN_RETENCION = 0.70   # conserva al menos el 70% de las operaciones
MAX_CAIDA_ER = 0.15    # el E[R] no cae mas de un 15%


# Ultimo dia con cobertura real de funding en todo el universo (fin del ultimo
# mes archivado). Mas alla de esto el dato esta congelado -ver docs/07,
# seccion 4.1- y evaluar ahi seria juzgar el filtro donde no puede actuar.
CORTE_FUNDING = "2026-07-31"


def cargar_diseno(recortar_a_funding_valido: bool = True) -> dict[str, pd.DataFrame]:
    split = json.load(open(os.path.join(RAIZ, "config", "holdout_split.json")))
    universo = {s: load_csv(os.path.join(RAIZ, "data", "cripto", f"{s}_1d.csv"))
                for s in split["diseno"]}
    if recortar_a_funding_valido:
        universo = {s: df.loc[:CORTE_FUNDING] for s, df in universo.items()}
    return universo


def correr(nombre: str, universo: dict, cfg, percentil: float | None, ventana: int) -> dict:
    """Agrega los trades de todo el universo, con o sin veto aplicado."""
    trozos = []
    for df in universo.values():
        est = build(nombre)
        sig = est.generate_signals(df, None)
        if percentil is not None:
            veto = veto_funding_crowding(df, lookback=ventana, percentile=percentil)
            sig = aplicar_veto(sig, df, veto)
        res = ShortBacktester(cfg).run(df, sig)
        if not res.trades.empty:
            trozos.append(res.trades)
    if not trozos:
        return {"n": 0}
    t = pd.concat(trozos, ignore_index=True)
    r = t["r_multiple"].dropna()
    return {
        "n": len(t),
        "expectancy_r": float(r.mean()),
        "peor_r": float(r.min()),
        "gap_stop_pct": float((t["reason"] == "gap_stop").mean()),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--incluir-tramo-sin-funding", action="store_true",
                    help="No recortar al tramo con funding valido (reproduce "
                         "el resultado contaminado por el hueco de datos, "
                         "solo para comparar -ver docs/07 4.1)")
    args = ap.parse_args()

    universo = cargar_diseno(recortar_a_funding_valido=not args.incluir_tramo_sin_funding)
    if not args.incluir_tramo_sin_funding:
        print(f"Universo recortado a <= {CORTE_FUNDING} (limite real de cobertura de funding)")
    cfg = get_market("cripto").config()

    for nombre in ESTRATEGIAS:
        base = correr(nombre, universo, cfg, percentil=None, ventana=0)
        print(f"\n{'='*90}\n{nombre}  -- SIN FILTRO (referencia)\n{'='*90}")
        print(f"  n={base['n']}  E[R]={base['expectancy_r']:+.3f}  "
              f"peor={base['peor_r']:+.2f}  gap_stop={base['gap_stop_pct']:.1%}")

        filas = []
        for pct in PERCENTILES:
            for vent in VENTANAS:
                r = correr(nombre, universo, cfg, percentil=pct, ventana=vent)
                if r["n"] == 0:
                    continue
                retencion = r["n"] / base["n"]
                caida_er = (base["expectancy_r"] - r["expectancy_r"]) / abs(base["expectancy_r"])
                cumple = (retencion >= MIN_RETENCION and caida_er <= MAX_CAIDA_ER
                         and r["peor_r"] > base["peor_r"])
                filas.append({
                    "percentil": pct, "ventana": vent, "n": r["n"],
                    "retencion": retencion, "E[R]": r["expectancy_r"],
                    "caida_ER": caida_er, "peor_r": r["peor_r"],
                    "mejora_peor": r["peor_r"] - base["peor_r"],
                    "gap_stop": r["gap_stop_pct"], "cumple_criterio": cumple,
                })

        tabla = pd.DataFrame(filas)
        num = tabla.select_dtypes("number")
        tabla[num.columns] = num.round(3)
        print(f"\n  Rejilla completa (12 combinaciones):")
        print(tabla.to_string(index=False))

        n_cumple = int(tabla["cumple_criterio"].sum())
        print(f"\n  {n_cumple}/12 combinaciones cumplen el criterio "
              f"(retencion>={MIN_RETENCION:.0%}, caida E[R]<={MAX_CAIDA_ER:.0%}, mejora el peor trade)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
