"""Familia 3 - Estructura de mercado y volatilidad.

Tesis compartida: el mercado deja rastros de donde hay ordenes (maximos previos,
rangos comprimidos). Cuando un movimiento va a buscar esas ordenes y falla, deja
atrapados a los compradores: ese es el combustible de una caida.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from .. import indicators as ind
from .base import Strategy, frame


class FailedBreakoutShort(Strategy):
    """Barrido de liquidez: se supera el maximo previo y se vuelve dentro.

    Reglas: el maximo de la barra supera el maximo de las N barras anteriores
    (se activan los stops de los cortos y las ordenes de ruptura) pero el cierre
    vuelve por debajo de ese nivel. Los compradores de la ruptura quedan
    atrapados y su salida alimenta la caida.

    Es de las pocas ideas cortas con logica de flujo de ordenes detras, no solo
    estadistica.
    """

    def __init__(self, **params):
        super().__init__(
            name="failed_breakout_short",
            family="estructura",
            thesis="Ruptura falsa del maximo previo: compradores atrapados venden.",
            params={
                "lookback": 20,
                "atr_period": 14,
                "min_volume_ratio": 1.2,
                "stop_atr": 1.5,
                "target_atr": 3.0,
                "max_bars": 12,
                **params,
            },
        )

    def _signals(self, df: pd.DataFrame, benchmark: Optional[pd.Series]) -> pd.DataFrame:
        p = self.params
        a = ind.atr(df, p["atr_period"])
        _, prior_high = ind.donchian(df, p["lookback"])
        vol_ok = ind.volume_filter(df["volume"], p["min_volume_ratio"])

        swept = df["high"] > prior_high      # se barre el maximo previo
        reclaimed = df["close"] < prior_high  # pero se cierra por debajo

        entry = swept & reclaimed & vol_ok
        return frame(
            df.index,
            entry=entry,
            atr=a,
            stop_atr=p["stop_atr"],
            target_atr=p["target_atr"],
            max_bars=p["max_bars"],
        )


class SqueezeBreakdown(Strategy):
    """Compresion de volatilidad que se resuelve a la baja.

    Reglas: el ancho de las Bandas de Bollinger esta en su percentil mas bajo
    (compresion) y el precio pierde el minimo de las ultimas barras. La
    volatilidad comprimida se expande; solo operamos la expansion bajista.
    """

    def __init__(self, **params):
        super().__init__(
            name="squeeze_breakdown",
            family="volatilidad",
            thesis="Tras la compresion viene la expansion; se opera solo la bajista.",
            params={
                "bb_period": 20,
                "width_lookback": 120,
                "width_pctile": 0.25,
                "trigger_lookback": 10,
                "atr_period": 14,
                "stop_atr": 2.0,
                "target_atr": 4.0,
                "max_bars": 20,
                **params,
            },
        )

    def _signals(self, df: pd.DataFrame, benchmark: Optional[pd.Series]) -> pd.DataFrame:
        p = self.params
        a = ind.atr(df, p["atr_period"])
        width = ind.bb_width(df["close"], p["bb_period"])
        rank = width.rolling(p["width_lookback"], min_periods=p["width_lookback"]).rank(pct=True)
        low_ch, _ = ind.donchian(df, p["trigger_lookback"])

        compressed = rank.shift(1) <= p["width_pctile"]
        entry = compressed & (df["close"] < low_ch)
        return frame(
            df.index,
            entry=entry,
            atr=a,
            stop_atr=p["stop_atr"],
            target_atr=p["target_atr"],
            max_bars=p["max_bars"],
        )


class VolatilitySpikeExhaustion(Strategy):
    """Subida vertical con volatilidad disparada: fase terminal de un squeeze.

    Reglas: la volatilidad realizada esta muy por encima de su nivel habitual,
    el activo acumula una subida fuerte en pocos dias y aparece la primera barra
    con cierre bajista.

    ATENCION: esta es la estrategia con mayor riesgo de ruina del catalogo.
    Es la que operan los que se ponen cortos contra un squeeze. Si la incluimos
    en produccion, tiene que ser con el tamano mas pequeno y stop duro.
    """

    def __init__(self, **params):
        super().__init__(
            name="volatility_spike_exhaustion",
            family="volatilidad",
            thesis="Climax de volatilidad al alza seguido de barra bajista = agotamiento.",
            params={
                "vol_period": 20,
                "vol_lookback": 120,
                "vol_pctile": 0.90,
                "run_bars": 5,
                "min_run_return": 0.15,
                "atr_period": 14,
                "stop_atr": 1.5,
                "target_atr": 3.0,
                "max_bars": 5,
                **params,
            },
        )

    def _signals(self, df: pd.DataFrame, benchmark: Optional[pd.Series]) -> pd.DataFrame:
        p = self.params
        close = df["close"]
        a = ind.atr(df, p["atr_period"])
        rv = ind.realized_vol(close, p["vol_period"])
        rv_rank = rv.rolling(p["vol_lookback"], min_periods=p["vol_lookback"]).rank(pct=True)
        run = ind.rolling_return(close, p["run_bars"])
        bearish_bar = close < df["open"]

        entry = (rv_rank >= p["vol_pctile"]) & (run >= p["min_run_return"]) & bearish_bar
        return frame(
            df.index,
            entry=entry,
            atr=a,
            stop_atr=p["stop_atr"],
            target_atr=p["target_atr"],
            max_bars=p["max_bars"],
        )
