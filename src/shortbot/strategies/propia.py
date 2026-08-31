"""Teoria propia: Continuacion Bajista con Riesgo Comprimido (CBRC).

Ver docs/04-teoria-propia.md para las premisas y el protocolo de validacion.

Sintesis de lo que la evidencia dijo que funciona, mas un elemento nuevo:

- Estructura bajista (de pullback_to_ema_short, t=5,85).
- Compresion de volatilidad, para que el stop sea barato (de squeeze_breakdown,
  t=5,12, la mas fuerte del catalogo).
- Gatillo de continuacion, nunca de fade: las 6 estrategias de fade del catalogo
  perdieron, las 3 de continuacion ganaron. Sin excepciones.
- **Veto de funding**: no abrir cortos con el funding en su decil superior.
  Sale de falsar funding_fade_short, donde medimos que un funding extremo
  predice +10,3% a 10 barras, no una correccion. El hallazgo se usa invertido:
  no como senal de entrada, sino como prohibicion.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from .. import indicators as ind
from .base import Strategy, frame


class CompressedTrendShort(Strategy):
    """CBRC: cuatro condiciones simultaneas para abrir un corto."""

    def __init__(self, **params):
        super().__init__(
            name="cbrc_short",
            family="propia",
            thesis=(
                "Estructura bajista + volatilidad comprimida + perdida de nivel, "
                "y nunca con el flujo alcista saturado."
            ),
            params={
                # 1. Estructura
                "fast_ema": 50,
                "slow_ema": 200,
                # 2. Compresion: el riesgo tiene que estar barato
                "bb_period": 20,
                "width_lookback": 120,
                "width_pctile": 0.35,
                # 3. Gatillo de continuacion
                "trigger_lookback": 10,
                # 4. Veto de flujo (aportacion propia)
                "funding_lookback": 90,
                "funding_veto_pctile": 0.90,
                "usar_veto_funding": True,
                # 5. Riesgo
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

        # 1. Estructura bajista confirmada.
        estructura = ind.ema(close, p["fast_ema"]) < ind.ema(close, p["slow_ema"])

        # 2. Volatilidad comprimida: aqui el stop en ATR esta cerca en terminos
        #    absolutos, asi que el mismo movimiento da mas R.
        ancho = ind.bb_width(close, p["bb_period"])
        rank_ancho = ancho.rolling(
            p["width_lookback"], min_periods=p["width_lookback"]
        ).rank(pct=True)
        comprimida = rank_ancho.shift(1) <= p["width_pctile"]

        # 3. Gatillo: perdida de nivel. Nunca un rechazo de maximo.
        minimo, _ = ind.donchian(df, p["trigger_lookback"])
        gatillo = close < minimo

        entry = estructura & comprimida & gatillo

        # 4. Veto de flujo: con el funding en su decil superior el precio tiende
        #    a SEGUIR subiendo (+10,3% a 10 barras frente a +2,3% de media). No
        #    es una senal de entrada invertida: es una prohibicion de operar.
        if p["usar_veto_funding"] and "funding_rate" in df.columns:
            rank_funding = df["funding_rate"].rolling(
                p["funding_lookback"], min_periods=p["funding_lookback"]
            ).rank(pct=True)
            # Solo veta cuando hay dato; un NaN no debe bloquear la operacion.
            veto = (rank_funding >= p["funding_veto_pctile"]).fillna(False)
            entry = entry & ~veto

        return frame(
            df.index,
            entry=entry,
            atr=a,
            stop_atr=p["stop_atr"],
            target_atr=p["target_atr"],
            max_bars=p["max_bars"],
        )
