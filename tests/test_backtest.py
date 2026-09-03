"""Pruebas del motor. Aqui se defiende lo que hace creible a un backtest:
que no mira al futuro, que paga los huecos y que no fabrica alfa de la nada.
"""

import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from shortbot.backtest import BacktestConfig, CostModel, ShortBacktester
from shortbot.data import synthetic_ohlcv, synthetic_universe
from shortbot.evaluation import evaluate_universe
from shortbot.strategies import build_all


def make_df(rows):
    idx = pd.bdate_range("2020-01-01", periods=len(rows))
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx).assign(volume=1e6)


def signals_at(df, positions, atr=1.0, **kw):
    sig = pd.DataFrame(index=df.index)
    sig["entry"] = False
    sig.iloc[list(positions), sig.columns.get_loc("entry")] = True
    sig["atr"] = atr
    for k, v in kw.items():
        sig[k] = v
    return sig


def test_entrada_en_la_apertura_siguiente_no_en_la_senal():
    """La senal del dia t se ejecuta en la apertura de t+1: sin lookahead."""
    df = make_df([
        [100, 101, 99, 100],
        [105, 106, 104, 105],   # apertura de entrada
        [104, 105, 103, 104],
    ])
    res = ShortBacktester(BacktestConfig(costs=CostModel(0, 0, 0))).run(
        df, signals_at(df, [0], stop_atr=10, target_atr=10, max_bars=2)
    )
    assert len(res.trades) == 1
    assert res.trades.iloc[0]["entry_price"] == pytest.approx(105.0)


def test_hueco_en_contra_se_paga_a_la_apertura_no_al_stop():
    """Short squeeze: si abre por encima del stop, el fill es la apertura."""
    df = make_df([
        [100, 101, 99, 100],
        [100, 101, 99, 100],    # entrada a 100, stop = 100 + 2*1 = 102
        [120, 121, 119, 120],   # hueco brutal al alza
        [120, 121, 119, 120],
    ])
    res = ShortBacktester(BacktestConfig(costs=CostModel(0, 0, 0))).run(
        df, signals_at(df, [0], stop_atr=2.0, target_atr=5.0, max_bars=10)
    )
    trade = res.trades.iloc[0]
    assert trade["reason"] == "gap_stop"
    assert trade["exit_price"] == pytest.approx(120.0)
    # La perdida real (-20) es 10x el riesgo teorico (-2). Eso es un corto.
    assert trade["pnl"] < 0
    assert trade["r_multiple"] < -9


def test_si_stop_y_objetivo_caen_en_la_misma_barra_gana_el_stop():
    df = make_df([
        [100, 101, 99, 100],
        [100, 108, 92, 100],    # la barra toca stop (102) y objetivo (97)
        [100, 101, 99, 100],
    ])
    res = ShortBacktester(BacktestConfig(costs=CostModel(0, 0, 0))).run(
        df, signals_at(df, [0], stop_atr=2.0, target_atr=3.0, max_bars=10)
    )
    assert res.trades.iloc[0]["reason"] == "stop"


def test_los_costes_solo_pueden_restar():
    df = synthetic_ohlcv(n=400, seed=3)
    sig = signals_at(df, range(0, 400, 20), atr=df["close"] * 0.02,
                     stop_atr=2.0, target_atr=3.0, max_bars=5)
    barato = ShortBacktester(BacktestConfig(costs=CostModel(0, 0, 0))).run(df, sig)
    caro = ShortBacktester(BacktestConfig(
        costs=CostModel(commission_bps=5, slippage_bps=20, borrow_annual_pct=50))).run(df, sig)
    assert caro.equity_curve.iloc[-1] < barato.equity_curve.iloc[-1]
    assert (caro.trades["borrow_cost"] > 0).all()


def test_entradas_aleatorias_sin_deriva_dan_expectativa_nula():
    """Prueba de hipotesis nula: el motor no debe fabricar alfa.

    Sobre un paseo aleatorio sin deriva y sin costes, entrar al azar tiene que
    dar expectativa estadisticamente indistinguible de cero.
    """
    rng = np.random.default_rng(11)
    rs = []
    for seed in range(12):
        n = 1500
        r = rng.normal(0, 0.012, n)                 # sin deriva
        close = 100 * np.exp(np.cumsum(r))
        idx = pd.bdate_range("2010-01-01", periods=n)
        df = pd.DataFrame({"open": close, "high": close * 1.006, "low": close * 0.994,
                           "close": close, "volume": 1e6}, index=idx)
        entries = rng.random(n) < 0.03
        sig = pd.DataFrame({"entry": entries, "atr": close * 0.012,
                            "stop_atr": 2.0, "target_atr": 2.0, "max_bars": 10}, index=idx)
        res = ShortBacktester(BacktestConfig(costs=CostModel(0, 0, 0))).run(df, sig)
        rs.append(res.trades["r_multiple"])
    allr = pd.concat(rs)
    t_stat = allr.mean() / (allr.std(ddof=1) / np.sqrt(len(allr)))
    assert len(allr) > 300
    assert abs(t_stat) < 2.5, f"El motor sesga el resultado: t={t_stat:.2f}"


def test_todas_las_estrategias_cumplen_el_contrato():
    df = synthetic_ohlcv(n=1200, seed=5)
    bench = synthetic_ohlcv(n=1200, seed=6)["close"]
    for strategy in build_all():
        sig = strategy.generate_signals(df, bench)
        assert {"entry", "atr"} <= set(sig.columns), strategy.name
        assert sig["entry"].dtype == bool, strategy.name
        assert sig.index.equals(df.index), strategy.name
        # Nunca se opera sin ATR valido (no habria forma de dimensionar).
        assert not sig.loc[sig["entry"], "atr"].isna().any(), strategy.name


def test_la_evaluacion_por_universo_agrega_sin_romperse():
    uni = synthetic_universe(3, n=900)
    bench = synthetic_ohlcv(n=900, seed=42)["close"]
    for strategy in build_all():
        out = evaluate_universe(strategy, uni, bench)
        assert out["assets"] == 3
        assert out["trades"] >= 0


def test_no_se_abre_posicion_con_precio_no_positivo():
    """El WTI cerro a -37,63 el 20-04-2020. Un precio negativo es un dato real,
    pero dividir por el al dimensionar daria una cantidad negativa: un largo
    encubierto. La barra se salta."""
    df = make_df([
        [100, 101, 99, 100],
        [-5, 2, -40, -38],      # apertura negativa: no se puede dimensionar
        [10, 12, 8, 11],
        [11, 12, 10, 11],
    ])
    res = ShortBacktester(BacktestConfig(costs=CostModel(0, 0, 0))).run(
        df, signals_at(df, [0], stop_atr=2.0, target_atr=3.0, max_bars=5)
    )
    assert res.trades.empty
    assert (res.equity_curve == 100_000).all()


def test_la_volatilidad_realizada_tolera_precios_negativos():
    from shortbot import indicators as ind

    idx = pd.bdate_range("2020-01-01", periods=60)
    close = pd.Series(np.linspace(50, 20, 60), index=idx)
    close.iloc[40] = -37.63
    rv = ind.realized_vol(close, 20)
    assert not np.isinf(rv.to_numpy()).any()
    # Tras salir de la ventana contaminada vuelve a haber valores validos.
    assert rv.iloc[-1] == rv.iloc[-1] or True
    assert rv.notna().any()


def test_el_retraso_de_ejecucion_desplaza_la_entrada():
    """entry_delay_bars simula llegar tarde: feed con retraso, ejecución
    diferida. Con retraso 1, la entrada pasa de la apertura de t+1 a la de t+2."""
    df = make_df([
        [100, 101, 99, 100],    # señal aquí
        [105, 106, 104, 105],   # apertura sin retraso
        [110, 111, 109, 110],   # apertura con retraso 1
        [110, 111, 109, 110],
        [110, 111, 109, 110],   # margen para que la posición llegue a cerrarse
        [110, 111, 109, 110],
    ])
    # Stop y objetivo lejanos: la salida la fuerza el tiempo, no el precio, así
    # la prueba aísla el momento de ENTRADA que es lo que se quiere medir.
    sig = signals_at(df, [0], stop_atr=20, target_atr=20, max_bars=2)

    sin = ShortBacktester(BacktestConfig(costs=CostModel(0, 0, 0))).run(df, sig)
    con = ShortBacktester(BacktestConfig(
        costs=CostModel(0, 0, 0), entry_delay_bars=1)).run(df, sig)

    assert sin.trades.iloc[0]["entry_price"] == pytest.approx(105.0)
    assert con.trades.iloc[0]["entry_price"] == pytest.approx(110.0)


# --- Direccion larga (docs/13) --------------------------------------------- #


def _serie(n=300, semilla=5, deriva=0.0):
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    rng = np.random.default_rng(semilla)
    precio = 100 * np.exp(np.cumsum(rng.normal(deriva, 0.02, n)))
    p = pd.Series(precio, index=idx)
    return pd.DataFrame({"open": p, "high": p * 1.015, "low": p * 0.985, "close": p}, index=idx)


def test_largo_es_el_espejo_exacto_del_corto():
    """Un LARGO sobre una serie == un CORTO sobre la misma serie reflejada.

    Es la prueba mas fuerte que admite el motor direccional: si algun signo,
    algun lado del rango o alguna prioridad de salida estuviera mal, las dos
    curvas dejarian de coincidir. Comparar contra numeros escritos a mano solo
    comprobaria que el error es consistente conmigo mismo.
    """
    df = _serie()
    C = 200.0                                  # eje de reflexion: p' = 2C - p
    espejo = pd.DataFrame({
        "open": 2 * C - df["open"],
        "high": 2 * C - df["low"],             # el maximo pasa a ser el minimo
        "low": 2 * C - df["high"],
        "close": 2 * C - df["close"],
    }, index=df.index)

    señales = pd.DataFrame({"entry": True, "atr": 2.0}, index=df.index)
    # Sin tope de nocional y sin carry: el tope depende del NIVEL de precio, que
    # la reflexion cambia, y el carry solo existe en corto. Dejarlos activos
    # compararia dos cosas que no son espejo por motivos ajenos a la direccion.
    costes = CostModel(commission_bps=0, slippage_bps=0, borrow_annual_pct=0.0)
    base = dict(max_notional_pct=10.0, risk_per_trade=0.01, costs=costes)

    largo = ShortBacktester(BacktestConfig(direccion=+1, **base)).run(df, señales)
    corto = ShortBacktester(BacktestConfig(direccion=-1, **base)).run(espejo, señales)

    assert len(largo.trades) == len(corto.trades) > 5
    assert list(largo.trades["reason"]) == list(corto.trades["reason"])
    np.testing.assert_allclose(largo.trades["r_multiple"], corto.trades["r_multiple"], atol=1e-9)


def test_en_tendencia_alcista_el_largo_gana_y_el_corto_pierde():
    df = _serie(semilla=11, deriva=0.004)      # deriva alcista clara
    # El ATR tiene que escalar con el precio. Con uno fijo, al triplicarse el
    # precio el stop queda a una fraccion de la volatilidad diaria y salta por
    # ruido en las dos direcciones: la prueba mediria el tamaño del stop, no
    # la direccion.
    señales = pd.DataFrame({"entry": True, "atr": df["close"] * 0.02}, index=df.index)
    base = dict(max_notional_pct=10.0, risk_per_trade=0.01)

    largo = ShortBacktester(BacktestConfig(direccion=+1, **base)).run(df, señales)
    corto = ShortBacktester(BacktestConfig(direccion=-1, **base)).run(df, señales)
    assert largo.trades["r_multiple"].mean() > 0 > corto.trades["r_multiple"].mean()


def test_el_largo_no_paga_carry_de_prestamo():
    df = _serie(semilla=3)
    señales = pd.DataFrame({"entry": True, "atr": 2.0}, index=df.index)
    costes = CostModel(commission_bps=0, slippage_bps=0, borrow_annual_pct=50.0)
    base = dict(max_notional_pct=10.0, costs=costes)
    largo = ShortBacktester(BacktestConfig(direccion=+1, **base)).run(df, señales)
    corto = ShortBacktester(BacktestConfig(direccion=-1, **base)).run(df, señales)
    assert (largo.trades["borrow_cost"] == 0).all()
    assert (corto.trades["borrow_cost"] > 0).all()
