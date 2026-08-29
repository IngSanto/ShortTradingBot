"""Indicadores tecnicos vectorizados sobre pandas.

Todas las funciones reciben Series/DataFrame con indice temporal ordenado y
devuelven Series alineadas. Ninguna funcion mira hacia el futuro: el valor en
la barra ``t`` solo usa informacion disponible hasta el cierre de ``t``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False, min_periods=period).mean()


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period, min_periods=period).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """RSI de Wilder. Con period=2 es el usado en las estrategias de reversion."""
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100 - (100 / (1 + rs))
    # avg_loss == 0 -> mercado sin bajadas en la ventana -> RSI 100
    return out.where(avg_loss != 0, 100.0)


def true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["close"].shift(1)
    ranges = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    )
    return ranges.max(axis=1)


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """ATR de Wilder. Es la unidad de riesgo de todo el sistema."""
    return true_range(df).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """ADX: fuerza de tendencia (sin direccion). Filtro de regimen."""
    up = df["high"].diff()
    down = -df["low"].diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    tr = true_range(df)
    atr_ = tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(
        alpha=1 / period, adjust=False, min_periods=period
    ).mean() / atr_
    minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(
        alpha=1 / period, adjust=False, min_periods=period
    ).mean() / atr_
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan)
    return dx.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def bollinger(series: pd.Series, period: int = 20, n_std: float = 2.0):
    mid = sma(series, period)
    sd = series.rolling(period, min_periods=period).std(ddof=0)
    return mid - n_std * sd, mid, mid + n_std * sd


def bb_width(series: pd.Series, period: int = 20, n_std: float = 2.0) -> pd.Series:
    lower, mid, upper = bollinger(series, period, n_std)
    return (upper - lower) / mid


def keltner(df: pd.DataFrame, period: int = 20, mult: float = 2.0):
    mid = ema(df["close"], period)
    rng = mult * atr(df, period)
    return mid - rng, mid, mid + rng


def donchian(df: pd.DataFrame, period: int = 20):
    """Maximo/minimo de las ``period`` barras ANTERIORES (excluye la actual)."""
    hi = df["high"].rolling(period, min_periods=period).max().shift(1)
    lo = df["low"].rolling(period, min_periods=period).min().shift(1)
    return lo, hi


def zscore(series: pd.Series, period: int = 20) -> pd.Series:
    mean = series.rolling(period, min_periods=period).mean()
    sd = series.rolling(period, min_periods=period).std(ddof=0)
    return (series - mean) / sd.replace(0.0, np.nan)


def rolling_return(series: pd.Series, period: int) -> pd.Series:
    return series.pct_change(period)


def realized_vol(series: pd.Series, period: int = 20, periods_per_year: int = 252) -> pd.Series:
    """Volatilidad realizada anualizada sobre retornos logaritmicos."""
    rets = np.log(series).diff()
    return rets.rolling(period, min_periods=period).std(ddof=0) * np.sqrt(periods_per_year)


def relative_strength(series: pd.Series, benchmark: pd.Series, period: int = 63) -> pd.Series:
    """Fuerza relativa: retorno del activo menos el del indice en la ventana."""
    bench = benchmark.reindex(series.index).ffill()
    return series.pct_change(period) - bench.pct_change(period)


def volume_ratio(volume: pd.Series, period: int = 20) -> pd.Series:
    mean = volume.rolling(period, min_periods=period).mean()
    return volume / mean.replace(0.0, np.nan)


def volume_filter(volume: pd.Series, min_ratio: float, period: int = 20) -> pd.Series:
    """Filtro de volumen que se DESACTIVA si el dato no existe.

    Sin esta distincion, una serie sin volumen (indices, muchos CSV publicos)
    hace que la estrategia devuelva cero senales en silencio: parece que no hay
    oportunidades cuando en realidad falta el dato. Es un modo de fallo mucho
    peor que un error, porque no se nota.
    """
    if volume is None or volume.isna().all() or (volume.fillna(0) == 0).all():
        return pd.Series(True, index=volume.index)
    return (volume_ratio(volume, period) >= min_ratio).fillna(True)
