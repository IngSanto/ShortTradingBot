"""Fuentes de datos.

Tres caminos, en orden de preferencia para investigar:

1. ``load_csv``  -> datos reales que ya tengas en disco (data/*.csv).
2. ``load_yfinance`` -> descarga acciones/ETFs si la libreria esta instalada.
3. ``synthetic_ohlcv`` -> generador con regimenes (alcista, bajista, lateral) y
   colas gordas + squeezes. Sirve para probar que el codigo funciona y para ver
   como se comporta una estrategia en cada regimen. **No es evidencia de edge.**
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

OHLCV = ["open", "high", "low", "close", "volume"]


def _validate(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).lower() for c in df.columns]
    missing = set(OHLCV[:4]) - set(df.columns)
    if missing:
        raise ValueError(f"Faltan columnas {sorted(missing)}; disponibles: {list(df.columns)}")
    if "volume" not in df.columns:
        df["volume"] = np.nan
    df = df[~df.index.duplicated(keep="last")].sort_index()
    # Se conservan las columnas extra (funding_rate, open_interest...): recortar
    # a OHLCV dejaba mudas a las estrategias que dependen de ellas, y sin error,
    # que es la peor forma de fallar.
    extra = [c for c in df.columns if c not in OHLCV]
    return df[OHLCV + extra].astype(float)


def load_csv(path: str, date_col: str = "date") -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [str(c).lower() for c in df.columns]
    df[date_col] = pd.to_datetime(df[date_col])
    return _validate(df.set_index(date_col))


def load_yfinance(ticker: str, start: str = "2015-01-01", end: Optional[str] = None,
                  interval: str = "1d") -> pd.DataFrame:
    try:
        import yfinance as yf
    except ImportError as exc:  # pragma: no cover
        raise ImportError("Instala yfinance: pip install yfinance") from exc
    raw = yf.download(ticker, start=start, end=end, interval=interval,
                      auto_adjust=False, progress=False)
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    return _validate(raw)


# --------------------------------------------------------------------------- #
# Generador sintetico con regimenes
# --------------------------------------------------------------------------- #

REGIMES = {
    # (deriva diaria, vol diaria, prob. de shock, sesgo del shock)
    "bull":     (0.0006, 0.011, 0.010, +1.0),
    "bear":     (-0.0008, 0.022, 0.020, -0.6),
    "chop":     (0.0000, 0.013, 0.012, 0.0),
    "squeeze":  (0.0025, 0.035, 0.045, +1.0),   # el escenario que mata a los cortos
}


def synthetic_ohlcv(
    n: int = 2000,
    start: str = "2016-01-01",
    seed: int = 7,
    regime_len: int = 180,
    regimes: Optional[list[str]] = None,
    start_price: float = 100.0,
) -> pd.DataFrame:
    """Serie diaria con regimenes encadenados y saltos asimetricos.

    Los shocks al alza son mas frecuentes y violentos en el regimen ``squeeze``:
    replica la asimetria real a la que se enfrenta un vendedor en corto.
    """
    rng = np.random.default_rng(seed)
    regimes = regimes or ["bull", "chop", "bear", "chop", "squeeze", "bull", "bear", "chop"]

    mu, sigma, shock_p, shock_bias, labels = [], [], [], [], []
    while len(mu) < n:
        name = regimes[len(mu) // regime_len % len(regimes)]
        m, s, p, b = REGIMES[name]
        take = min(regime_len, n - len(mu))
        mu += [m] * take
        sigma += [s] * take
        shock_p += [p] * take
        shock_bias += [b] * take
        labels += [name] * take

    mu = np.array(mu); sigma = np.array(sigma)
    shock_p = np.array(shock_p); shock_bias = np.array(shock_bias)

    rets = rng.normal(mu, sigma)
    shocks = rng.random(n) < shock_p
    shock_size = rng.gamma(shape=2.0, scale=0.022, size=n)
    shock_sign = np.where(rng.random(n) < (0.5 + 0.5 * shock_bias), 1.0, -1.0)
    rets = rets + shocks * shock_size * shock_sign

    close = start_price * np.exp(np.cumsum(rets))

    # Reparto intradia/nocturno. En renta variable la mayor parte del salto de
    # un shock ocurre fuera de sesion: es exactamente el riesgo que no puedes
    # gestionar con un stop y el que arruina a los vendedores en corto. Si el
    # generador no lo reproduce, el backtest sale optimista de fabrica.
    prev_close = np.concatenate([[start_price], close[:-1]])
    overnight_share = np.where(shocks, rng.uniform(0.5, 0.9, n), 0.0)
    shock_component = shocks * shock_size * shock_sign
    gap_ret = overnight_share * shock_component + rng.normal(0, 0.45, n) * sigma
    open_ = prev_close * np.exp(gap_ret)
    open_ = np.clip(open_, np.minimum(prev_close, close) * 0.5,
                    np.maximum(prev_close, close) * 1.5)
    body_hi = np.maximum(open_, close)
    body_lo = np.minimum(open_, close)
    wick = np.abs(rng.normal(0, 0.6, n)) * sigma * close
    high = body_hi + wick
    low = np.maximum(body_lo - np.abs(rng.normal(0, 0.6, n)) * sigma * close, 0.01)

    base_vol = 1_000_000
    volume = base_vol * np.exp(rng.normal(0, 0.35, n)) * (1 + 3 * shocks)

    idx = pd.bdate_range(start=start, periods=n)
    df = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )
    # Lista simple (no Series): pandas compara attrs con == al propagarlos.
    df.attrs["regime"] = labels
    return df


def regime_series(df: pd.DataFrame) -> pd.Series:
    """Etiqueta de regimen por barra de una serie sintetica."""
    labels = df.attrs.get("regime")
    if labels is None:
        raise ValueError("El DataFrame no lleva etiquetas de regimen.")
    return pd.Series(labels, index=df.index, name="regime")


def synthetic_universe(n_assets: int = 8, **kwargs) -> dict[str, pd.DataFrame]:
    """Varios activos con semillas distintas, para pruebas cross-sectional."""
    return {f"SYN{i:02d}": synthetic_ohlcv(seed=100 + i, **kwargs) for i in range(n_assets)}


def synthetic_perp(n: int = 2000, seed: int = 7, **kwargs) -> pd.DataFrame:
    """Serie de perpetuo con ``funding_rate`` y ``open_interest`` sinteticos.

    El funding se modela como funcion del impulso reciente del precio, que es
    como se comporta en la realidad: cuando el precio sube, los largos se
    apalancan y pagan cada vez mas por mantener la posicion. El open interest
    crece con las tendencias y se desploma tras las caidas fuertes
    (liquidaciones).
    """
    rng = np.random.default_rng(seed + 5000)
    df = synthetic_ohlcv(n=n, seed=seed, **kwargs)

    momentum = df["close"].pct_change(5).fillna(0.0)
    base_funding = 0.0003                      # 0,03% diario ~ 11% anual
    funding = base_funding + 0.020 * momentum + rng.normal(0, 0.00015, n)
    df["funding_rate"] = funding.clip(-0.003, 0.005)

    trend = df["close"].pct_change(10).fillna(0.0)
    oi = 1e8 * np.exp(np.cumsum(0.35 * trend.to_numpy() + rng.normal(0, 0.01, n)))
    # Purga de open interest tras caidas fuertes: la cascada de liquidaciones.
    flush = df["close"].pct_change(3).fillna(0.0) < -0.08
    df["open_interest"] = pd.Series(oi, index=df.index).where(~flush, pd.Series(oi, index=df.index) * 0.75)
    return df


def synthetic_perp_universe(n_assets: int = 6, **kwargs) -> dict[str, pd.DataFrame]:
    symbols = ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "AVAX", "LINK"]
    return {symbols[i % len(symbols)]: synthetic_perp(seed=200 + i, **kwargs)
            for i in range(n_assets)}
