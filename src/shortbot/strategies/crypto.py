"""Familia E - Especificas de perpetuos de cripto.

Tesis: en un futuro perpetuo el funding es una medida DIRECTA y observable del
posicionamiento. Cuando se dispara en positivo, los largos apalancados estan
pagando a los cortos para mantener su posicion abierta.

Esto es lo mas parecido a un edge estructural que existe en el lado corto:
- No hay deriva alcista persistente que combatir.
- El desequilibrio de flujo es medible en tiempo real, no inferido del precio.
- **Cobras carry mientras esperas** en lugar de pagarlo. Es el unico caso del
  catalogo en el que el paso del tiempo juega a favor del vendedor en corto.

Requiere una columna ``funding_rate`` en el DataFrame (tasa por barra, en
fraccion: 0.0003 = 0,03% diario). Sin ella la estrategia no genera senales,
y eso es intencionado: no queremos aproximarla con el precio.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from .. import indicators as ind
from .base import Strategy, frame


class FundingFadeShort(Strategy):
    """Corto cuando el funding marca largos saturados y el impulso se gira.

    Reglas:
      1. El funding esta en su percentil alto de las ultimas ``rank_lookback``
         barras **y** supera un suelo absoluto (evita disparar en un regimen
         de funding uniformemente bajo, donde el percentil enganaria).
      2. Barra de giro: cierre por debajo de la apertura. Sin esto estariamos
         vendiendo en plena euforia, que es como se arruina un corto.
      3. Salida cuando el funding se normaliza: la multitud ya se ha ido y el
         motivo de la operacion ha desaparecido.
    """

    def __init__(self, **params):
        super().__init__(
            name="funding_fade_short",
            family="cripto",
            thesis="Funding extremo = largos apalancados saturados; el corto cobra carry mientras espera.",
            params={
                "rank_lookback": 90,
                "funding_pctile": 0.90,
                # Suelo absoluto: 0,05% diario ~ 18% anualizado pagado por los largos.
                "min_funding_daily": 0.0005,
                "exit_pctile": 0.50,
                "atr_period": 14,
                "stop_atr": 2.0,
                "target_atr": 3.0,
                "max_bars": 10,
                **params,
            },
        )

    def _signals(self, df: pd.DataFrame, benchmark: Optional[pd.Series]) -> pd.DataFrame:
        p = self.params
        a = ind.atr(df, p["atr_period"])
        if "funding_rate" not in df.columns:
            # Sin el dato que da sentido a la tesis, no se opera.
            return frame(df.index, entry=False, atr=a)

        funding = df["funding_rate"]
        rank = funding.rolling(p["rank_lookback"], min_periods=p["rank_lookback"]).rank(pct=True)

        crowded = (rank >= p["funding_pctile"]) & (funding >= p["min_funding_daily"])
        turn = df["close"] < df["open"]

        entry = crowded & turn
        exit_ = rank <= p["exit_pctile"]
        return frame(
            df.index,
            entry=entry,
            exit=exit_,
            atr=a,
            stop_atr=p["stop_atr"],
            target_atr=p["target_atr"],
            max_bars=p["max_bars"],
        )


class OpenInterestFlushShort(Strategy):
    """Interes abierto creciendo con el precio, y el precio se gira.

    Si el open interest sube a la vez que el precio, las posiciones nuevas son
    mayoritariamente largas. Cuando el precio pierde el minimo reciente, esas
    posiciones entran en zona de liquidacion y su cierre forzado empuja el
    precio a la baja: una cascada auto-alimentada.

    Requiere la columna ``open_interest``.
    """

    def __init__(self, **params):
        super().__init__(
            name="oi_flush_short",
            family="cripto",
            thesis="Apalancamiento largo acumulado + perdida de soporte = cascada de liquidaciones.",
            params={
                "oi_lookback": 10,
                "min_oi_growth": 0.10,
                "min_price_run": 0.05,
                "trigger_lookback": 5,
                "atr_period": 14,
                "stop_atr": 1.5,
                "target_atr": 3.0,
                "max_bars": 8,
                **params,
            },
        )

    def _signals(self, df: pd.DataFrame, benchmark: Optional[pd.Series]) -> pd.DataFrame:
        p = self.params
        a = ind.atr(df, p["atr_period"])
        if "open_interest" not in df.columns:
            return frame(df.index, entry=False, atr=a)

        oi_growth = df["open_interest"].pct_change(p["oi_lookback"])
        price_run = df["close"].pct_change(p["oi_lookback"])
        low_ch, _ = ind.donchian(df, p["trigger_lookback"])

        # Apalancamiento largo acumulandose: OI y precio suben juntos.
        crowded_longs = (oi_growth >= p["min_oi_growth"]) & (price_run >= p["min_price_run"])
        breakdown = df["close"] < low_ch

        entry = crowded_longs & breakdown
        return frame(
            df.index,
            entry=entry,
            atr=a,
            stop_atr=p["stop_atr"],
            target_atr=p["target_atr"],
            max_bars=p["max_bars"],
        )


class OpenInterestDeleverageShort(Strategy):
    """Corto cuando el apalancamiento se esta destruyendo, no cuando se acumula.

    La diferencia con ``OpenInterestFlushShort`` -que mira interes abierto
    acumulandose y luego una rotura- es de tiempo verbal: aquella busca un
    estado ya formado, esta busca un proceso en marcha.

    Reglas (docs/12-oi-flush-short.md, seccion 2):
      1. La variacion diaria del interes abierto esta en su percentil inferior
         de las ultimas ``rank_lookback`` barras: se estan cerrando posiciones
         en masa.
      2. El precio cae ese mismo dia (``close < open``). Sin esta condicion la
         señal mezcla dos causas opuestas: interes abierto cayendo con el
         precio SUBIENDO son cortos cubriendo, que es el proceso contrario.

    Requiere la columna ``open_interest``. Sin ella no genera señales, igual
    que ``FundingFadeShort`` sin funding: aproximarla con el precio seria
    inventar justo la parte que hace distinta a la hipotesis.
    """

    def __init__(self, **params):
        super().__init__(
            name="oi_deleverage_short",
            family="cripto",
            thesis="Liquidacion forzada en curso: la cola de liquidaciones no se vacia dentro de la barra.",
            params={
                "percentile": 0.10,
                "rank_lookback": 180,
                "atr_period": 14,
                "stop_atr": 2.0,
                "target_atr": 3.0,
                "max_bars": 10,
                **params,
            },
        )

    def _signals(self, df: pd.DataFrame, benchmark: Optional[pd.Series]) -> pd.DataFrame:
        p = self.params
        a = ind.atr(df, p["atr_period"])
        if "open_interest" not in df.columns:
            return frame(df.index, entry=False, atr=a)

        cambio = df["open_interest"].pct_change()
        rango = cambio.rolling(p["rank_lookback"], min_periods=p["rank_lookback"]).rank(pct=True)
        desplome = (rango <= p["percentile"]).fillna(False)
        precio_cae = df["close"] < df["open"]

        return frame(
            df.index,
            entry=desplome & precio_cae,
            atr=a,
            stop_atr=p["stop_atr"],
            target_atr=p["target_atr"],
            max_bars=p["max_bars"],
        )
