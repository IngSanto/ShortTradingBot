"""Metricas de evaluacion.

En corto importan mas la cola izquierda y el peor trade que el retorno medio:
la perdida de un corto no esta acotada y llega en huecos, no en deriva suave.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .backtest import BacktestResult


def max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    return float((equity / peak - 1.0).min())


def sharpe(returns: pd.Series, periods_per_year: int = 252) -> float:
    sd = returns.std(ddof=0)
    if sd == 0 or np.isnan(sd):
        return 0.0
    return float(returns.mean() / sd * np.sqrt(periods_per_year))


def sortino(returns: pd.Series, periods_per_year: int = 252) -> float:
    downside = returns[returns < 0]
    dd = downside.std(ddof=0)
    if dd == 0 or np.isnan(dd) or len(downside) == 0:
        return 0.0
    return float(returns.mean() / dd * np.sqrt(periods_per_year))


def cagr(equity: pd.Series, periods_per_year: int = 252) -> float:
    if len(equity) < 2 or equity.iloc[0] <= 0:
        return 0.0
    years = len(equity) / periods_per_year
    if years <= 0:
        return 0.0
    return float((equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1)


def summarize(result: BacktestResult, periods_per_year: int = 252) -> dict:
    """Resumen de una sola corrida. Devuelve un dict listo para tabular."""
    eq = result.equity_curve
    trades = result.trades
    rets = result.returns

    out = {
        "trades": int(len(trades)),
        "return_total": float(eq.iloc[-1] / eq.iloc[0] - 1) if len(eq) else 0.0,
        "cagr": cagr(eq, periods_per_year),
        "sharpe": sharpe(rets, periods_per_year),
        "sortino": sortino(rets, periods_per_year),
        "max_dd": max_drawdown(eq),
        "exposure": float(result.exposure.abs().mean()),
    }

    if trades.empty:
        out.update({
            "win_rate": np.nan, "profit_factor": np.nan, "expectancy_r": np.nan,
            "avg_win_r": np.nan, "avg_loss_r": np.nan, "worst_trade_r": np.nan,
            "avg_bars": np.nan, "gap_stops": 0, "costs_pct_of_gross": np.nan,
        })
        return out

    wins = trades[trades["pnl"] > 0]
    losses = trades[trades["pnl"] <= 0]
    gross_win = float(wins["pnl"].sum())
    gross_loss = float(-losses["pnl"].sum())
    total_costs = float((trades["fees"] + trades["borrow_cost"]).sum())
    gross_abs = float(trades["gross_pnl"].abs().sum())

    out.update({
        "win_rate": float(len(wins) / len(trades)),
        "profit_factor": float(gross_win / gross_loss) if gross_loss > 0 else np.inf,
        "expectancy_r": float(trades["r_multiple"].mean()),
        "avg_win_r": float(wins["r_multiple"].mean()) if len(wins) else np.nan,
        "avg_loss_r": float(losses["r_multiple"].mean()) if len(losses) else np.nan,
        "worst_trade_r": float(trades["r_multiple"].min()),
        "avg_bars": float(trades["bars_held"].mean()),
        # Cuantas salidas fueron por hueco en contra: proxy de riesgo de squeeze.
        "gap_stops": int((trades["reason"] == "gap_stop").sum()),
        "costs_pct_of_gross": float(total_costs / gross_abs) if gross_abs > 0 else np.nan,
    })
    return out


def format_summary_table(rows: list[dict]) -> pd.DataFrame:
    """Ordena por expectativa en R y redondea para lectura humana."""
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    if "expectancy_r" in df:
        df = df.sort_values("expectancy_r", ascending=False)
    num = df.select_dtypes(include=[float])
    df[num.columns] = num.round(4)
    return df.reset_index(drop=True)
