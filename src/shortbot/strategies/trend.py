"""Familia 2 - Seguimiento de tendencia bajista.

Tesis compartida: la volatilidad se agrupa y las caidas son mas rapidas que las
subidas. Un corto en tendencia gana poco a menudo y mucho de vez en cuando: hay
que dejar correr al ganador y cortar rapido al perdedor.

El precio a pagar: tasa de acierto baja (30-40%) y rachas largas de perdidas.
Si no toleras eso emocionalmente, esta familia no es para ti aunque sea rentable.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from .. import indicators as ind
from .base import Strategy, frame


class DonchianBreakdown(Strategy):
    """Ruptura del minimo de N barras con confirmacion de tendencia.

    Es la version corta del sistema Turtle. El filtro de EMA rapida < EMA lenta
    evita vender rupturas dentro de un mercado alcista, donde son trampas.
    """

    def __init__(self, **params):
        super().__init__(
            name="donchian_breakdown",
            family="tendencia",
            thesis="La ruptura de soporte en tendencia bajista tiende a continuar.",
            params={
                "channel": 20,
                "fast_ema": 50,
                "slow_ema": 200,
                "atr_period": 14,
                "stop_atr": 2.5,
                "target_atr": 6.0,
                "max_bars": 40,
                **params,
            },
        )

    def _signals(self, df: pd.DataFrame, benchmark: Optional[pd.Series]) -> pd.DataFrame:
        p = self.params
        a = ind.atr(df, p["atr_period"])
        low_ch, _ = ind.donchian(df, p["channel"])
        downtrend = ind.ema(df["close"], p["fast_ema"]) < ind.ema(df["close"], p["slow_ema"])

        entry = (df["close"] < low_ch) & downtrend
        # Salir si la estructura se rompe al alza: cierre sobre la EMA rapida.
        exit_ = df["close"] > ind.ema(df["close"], p["fast_ema"])
        return frame(
            df.index,
            entry=entry,
            exit=exit_,
            atr=a,
            stop_atr=p["stop_atr"],
            target_atr=p["target_atr"],
            max_bars=p["max_bars"],
        )


class PullbackToEMAShort(Strategy):
    """Rebote tecnico contra la EMA en tendencia bajista confirmada.

    Reglas: EMA50 < EMA200 (estructura bajista), el precio rebota hasta la EMA
    de referencia y la rechaza cerrando por debajo -> corto.

    Mejor relacion riesgo/beneficio que perseguir la ruptura: el stop cabe justo
    por encima del maximo del rebote.
    """

    def __init__(self, **params):
        super().__init__(
            name="pullback_to_ema_short",
            family="tendencia",
            thesis="El rebote a la media movil en tendencia bajista es zona de venta.",
            params={
                "pullback_ema": 20,
                "fast_ema": 50,
                "slow_ema": 200,
                "atr_period": 14,
                "stop_atr": 2.0,
                "target_atr": 4.0,
                "max_bars": 20,
                **params,
            },
        )

    def _signals(self, df: pd.DataFrame, benchmark: Optional[pd.Series]) -> pd.DataFrame:
        p = self.params
        close = df["close"]
        a = ind.atr(df, p["atr_period"])
        ema_pb = ind.ema(close, p["pullback_ema"])
        downtrend = ind.ema(close, p["fast_ema"]) < ind.ema(close, p["slow_ema"])

        touched = df["high"] >= ema_pb          # el rebote llega a la media
        rejected = close < ema_pb               # y la pierde en el cierre
        was_below = close.shift(1) < ema_pb.shift(1)

        entry = downtrend & touched & rejected & ~was_below.fillna(False)
        return frame(
            df.index,
            entry=entry,
            atr=a,
            stop_atr=p["stop_atr"],
            target_atr=p["target_atr"],
            max_bars=p["max_bars"],
        )


class RelativeWeaknessShort(Strategy):
    """Debilidad relativa frente al indice: la pata corta del momentum.

    Reglas: el activo rinde peor que su indice en la ventana de referencia y el
    propio indice no esta en modo risk-on (esta por debajo de su media larga).

    Es la unica estrategia del catalogo que necesita ``benchmark``. Sin indice
    de referencia no genera senales: es intencionado, no un fallo.
    """

    def __init__(self, **params):
        super().__init__(
            name="relative_weakness_short",
            family="tendencia",
            thesis="Lo que peor se comporta frente al indice sigue comportandose peor.",
            params={
                "lookback": 63,
                "rs_threshold": -0.05,      # 5 puntos por detras del indice
                "bench_sma": 200,
                "atr_period": 14,
                "stop_atr": 3.0,
                "target_atr": 6.0,
                "max_bars": 60,
                **params,
            },
        )

    def _signals(self, df: pd.DataFrame, benchmark: Optional[pd.Series]) -> pd.DataFrame:
        p = self.params
        a = ind.atr(df, p["atr_period"])
        if benchmark is None:
            return frame(df.index, entry=False, atr=a)

        bench = benchmark.reindex(df.index).ffill()
        rs = ind.relative_strength(df["close"], bench, p["lookback"])
        bench_weak = bench < ind.sma(bench, p["bench_sma"])

        entry = (rs <= p["rs_threshold"]) & bench_weak
        # Solo la primera senal de cada racha: si no, entrariamos cada dia.
        entry = entry & ~entry.shift(1).fillna(False)
        return frame(
            df.index,
            entry=entry,
            atr=a,
            stop_atr=p["stop_atr"],
            target_atr=p["target_atr"],
            max_bars=p["max_bars"],
        )
