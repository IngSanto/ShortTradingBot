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


def amplitud_aglomeracion(universo: dict[str, pd.DataFrame], lookback: int = 90,
                          percentile: float = 0.10) -> pd.Series:
    """Fraccion del universo con el corto masificado el mismo dia (docs/08).

    Por cada activo, mismo calculo por-activo que `veto_funding_crowding`
    (funding en su percentil extremo negativo de los ultimos `lookback`
    dias). Se promedia across activos: el resultado es una serie de mercado,
    no de un activo -un dia donde una porcion grande del universo tiene el
    lado corto masificado a la vez es la firma de un apreton en marcha, no
    de un activo aislado.
    """
    masificado = {}
    for simbolo, df in universo.items():
        masificado[simbolo] = veto_funding_crowding(df, lookback=lookback, percentile=percentile)
    tabla = pd.DataFrame(masificado)
    return tabla.mean(axis=1, skipna=True)


def ventana_eventos(index: pd.DatetimeIndex, fechas, dias_antes: int,
                    dias_despues: int) -> pd.Series:
    """True en las barras que caen a [-dias_antes, +dias_despues] de un evento.

    La ventana se expande en dias de CALENDARIO, no en posiciones del indice:
    asi sigue significando lo mismo si al indice le falta una barra.
    """
    eventos = pd.DatetimeIndex(pd.to_datetime(list(fechas))).normalize()
    dias = {f + pd.Timedelta(days=d)
            for f in eventos
            for d in range(-dias_antes, dias_despues + 1)}
    return pd.Series(index.normalize().isin(dias), index=index)


def veto_evento_macro(index: pd.DatetimeIndex, fechas, dias_antes: int,
                      dias_despues: int, retraso_entrada: int = 0) -> pd.Series:
    """Veto de eventos macro, devuelto sobre la fila de SEÑAL (docs/10, seccion 1.1).

    Lo que se quiere evitar es tener la posicion ABIERTA durante el evento,
    y la entrada no ocurre en la barra de la senal: una senal en `i` se
    ejecuta en la apertura de `i + 1 + retraso_entrada` (backtest y paper
    comparten esta regla). Por eso la ventana se desplaza hacia atras esas
    barras antes de aplicarla.

    Devolver la ventana sin desplazar seria un error silencioso: vetaria
    entradas que caen justo FUERA del evento y dejaria pasar las que caen
    dentro -es decir, lo contrario de lo que dice hacer, sin fallar nunca.
    """
    ventana = ventana_eventos(index, fechas, dias_antes, dias_despues)
    return ventana.shift(-(1 + retraso_entrada), fill_value=False).astype(bool)


def veto_amplitud_mercado(amplitud: pd.Series, umbral: float) -> pd.Series:
    """True los dias donde la amplitud de aglomeracion supera `umbral`.

    A diferencia de `veto_funding_crowding` (por activo), este veto es el
    mismo para todo el universo ese dia: se aplica a cada activo por igual,
    no solo al que "dispara" la amplitud -el mecanismo es deliberadamente
    universal (docs/08, seccion 0-1).
    """
    return amplitud >= umbral
