"""El veto de aglomeracion: bloquea sin funding no lo hace, y con funding
extremo negativo si."""

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from shortbot.risk_filters import (
    aplicar_veto,
    amplitud_aglomeracion,
    veto_amplitud_mercado,
    veto_funding_crowding,
)


def test_sin_funding_no_veta_nada():
    idx = pd.bdate_range("2020-01-01", periods=200)
    df = pd.DataFrame({"close": 100.0}, index=idx)  # sin funding_rate
    v = veto_funding_crowding(df)
    assert not v.any()


def test_veta_solo_el_percentil_extremo_negativo():
    idx = pd.bdate_range("2020-01-01", periods=200)
    rng = np.random.default_rng(3)
    funding = pd.Series(rng.normal(0.0003, 0.0002, 200), index=idx)
    # Se fuerza un tramo de funding muy negativo al final: ahi SI debe vetar.
    funding.iloc[-5:] = -0.01
    df = pd.DataFrame({"close": 100.0, "funding_rate": funding}, index=idx)
    v = veto_funding_crowding(df, lookback=90, percentile=0.10)
    assert v.iloc[-5:].all()
    # En una zona sin nada forzado, un corte al percentil 10 veta ~10% de los
    # dias POR CONSTRUCCION (es ranking sobre ruido): pedir cero seria una
    # expectativa estadistica equivocada, no una propiedad del filtro.
    tasa = v.iloc[100:200].mean()
    assert 0.03 <= tasa <= 0.20


def test_aplicar_veto_solo_afecta_a_entry():
    idx = pd.bdate_range("2020-01-01", periods=10)
    signals = pd.DataFrame({"entry": [True] * 10, "atr": 1.0}, index=idx)
    df = pd.DataFrame({"close": 100.0}, index=idx)
    veto = pd.Series([True] * 5 + [False] * 5, index=idx)
    out = aplicar_veto(signals, df, veto)
    assert list(out["entry"]) == [False] * 5 + [True] * 5
    assert (out["atr"] == 1.0).all()  # el resto de columnas no se toca


def test_amplitud_aglomeracion_es_la_media_del_veto_por_activo():
    idx = pd.bdate_range("2020-01-01", periods=150)
    rng = np.random.default_rng(7)
    universo = {}
    for nombre in ["A", "B", "C", "D"]:
        funding = pd.Series(rng.normal(0.0003, 0.0002, 150), index=idx)
        universo[nombre] = pd.DataFrame({"close": 100.0, "funding_rate": funding}, index=idx)
    amplitud = amplitud_aglomeracion(universo, lookback=90, percentile=0.10)
    esperado = pd.concat(
        [veto_funding_crowding(df, lookback=90, percentile=0.10) for df in universo.values()],
        axis=1,
    ).mean(axis=1)
    pd.testing.assert_series_equal(amplitud, esperado, check_names=False)


def test_veto_amplitud_mercado_umbral():
    idx = pd.bdate_range("2020-01-01", periods=5)
    amplitud = pd.Series([0.05, 0.15, 0.25, 0.35, 0.50], index=idx)
    v = veto_amplitud_mercado(amplitud, umbral=0.25)
    assert list(v) == [False, False, True, True, True]


def test_veto_amplitud_mercado_es_universal_no_selectivo():
    # Un dia con amplitud alta veta TODOS los activos por igual, no solo al
    # que "dispara" la amplitud -es justo la diferencia con docs/07.
    idx = pd.bdate_range("2020-01-01", periods=10)
    amplitud = pd.Series([0.5] * 10, index=idx)
    veto = veto_amplitud_mercado(amplitud, umbral=0.3)
    df_cualquiera = pd.DataFrame({"close": 100.0}, index=idx)
    signals = pd.DataFrame({"entry": [True] * 10, "atr": 1.0}, index=idx)
    out = aplicar_veto(signals, df_cualquiera, veto)
    assert not out["entry"].any()
