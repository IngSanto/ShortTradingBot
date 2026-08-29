"""Pruebas de los perfiles de mercado y de la familia cripto."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from shortbot.data import synthetic_perp, synthetic_perp_universe
from shortbot.evaluation import evaluate_universe, run_strategy
from shortbot.markets import MERCADOS, get_market
from shortbot.strategies import build


def test_el_carry_de_cripto_es_un_ingreso_para_el_corto():
    """Es el supuesto central del perfil: en perpetuos el corto cobra funding."""
    assert get_market("cripto").costs.borrow_annual_pct < 0
    assert get_market("acciones").costs.borrow_annual_pct > 0
    assert get_market("futuros").costs.borrow_annual_pct == 0


def test_cripto_cuenta_365_barras_por_anio():
    """24/7: usar 252 subestimaria el carry acumulado en un tercio."""
    assert get_market("cripto").periods_per_year == 365
    assert get_market("acciones").periods_per_year == 252


def test_carry_negativo_suma_al_resultado_en_vez_de_restar():
    df = synthetic_perp(n=600, seed=4)
    strategy = build("donchian_breakdown")

    acciones = run_strategy(strategy, df, None, get_market("acciones").config())
    cripto = run_strategy(strategy, df, None, get_market("cripto").config())

    assert not acciones.trades.empty
    assert (acciones.trades["borrow_cost"] > 0).all()
    assert (cripto.trades["borrow_cost"] < 0).all()   # ingreso, no coste
    assert cripto.trades["pnl"].sum() > acciones.trades["pnl"].sum()


def test_las_estrategias_cripto_no_operan_sin_su_dato():
    """Sin funding ni open interest no hay tesis: no deben inventar senales."""
    from shortbot.data import synthetic_ohlcv

    plain = synthetic_ohlcv(n=800, seed=2)   # sin funding_rate ni open_interest
    for name in ("funding_fade_short", "oi_flush_short"):
        sig = build(name).generate_signals(plain, None)
        assert not sig["entry"].any(), f"{name} genero senales sin su dato"


def test_las_estrategias_cripto_si_operan_con_su_dato():
    uni = synthetic_perp_universe(4, n=1500)
    for name in ("funding_fade_short", "oi_flush_short"):
        out = evaluate_universe(build(name), uni, None, get_market("cripto").config())
        assert out["trades"] > 0, f"{name} no genero ninguna operacion"


def test_todos_los_perfiles_construyen_configuracion_valida():
    for key in MERCADOS:
        cfg = get_market(key).config(risk_per_trade=0.005)
        assert cfg.risk_per_trade == pytest.approx(0.005)
        assert cfg.costs.side_cost > 0
