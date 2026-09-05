"""El veto de aglomeracion: bloquea sin funding no lo hace, y con funding
extremo negativo si."""

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from shortbot.backtest import BacktestConfig
from shortbot.data import synthetic_perp
from shortbot.paper import EstadoPapel, PaperBroker
from shortbot.strategies import build
from shortbot.risk_filters import (
    ventana_eventos,
    veto_evento_macro,
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


# --- Filtro de eventos macro (docs/10) ------------------------------------- #


def test_ventana_eventos_se_expande_en_dias_de_calendario():
    idx = pd.date_range("2026-01-01", periods=20, freq="D")
    v = ventana_eventos(idx, ["2026-01-10"], dias_antes=1, dias_despues=1)
    assert list(idx[v].strftime("%Y-%m-%d")) == ["2026-01-09", "2026-01-10", "2026-01-11"]


def test_ventana_eventos_ignora_eventos_fuera_del_indice():
    idx = pd.date_range("2026-01-01", periods=5, freq="D")
    v = ventana_eventos(idx, ["2030-06-01"], dias_antes=2, dias_despues=2)
    assert not v.any()


def test_veto_macro_se_desplaza_con_el_retraso_de_entrada():
    """El veto va sobre la señal, pero apunta a donde caeria la ENTRADA."""
    idx = pd.date_range("2026-01-01", periods=20, freq="D")
    ventana = ventana_eventos(idx, ["2026-01-10"], 0, 0)

    # Sin retraso: la senal de i entra en i+1, asi que se veta la vispera.
    v0 = veto_evento_macro(idx, ["2026-01-10"], 0, 0, retraso_entrada=0)
    assert list(idx[v0].strftime("%Y-%m-%d")) == ["2026-01-09"]

    # Con un dia de retraso (el del paper diario), dos barras antes.
    v1 = veto_evento_macro(idx, ["2026-01-10"], 0, 0, retraso_entrada=1)
    assert list(idx[v1].strftime("%Y-%m-%d")) == ["2026-01-08"]

    # Y en ningun caso coincide con la ventana sin desplazar: si coincidiera,
    # el filtro estaria vetando el dia equivocado sin dar ningun error.
    assert not (v0 & ventana).any()


def test_ninguna_entrada_cae_dentro_de_la_ventana_de_evento():
    """La prueba que de verdad importa: se corre el backtest y se comprueba
    que no queda ni una entrada dentro de la ventana. Un desplazamiento mal
    puesto no rompe nada -solo protege los dias equivocados-, asi que se
    verifica contra el motor real, no contra la aritmetica del veto."""
    from shortbot.backtest import BacktestConfig, ShortBacktester

    idx = pd.date_range("2026-01-01", periods=120, freq="D")
    rng = np.random.default_rng(11)
    precio = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.02, 120))), index=idx)
    df = pd.DataFrame({"open": precio, "high": precio * 1.02,
                       "low": precio * 0.98, "close": precio}, index=idx)
    señales = pd.DataFrame({"entry": True, "atr": 2.0}, index=idx)
    eventos = ["2026-01-20", "2026-02-15", "2026-03-10"]

    for retraso in (0, 1, 2):
        cfg = BacktestConfig(entry_delay_bars=retraso)
        veto = veto_evento_macro(idx, eventos, 1, 1, retraso_entrada=retraso)
        res = ShortBacktester(cfg).run(df, aplicar_veto(señales, df, veto))
        ventana = ventana_eventos(idx, eventos, 1, 1)
        prohibidas = set(idx[ventana])
        assert not res.trades.empty, "sin operaciones no se prueba nada"
        assert not set(res.trades["entry_date"]) & prohibidas, f"retraso={retraso}"


def test_el_arranque_no_reporta_vetos_del_historico():
    """En la primera pasada `nuevas` es TODO el historico.

    Si el recuento de vetos corriera antes del corto-circuito de arranque,
    cada activo anunciaria las señales vetadas de años atras como "vetadas
    hoy". El numero seria correcto y la etiqueta falsa, que es justo como
    estos fallos sobreviven a una revision por encima.
    """
    df = synthetic_perp(n=400, seed=7)
    estado = EstadoPapel(creado="2026-01-01T00:00:00+00:00",
                         equity_inicial=100_000.0, equity=100_000.0)
    broker = PaperBroker(BacktestConfig(initial_equity=100_000.0))
    veto = pd.Series(True, index=df.index)          # el caso extremo: veta todo

    log = broker.procesar(estado, build("pullback_to_ema_short"), "TEST", df, veto)

    assert not any("vetadas hoy" in linea for linea in log), log
    assert any("arranque" in linea for linea in log), log
    # Y el arranque tiene que dejar marcado el punto de partida, no operar.
    assert estado.ultima_barra["pullback_to_ema_short|TEST"] == str(df.index[-1])
    assert estado.cerradas == [] and estado.abiertas == []
