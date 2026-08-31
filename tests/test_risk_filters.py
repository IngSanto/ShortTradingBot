"""El veto de aglomeracion: bloquea sin funding no lo hace, y con funding
extremo negativo si."""

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from shortbot.risk_filters import aplicar_veto, veto_funding_crowding


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
