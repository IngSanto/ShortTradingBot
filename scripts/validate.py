#!/usr/bin/env python3
"""Ejecuta las puertas de validacion sobre un universo real y da un veredicto.

    python scripts/validate.py --market cripto --data "data/cripto/*_1d.csv"

Aplica, en orden, las puertas de docs/02-metodologia-validacion.md:

  Puerta 1  Criba          muestra suficiente y expectativa positiva sin costes
  Puerta 2  Robustez       meseta de parametros, consistencia entre activos, t>2
  Puerta 2.5 Temporalidad  el edge debe sobrevivir al cambio de barra
  Puerta 3  Fuera muestra  el ultimo 20% del historico, nunca usado para decidir

Una estrategia solo avanza si supera TODAS las anteriores. El objetivo del
script no es encontrar ganadoras: es descartar barato.
"""

from __future__ import annotations

import argparse
import glob
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from shortbot.backtest import BacktestConfig, CostModel  # noqa: E402
from shortbot.data import load_csv  # noqa: E402
from shortbot.evaluation import (  # noqa: E402
    evaluate_universe,
    parameter_robustness,
    robustness_score,
)
from shortbot.markets import get_market  # noqa: E402
from shortbot.strategies import STRATEGY_REGISTRY, build  # noqa: E402

MIN_TRADES = 30
MIN_T = 2.0
MIN_PLATEAU = 0.60
MIN_ASSETS_POSITIVE = 0.50
MIN_OOS_RATIO = 0.50

GRIDS = {
    "rsi2_fade": {"rsi_threshold": [85, 90, 95], "max_bars": [3, 5, 8]},
    "gap_up_fade": {"gap_atr": [0.7, 1.0, 1.5], "stop_atr": [1.0, 1.5, 2.0]},
    "parabolic_extension_fade": {"ext_atr": [1.5, 2.0, 2.5], "stop_atr": [1.0, 1.5, 2.0]},
    "bollinger_upper_fade": {"adx_max": [15, 20, 25], "bb_std": [1.5, 2.0, 2.5]},
    "donchian_breakdown": {"channel": [10, 20, 40], "stop_atr": [2.0, 2.5, 3.0]},
    "pullback_to_ema_short": {"pullback_ema": [10, 20, 30], "stop_atr": [1.5, 2.0, 2.5]},
    "relative_weakness_short": {"lookback": [21, 63, 126], "rs_threshold": [-0.10, -0.05, -0.02]},
    "failed_breakout_short": {"lookback": [10, 20, 40], "target_atr": [2.0, 3.0, 4.0]},
    "squeeze_breakdown": {"width_pctile": [0.15, 0.25, 0.35], "stop_atr": [1.5, 2.0, 2.5]},
    "volatility_spike_exhaustion": {"vol_pctile": [0.80, 0.90], "min_run_return": [0.10, 0.15]},
    "funding_fade_short": {"funding_pctile": [0.85, 0.90, 0.95],
                           "min_funding_daily": [0.0003, 0.0005, 0.0008]},
    "oi_flush_short": {"min_oi_growth": [0.05, 0.10], "min_price_run": [0.03, 0.05]},
}


def cargar(patrones, sufijo_alt=None):
    universo = {}
    for patron in patrones:
        for path in sorted(glob.glob(patron)):
            universo[os.path.splitext(os.path.basename(path))[0]] = load_csv(path)
    if not universo:
        raise SystemExit(f"Sin CSV para {patrones}")
    return universo


def partir(universo, ratio=0.8):
    """Reserva ciega: el ultimo 20% de cada serie no participa en ninguna decision."""
    dentro, fuera = {}, {}
    for k, df in universo.items():
        corte = int(len(df) * ratio)
        dentro[k], fuera[k] = df.iloc[:corte], df.iloc[corte:]
    return dentro, fuera


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--market", default="cripto")
    ap.add_argument("--data", nargs="+", required=True)
    ap.add_argument("--alt-timeframe", nargs="*", default=None,
                    help="CSV de la misma cesta en otra temporalidad (puerta 2.5)")
    ap.add_argument("--alt-bars-per-year", type=int, default=None,
                    help="Barras/anio de esa temporalidad, p.ej. 2190 para 4h en cripto")
    ap.add_argument("--benchmark", help="CSV del indice de referencia (relative_weakness_short)")
    ap.add_argument("--risk", type=float, default=0.01)
    args = ap.parse_args()

    profile = get_market(args.market)
    universo = cargar(args.data)
    cfg = profile.config(risk_per_trade=args.risk)
    sin_costes = BacktestConfig(risk_per_trade=args.risk, costs=CostModel(
        0, 0, 0, periods_per_year=profile.periods_per_year))

    bench = load_csv(args.benchmark)["close"] if args.benchmark else None
    if bench is None:
        print("[!] Sin --benchmark: relative_weakness_short no generara senales.")

    dentro, fuera = partir(universo)
    n_barras = sum(len(d) for d in universo.values())
    print(f"\nMercado: {profile.nombre}")
    print(f"Universo: {len(universo)} activos, {n_barras:,} barras")
    print(f"Reserva ciega: ultimo 20% de cada serie ({sum(len(d) for d in fuera.values()):,} barras)\n")

    filas = []
    for nombre in STRATEGY_REGISTRY:
        est = build(nombre)
        fila = {"estrategia": nombre, "veredicto": "", "motivo": ""}

        # ---- Puerta 1: muestra y viabilidad sin costes ----
        base = evaluate_universe(est, dentro, bench, cfg)
        crudo = evaluate_universe(est, dentro, bench, sin_costes)
        fila.update({"n": base["trades"], "E[R]": base["expectancy_r"],
                     "t": base["t_stat"], "activos+": base["assets_positive"]})

        if base["trades"] < MIN_TRADES:
            fila.update(veredicto="sin muestra", motivo=f"{base['trades']} ops < {MIN_TRADES}")
            filas.append(fila); continue
        if crudo["expectancy_r"] <= 0:
            fila.update(veredicto="P1 fallida", motivo="pierde incluso sin costes")
            filas.append(fila); continue

        # ---- Puerta 2: robustez ----
        rejilla = parameter_robustness(STRATEGY_REGISTRY[nombre], GRIDS[nombre], dentro, bench, cfg)
        sc = robustness_score(rejilla, min_trades=20)
        fila["meseta"] = sc["pct_positivos"]

        if pd.isna(base["t_stat"]) or abs(base["t_stat"]) < MIN_T or base["t_stat"] < 0:
            fila.update(veredicto="P2 fallida", motivo=f"t={base['t_stat']:.2f}, no se distingue del ruido")
            filas.append(fila); continue
        if sc["pct_positivos"] is None or pd.isna(sc["pct_positivos"]) or sc["pct_positivos"] < MIN_PLATEAU:
            fila.update(veredicto="P2 fallida", motivo=f"meseta {sc['pct_positivos']:.0%} < {MIN_PLATEAU:.0%}")
            filas.append(fila); continue
        if base["assets_positive"] < MIN_ASSETS_POSITIVE:
            fila.update(veredicto="P2 fallida",
                        motivo=f"solo {base['assets_positive']:.0%} de activos en positivo")
            filas.append(fila); continue

        # ---- Puerta 2.5: temporalidad cruzada ----
        if args.alt_timeframe:
            alt_uni = cargar(args.alt_timeframe)
            ppy = args.alt_bars_per_year or profile.periods_per_year
            alt_cfg = BacktestConfig(risk_per_trade=args.risk, costs=CostModel(
                profile.costs.commission_bps, profile.costs.slippage_bps,
                profile.costs.borrow_annual_pct, periods_per_year=ppy))
            alt = evaluate_universe(est, alt_uni, bench, alt_cfg)
            fila["E[R] alt"] = alt["expectancy_r"]
            if alt["trades"] >= MIN_TRADES and alt["expectancy_r"] <= 0:
                fila.update(veredicto="P2.5 fallida",
                            motivo=f"otra temporalidad: {alt['expectancy_r']:+.3f} R")
                filas.append(fila); continue

        # ---- Puerta 3: fuera de muestra ----
        oos = evaluate_universe(est, fuera, bench, cfg)
        fila["E[R] oos"] = oos["expectancy_r"]
        fila["n oos"] = oos["trades"]
        if oos["trades"] < 10:
            fila.update(veredicto="P3 sin datos", motivo=f"solo {oos['trades']} ops fuera de muestra")
        elif oos["expectancy_r"] < base["expectancy_r"] * MIN_OOS_RATIO:
            fila.update(veredicto="P3 fallida",
                        motivo=f"degrada de {base['expectancy_r']:+.3f} a {oos['expectancy_r']:+.3f}")
        else:
            fila.update(veredicto="PASA", motivo="supera todas las puertas")
        filas.append(fila)

    tabla = pd.DataFrame(filas)
    cols = [c for c in ["estrategia", "n", "E[R]", "t", "activos+", "meseta",
                        "E[R] alt", "E[R] oos", "n oos", "veredicto", "motivo"]
            if c in tabla.columns]
    tabla = tabla[cols]
    num = tabla.select_dtypes("number")
    tabla[num.columns] = num.round(3)

    orden = {"PASA": 0, "P3 fallida": 1, "P3 sin datos": 2, "P2.5 fallida": 3,
             "P2 fallida": 4, "P1 fallida": 5, "sin muestra": 6}
    tabla = tabla.sort_values("veredicto", key=lambda s: s.map(orden).fillna(9))

    print("=" * 118)
    print("VALIDACION POR PUERTAS")
    print("=" * 118)
    print(tabla.to_string(index=False))

    pasan = tabla[tabla["veredicto"] == "PASA"]
    print(f"\n{len(pasan)} de {len(tabla)} estrategias superan todas las puertas.")
    if pasan.empty:
        print("Ninguna pasa. Es el resultado esperado en las primeras tandas: "
              "descartar barato es el objetivo.")
    else:
        print("Siguiente para las que pasan: paper trading (puerta 4), "
              "minimo 60 sesiones o 50 operaciones.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
