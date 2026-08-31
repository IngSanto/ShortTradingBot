"""Filtros de riesgo transversales: vetan entradas, nunca las generan.

Se aplican DESPUES de que una estrategia decide que quiere entrar. La
diferencia con una estrategia es deliberada: un filtro de riesgo no necesita
demostrar que predice el retorno, solo que reduce el riesgo de cola sin
destruir la muestra ni hundir la expectativa. Ver docs/07-filtro-aglomeracion.md
para el diseño y el criterio de adopcion.
"""

from __future__ import annotations

import pandas as pd


def veto_funding_crowding(df: pd.DataFrame, lookback: int = 90, percentile: float = 0.10) -> pd.Series:
    """True donde una entrada nueva en corto deberia BLOQUEARSE.

    Funding en su percentil extremo negativo de los ultimos `lookback` dias
    significa que el lado corto de ese activo ya esta masificado (los cortos
    estan pagando a los largos): es el ingrediente de un apreton que jugaria
    en contra de abrir un corto mas ahi.

    Sin dato de funding, no se veta nada -no se puede evaluar el riesgo que
    no se puede medir, y negarlo por defecto seria inventar una razon.
    """
    if "funding_rate" not in df.columns:
        return pd.Series(False, index=df.index)
    rank = df["funding_rate"].rolling(lookback, min_periods=lookback).rank(pct=True)
    return (rank <= percentile).fillna(False)


def aplicar_veto(signals: pd.DataFrame, df: pd.DataFrame, veto: pd.Series) -> pd.DataFrame:
    """Aplica un veto (True = bloquear) sobre la columna 'entry' de las senales."""
    out = signals.copy()
    out["entry"] = out["entry"] & ~veto.reindex(out.index).fillna(False)
    return out
