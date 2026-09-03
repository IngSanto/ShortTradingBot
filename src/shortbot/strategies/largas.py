"""Version larga de las dos estrategias aprobadas. Familia espejo.

No son hipotesis nuevas: son **las mismas reglas con el signo cambiado**, y
eso es deliberado. Inventar estrategias largas distintas mezclaria dos
preguntas -"¿funciona la pata larga?" y "¿funciona esta idea nueva?"- y
ninguna de las dos quedaria contestada.

Cada parametro se hereda literalmente de su espejo corto. No se calibra
ninguno: si hubiera que ajustarlos para que funcionen, eso ya seria evidencia
de que la simetria no se sostiene, que es justo lo que se quiere medir.

Ver docs/13-pata-larga.md.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from .. import indicators as ind
from .base import Strategy, frame


class PullbackToEMALong(Strategy):
    """Espejo de ``PullbackToEMAShort``: retroceso a la media en tendencia alcista.

    EMA50 > EMA200 (estructura alcista), el precio retrocede hasta la EMA de
    referencia y la recupera cerrando por encima -> largo.
    """

    def __init__(self, **params):
        super().__init__(
            name="pullback_to_ema_long",
            family="tendencia",
            thesis="El retroceso a la media movil en tendencia alcista es zona de compra.",
            params={
                "pullback_ema": 20, "fast_ema": 50, "slow_ema": 200,
                "atr_period": 14, "stop_atr": 2.0, "target_atr": 4.0,
                "max_bars": 20, **params,
            },
        )

    def _signals(self, df: pd.DataFrame, benchmark: Optional[pd.Series]) -> pd.DataFrame:
        p = self.params
        close = df["close"]
        a = ind.atr(df, p["atr_period"])
        ema_pb = ind.ema(close, p["pullback_ema"])
        alcista = ind.ema(close, p["fast_ema"]) > ind.ema(close, p["slow_ema"])

        tocada = df["low"] <= ema_pb            # el retroceso llega a la media
        recuperada = close > ema_pb             # y la recupera en el cierre
        estaba_encima = close.shift(1) > ema_pb.shift(1)

        entry = alcista & tocada & recuperada & ~estaba_encima.fillna(False)
        return frame(df.index, entry=entry, atr=a, stop_atr=p["stop_atr"],
                     target_atr=p["target_atr"], max_bars=p["max_bars"])


class SqueezeBreakoutLong(Strategy):
    """Espejo de ``SqueezeBreakdown``: compresion que se resuelve al alza."""

    def __init__(self, **params):
        super().__init__(
            name="squeeze_breakout_long",
            family="volatilidad",
            thesis="Tras la compresion viene la expansion; se opera solo la alcista.",
            params={
                "bb_period": 20, "width_lookback": 120, "width_pctile": 0.25,
                "trigger_lookback": 10, "atr_period": 14, "stop_atr": 2.0,
                "target_atr": 4.0, "max_bars": 20, **params,
            },
        )

    def _signals(self, df: pd.DataFrame, benchmark: Optional[pd.Series]) -> pd.DataFrame:
        p = self.params
        a = ind.atr(df, p["atr_period"])
        width = ind.bb_width(df["close"], p["bb_period"])
        rank = width.rolling(p["width_lookback"], min_periods=p["width_lookback"]).rank(pct=True)
        _, alto = ind.donchian(df, p["trigger_lookback"])

        comprimida = rank.shift(1) <= p["width_pctile"]
        entry = comprimida & (df["close"] > alto)
        return frame(df.index, entry=entry, atr=a, stop_atr=p["stop_atr"],
                     target_atr=p["target_atr"], max_bars=p["max_bars"])
