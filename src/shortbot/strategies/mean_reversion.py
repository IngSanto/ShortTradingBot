"""Familia 1 - Reversion a la media: vender el exceso al alza.

Tesis compartida: un movimiento vertical al alza sin soporte de flujo real
tiende a corregir. El edge es *estadistico y de corto plazo* (dias, no meses),
por lo que la ventana de exposicion tiene que ser corta: cuanto mas tiempo en
mercado, mas paga la deriva alcista estructural en contra del corto.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from .. import indicators as ind
from .base import Strategy, frame


class RSI2Fade(Strategy):
    """Sobrecompra extrema de muy corto plazo dentro de una tendencia bajista.

    Reglas: precio por debajo de la SMA larga (filtro de tendencia bajista) y
    RSI(2) por encima del umbral -> corto. Salida rapida por objetivo, stop
    en ATR o tiempo. Es la version corta del clasico de Connors: el filtro de
    tendencia es lo que evita pelearse con un mercado alcista.
    """

    def __init__(self, **params):
        super().__init__(
            name="rsi2_fade",
            family="reversion",
            thesis="Sobrecompra de 2 dias dentro de tendencia bajista se corrige.",
            params={
                "rsi_period": 2,
                "rsi_threshold": 90,
                "trend_sma": 200,
                "atr_period": 14,
                "stop_atr": 2.0,
                "target_atr": 2.0,
                "max_bars": 5,
                **params,
            },
        )

    def _signals(self, df: pd.DataFrame, benchmark: Optional[pd.Series]) -> pd.DataFrame:
        p = self.params
        close = df["close"]
        r = ind.rsi(close, p["rsi_period"])
        trend = ind.sma(close, p["trend_sma"])
        a = ind.atr(df, p["atr_period"])

        entry = (r > p["rsi_threshold"]) & (close < trend)
        return frame(
            df.index,
            entry=entry,
            atr=a,
            stop_atr=p["stop_atr"],
            target_atr=p["target_atr"],
            max_bars=p["max_bars"],
        )


class GapUpFade(Strategy):
    """Hueco de apertura al alza sin continuidad: se cierra el gap.

    Reglas: la apertura abre por encima del cierre previo mas ``gap_atr`` ATRs,
    el volumen confirma interes (climax) y la barra cierra por debajo de su
    propia mitad -> el impulso ha fallado. Corto al dia siguiente.
    """

    def __init__(self, **params):
        super().__init__(
            name="gap_up_fade",
            family="reversion",
            thesis="Un hueco alcista climatico que cierra debil tiende a rellenarse.",
            params={
                "gap_atr": 1.0,
                "atr_period": 14,
                "min_volume_ratio": 1.5,
                "close_position_max": 0.5,   # cierre en la mitad baja del rango
                "stop_atr": 1.5,
                "target_atr": 2.0,
                "max_bars": 4,
                **params,
            },
        )

    def _signals(self, df: pd.DataFrame, benchmark: Optional[pd.Series]) -> pd.DataFrame:
        p = self.params
        a = ind.atr(df, p["atr_period"])
        gap = (df["open"] - df["close"].shift(1)) / a
        rng = (df["high"] - df["low"]).replace(0.0, np.nan)
        close_pos = (df["close"] - df["low"]) / rng
        vol_ok = ind.volume_filter(df["volume"], p["min_volume_ratio"])

        entry = (gap >= p["gap_atr"]) & (close_pos <= p["close_position_max"]) & vol_ok
        return frame(
            df.index,
            entry=entry,
            atr=a,
            stop_atr=p["stop_atr"],
            target_atr=p["target_atr"],
            max_bars=p["max_bars"],
        )


class ParabolicExtensionFade(Strategy):
    """Extension parabolica sobre la media: vender el agotamiento, no la subida.

    Reglas: el cierre esta a mas de ``ext_atr`` ATRs por encima de la EMA de
    referencia, se han encadenado varias subidas y la ultima barra hace un
    maximo mas bajo (primera senal de que se acabo el impulso).

    Ojo: entrar *durante* la extension es como ponerse delante de un tren. La
    condicion de maximo mas bajo es lo que convierte la idea en operable.
    """

    def __init__(self, **params):
        super().__init__(
            name="parabolic_extension_fade",
            family="reversion",
            thesis="Agotamiento tras extension vertical; se opera el primer maximo mas bajo.",
            params={
                "ema_period": 20,
                "ext_atr": 2.0,          # ATRs por encima de la media
                "run_bars": 5,
                "min_run_return": 0.08,  # subida acumulada minima del tramo
                "min_up_bars": 3,        # de las 'run_bars', cuantas al alza
                "atr_period": 14,
                "stop_atr": 1.5,
                "target_atr": 2.5,
                "max_bars": 6,
                **params,
            },
        )

    def _signals(self, df: pd.DataFrame, benchmark: Optional[pd.Series]) -> pd.DataFrame:
        p = self.params
        a = ind.atr(df, p["atr_period"])
        base = ind.ema(df["close"], p["ema_period"])
        extension = (df["close"] - base) / a

        # El tramo se mide por la subida acumulada, no por exigir que todas las
        # barras sean alcistas: un tramo parabolico real tiene barras de pausa.
        run = df["close"].pct_change(p["run_bars"])
        up_bars = (df["close"] > df["close"].shift(1)).rolling(p["run_bars"]).sum()
        lower_high = df["high"] < df["high"].shift(1)

        stretched = (
            (extension.shift(1) >= p["ext_atr"])
            & (run.shift(1) >= p["min_run_return"])
            & (up_bars.shift(1) >= p["min_up_bars"])
        )
        entry = stretched & lower_high
        return frame(
            df.index,
            entry=entry,
            atr=a,
            stop_atr=p["stop_atr"],
            target_atr=p["target_atr"],
            max_bars=p["max_bars"],
        )


class BollingerUpperFade(Strategy):
    """Cierre fuera de la banda superior en mercado sin tendencia (ADX bajo).

    El filtro de ADX es lo que separa esta estrategia de perder dinero: fuera
    de banda en un mercado en tendencia no es exceso, es continuacion.
    """

    def __init__(self, **params):
        super().__init__(
            name="bollinger_upper_fade",
            family="reversion",
            thesis="Fuera de banda superior en rango lateral revierte a la media.",
            params={
                "bb_period": 20,
                "bb_std": 2.0,
                "adx_period": 14,
                "adx_max": 20,
                "atr_period": 14,
                "stop_atr": 2.0,
                "target_atr": 2.0,
                "max_bars": 8,
                **params,
            },
        )

    def _signals(self, df: pd.DataFrame, benchmark: Optional[pd.Series]) -> pd.DataFrame:
        p = self.params
        a = ind.atr(df, p["atr_period"])
        _, mid, upper = ind.bollinger(df["close"], p["bb_period"], p["bb_std"])
        trend_strength = ind.adx(df, p["adx_period"])

        entry = (df["close"] > upper) & (trend_strength < p["adx_max"])
        # Salida discrecional: vuelta a la media, aunque no se toque el objetivo.
        exit_ = df["close"] < mid
        return frame(
            df.index,
            entry=entry,
            exit=exit_,
            atr=a,
            stop_atr=p["stop_atr"],
            target_atr=p["target_atr"],
            max_bars=p["max_bars"],
        )
