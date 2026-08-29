"""Evaluacion de estrategias.

Una sola corrida rentable no dice nada. Lo que buscamos aqui son tres cosas,
en este orden de importancia:

1. **Consistencia entre activos** (no una accion afortunada).
2. **Meseta de parametros**, no un pico. Si la estrategia solo gana con
   RSI>90 y se hunde con RSI>88, no hay edge: hay sobreajuste.
3. **Comportamiento por regimen.** Un corto que solo gana en el regimen bajista
   es un seguro, no una fuente de alfa; hay que saberlo antes, no despues.
"""

from __future__ import annotations

import itertools
from typing import Iterable, Mapping, Optional

import numpy as np
import pandas as pd

from .backtest import BacktestConfig, BacktestResult, ShortBacktester
from .metrics import summarize
from .strategies.base import Strategy


def run_strategy(
    strategy: Strategy,
    df: pd.DataFrame,
    benchmark: Optional[pd.Series] = None,
    config: Optional[BacktestConfig] = None,
) -> BacktestResult:
    signals = strategy.generate_signals(df, benchmark)
    return ShortBacktester(config or BacktestConfig()).run(df, signals)


def evaluate_universe(
    strategy: Strategy,
    universe: Mapping[str, pd.DataFrame],
    benchmark: Optional[pd.Series] = None,
    config: Optional[BacktestConfig] = None,
) -> dict:
    """Agrega los trades de todos los activos y resume el conjunto.

    Se juntan los trades (no las curvas de equity) porque cada activo se opera
    con el mismo riesgo por operacion: la unidad comparable es el R-multiplo.
    """
    all_trades, per_asset = [], []
    for symbol, df in universe.items():
        res = run_strategy(strategy, df, benchmark, config)
        row = summarize(res)
        row["symbol"] = symbol
        per_asset.append(row)
        if not res.trades.empty:
            trades = res.trades.copy()
            trades["symbol"] = symbol
            all_trades.append(trades)

    trades = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
    per_asset_df = pd.DataFrame(per_asset)

    out = {
        "strategy": strategy.name,
        "family": strategy.family,
        "assets": len(universe),
        "trades": int(len(trades)),
    }
    if trades.empty:
        out.update({k: np.nan for k in
                    ["expectancy_r", "win_rate", "profit_factor", "avg_win_r",
                     "avg_loss_r", "worst_trade_r", "avg_bars", "gap_stop_pct",
                     "assets_positive", "t_stat"]})
        return out

    r = trades["r_multiple"].dropna()
    wins = trades[trades["pnl"] > 0]
    gross_win = float(wins["pnl"].sum())
    gross_loss = float(-trades.loc[trades["pnl"] <= 0, "pnl"].sum())

    out.update({
        "expectancy_r": float(r.mean()),
        # t-stat de la expectativa: por debajo de ~2 no distinguimos el
        # resultado del ruido, por muy bonita que sea la curva.
        "t_stat": float(r.mean() / (r.std(ddof=1) / np.sqrt(len(r)))) if len(r) > 1 and r.std(ddof=1) > 0 else np.nan,
        "win_rate": float(len(wins) / len(trades)),
        "profit_factor": float(gross_win / gross_loss) if gross_loss > 0 else np.inf,
        "avg_win_r": float(wins["r_multiple"].mean()) if len(wins) else np.nan,
        "avg_loss_r": float(trades.loc[trades["pnl"] <= 0, "r_multiple"].mean()),
        "worst_trade_r": float(r.min()),
        "avg_bars": float(trades["bars_held"].mean()),
        "gap_stop_pct": float((trades["reason"] == "gap_stop").mean()),
        # Fraccion de activos con expectativa positiva: mide consistencia.
        "assets_positive": float((per_asset_df["expectancy_r"] > 0).mean()),
    })
    out["_per_asset"] = per_asset_df
    out["_trades"] = trades
    return out


def parameter_robustness(
    strategy_cls,
    grid: Mapping[str, Iterable],
    universe: Mapping[str, pd.DataFrame],
    benchmark: Optional[pd.Series] = None,
    config: Optional[BacktestConfig] = None,
) -> pd.DataFrame:
    """Barre la rejilla de parametros y devuelve la expectativa de cada combo.

    Lo que importa no es el mejor valor de la tabla, sino cuantas combinaciones
    quedan en positivo. Una estrategia sana tiene una meseta amplia.
    """
    keys = list(grid)
    rows = []
    for combo in itertools.product(*(grid[k] for k in keys)):
        params = dict(zip(keys, combo))
        res = evaluate_universe(strategy_cls(**params), universe, benchmark, config)
        rows.append({**params,
                     "trades": res["trades"],
                     "expectancy_r": res["expectancy_r"],
                     "profit_factor": res["profit_factor"]})
    return pd.DataFrame(rows)


def robustness_score(grid_df: pd.DataFrame, min_trades: int = 30) -> dict:
    """Resume un barrido: cuanta meseta hay y cuanto se dispersa el resultado."""
    valid = grid_df[grid_df["trades"] >= min_trades]
    if valid.empty:
        return {"combos": int(len(grid_df)), "combos_validos": 0,
                "pct_positivos": np.nan, "expectancy_mediana": np.nan,
                "expectancy_peor": np.nan}
    return {
        "combos": int(len(grid_df)),
        "combos_validos": int(len(valid)),
        "pct_positivos": float((valid["expectancy_r"] > 0).mean()),
        "expectancy_mediana": float(valid["expectancy_r"].median()),
        "expectancy_peor": float(valid["expectancy_r"].min()),
    }


def regime_breakdown(
    strategy: Strategy,
    universe: Mapping[str, pd.DataFrame],
    benchmark: Optional[pd.Series] = None,
    config: Optional[BacktestConfig] = None,
) -> pd.DataFrame:
    """Expectativa por regimen de mercado (solo con datos sinteticos etiquetados)."""
    rows = []
    for symbol, df in universe.items():
        labels = df.attrs.get("regime")
        if labels is None:
            continue
        regime = pd.Series(labels, index=df.index)
        res = run_strategy(strategy, df, benchmark, config)
        if res.trades.empty:
            continue
        t = res.trades.copy()
        t["regime"] = regime.reindex(t["entry_date"]).to_numpy()
        rows.append(t[["regime", "r_multiple", "pnl"]])
    if not rows:
        return pd.DataFrame()
    allt = pd.concat(rows, ignore_index=True)
    return (
        allt.groupby("regime")["r_multiple"]
        .agg(trades="count", expectancy_r="mean", peor="min")
        .reset_index()
        .sort_values("expectancy_r", ascending=False)
    )


def walk_forward_split(df: pd.DataFrame, n_folds: int = 4, train_ratio: float = 0.6):
    """Divide la serie en ventanas ancladas train/test consecutivas.

    Los parametros se eligen SOLO en train y se miden SOLO en test. Es la
    unica forma de que el resultado se parezca a lo que pasara en vivo.
    """
    n = len(df)
    fold_size = n // n_folds
    for k in range(n_folds):
        end = fold_size * (k + 1)
        train_end = int(end * train_ratio) if k == 0 else fold_size * k
        if train_end < 250 or end - train_end < 50:
            continue
        yield df.iloc[:train_end], df.iloc[train_end:end]
