#!/usr/bin/env python3
"""Criba inicial: pasa todo el catalogo por el mismo aro y ordena.

Uso:
    python scripts/screen_strategies.py                      # datos sinteticos
    python scripts/screen_strategies.py --data data/*.csv    # datos reales
    python scripts/screen_strategies.py --robustness         # + barrido de parametros

La tabla que imprime NO dice que estrategia gana dinero. Dice cual merece que
le dediquemos datos reales y horas de validacion, y cual podemos descartar ya.
"""

from __future__ import annotations

import argparse
import glob
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from shortbot.backtest import BacktestConfig, CostModel  # noqa: E402
from shortbot.data import (  # noqa: E402
    load_csv,
    synthetic_ohlcv,
    synthetic_perp_universe,
    synthetic_universe,
)
from shortbot.markets import MERCADOS, get_market  # noqa: E402
from shortbot.evaluation import (  # noqa: E402
    evaluate_universe,
    parameter_robustness,
    regime_breakdown,
    robustness_score,
)
from shortbot.strategies import STRATEGY_REGISTRY, build_all  # noqa: E402

# Rejillas deliberadamente pequenas: buscamos meseta, no el mejor valor.
ROBUSTNESS_GRIDS = {
    "rsi2_fade": {"rsi_threshold": [85, 90, 95], "max_bars": [3, 5, 8]},
    "donchian_breakdown": {"channel": [10, 20, 40], "stop_atr": [2.0, 2.5, 3.0]},
    "pullback_to_ema_short": {"pullback_ema": [10, 20, 30], "stop_atr": [1.5, 2.0, 2.5]},
    "failed_breakout_short": {"lookback": [10, 20, 40], "target_atr": [2.0, 3.0, 4.0]},
    "bollinger_upper_fade": {"adx_max": [15, 20, 25], "bb_std": [1.5, 2.0, 2.5]},
    "squeeze_breakdown": {"width_pctile": [0.15, 0.25, 0.35], "stop_atr": [1.5, 2.0, 2.5]},
}


def load_universe(patterns: list[str] | None, n_assets: int, n_bars: int, market: str):
    if not patterns:
        # En cripto la serie sintetica incluye funding y open interest, sin los
        # cuales las dos estrategias de esa familia no generan senal alguna.
        universe = (synthetic_perp_universe(n_assets, n=n_bars) if market == "cripto"
                    else synthetic_universe(n_assets, n=n_bars))
        benchmark = synthetic_ohlcv(n=n_bars, seed=999)["close"]
        return universe, benchmark, True

    universe = {}
    for pattern in patterns:
        for path in sorted(glob.glob(pattern)):
            symbol = os.path.splitext(os.path.basename(path))[0]
            universe[symbol] = load_csv(path)
    if not universe:
        raise SystemExit(f"No se encontraron CSV con: {patterns}")
    # Sin indice explicito, usamos el activo mas largo como referencia relativa.
    longest = max(universe.values(), key=len)
    return universe, longest["close"], False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--market", default="acciones", choices=sorted(MERCADOS),
                    help="Perfil de mercado: fija costes, carry y dias por anio")
    ap.add_argument("--data", nargs="*", help="Patrones glob de CSV con columnas date,open,high,low,close,volume")
    ap.add_argument("--assets", type=int, default=10, help="Activos sinteticos (por defecto 10)")
    ap.add_argument("--bars", type=int, default=2500, help="Barras por activo (por defecto 2500 ~ 10 anios)")
    ap.add_argument("--borrow", type=float, default=None,
                    help="Sobrescribe el carry anual %% del perfil (negativo = lo cobras)")
    ap.add_argument("--slippage", type=float, default=None,
                    help="Sobrescribe el slippage en bps por lado")
    ap.add_argument("--risk", type=float, default=0.01, help="Riesgo por operacion (por defecto 1%%)")
    ap.add_argument("--robustness", action="store_true", help="Anade el barrido de parametros")
    ap.add_argument("--regimes", action="store_true", help="Desglose por regimen (solo datos sinteticos)")
    ap.add_argument("--out", help="Guarda la tabla resumen en este CSV")
    args = ap.parse_args()

    profile = get_market(args.market)
    universe, benchmark, is_synthetic = load_universe(
        args.data, args.assets, args.bars, args.market
    )

    base = profile.costs
    costs = CostModel(
        commission_bps=base.commission_bps,
        slippage_bps=args.slippage if args.slippage is not None else base.slippage_bps,
        borrow_annual_pct=args.borrow if args.borrow is not None else base.borrow_annual_pct,
        periods_per_year=base.periods_per_year,
    )
    config = BacktestConfig(risk_per_trade=args.risk, costs=costs)

    carry = costs.borrow_annual_pct
    carry_txt = (f"{abs(carry):.1f}% anual QUE COBRAS" if carry < 0
                 else f"{carry:.1f}% anual que pagas")
    print(f"\nMercado : {profile.nombre} ({profile.periods_per_year} barras/anio)")
    print(f"Universo: {len(universe)} activos x {len(next(iter(universe.values())))} barras "
          f"({'SINTETICO' if is_synthetic else 'DATOS REALES'})")
    print(f"Costes  : {costs.slippage_bps} bps slippage/lado + {costs.commission_bps} bps comision")
    print(f"Carry   : {carry_txt}")
    print(f"Riesgo  : {args.risk:.1%} del capital por operacion\n")

    rows = []
    for strategy in build_all():
        res = evaluate_universe(strategy, universe, benchmark, config)
        rows.append({k: v for k, v in res.items() if not k.startswith("_")})

    table = pd.DataFrame(rows)
    cols = ["strategy", "family", "trades", "expectancy_r", "t_stat", "win_rate",
            "profit_factor", "avg_win_r", "avg_loss_r", "worst_trade_r",
            "gap_stop_pct", "assets_positive", "avg_bars"]
    table = table[cols].sort_values("expectancy_r", ascending=False)
    num = table.select_dtypes("number")
    table[num.columns] = num.round(3)

    print("=" * 100)
    print("CRIBA DE ESTRATEGIAS (expectativa en multiplos de R, neta de costes)")
    print("=" * 100)
    print(table.to_string(index=False))

    thin = table[table["trades"] < 30]
    if not thin.empty:
        print("\n[!] Muestra insuficiente (<30 operaciones), resultado no interpretable: "
              + ", ".join(thin["strategy"]))

    if args.regimes and is_synthetic:
        print("\n" + "=" * 100)
        print("DESGLOSE POR REGIMEN")
        print("=" * 100)
        for strategy in build_all():
            rb = regime_breakdown(strategy, universe, benchmark, config)
            if not rb.empty:
                print(f"\n{strategy.name}")
                print(rb.round(3).to_string(index=False))

    if args.robustness:
        print("\n" + "=" * 100)
        print("ROBUSTEZ: fraccion de combinaciones de parametros con expectativa positiva")
        print("(<0.5 = el resultado depende de acertar el parametro -> sobreajuste)")
        print("=" * 100)
        rob_rows = []
        for name, grid in ROBUSTNESS_GRIDS.items():
            grid_df = parameter_robustness(
                STRATEGY_REGISTRY[name], grid, universe, benchmark, config
            )
            rob_rows.append({"strategy": name, **robustness_score(grid_df)})
        print(pd.DataFrame(rob_rows).round(3).to_string(index=False))

    if args.out:
        table.to_csv(args.out, index=False)
        print(f"\nTabla guardada en {args.out}")

    if is_synthetic:
        print("\nRecordatorio: sobre datos sinteticos esta tabla valida el CODIGO, no el EDGE.")
        print("Para validar el edge: python scripts/fetch_data.py --market "
              f"{args.market}  (requiere internet)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
