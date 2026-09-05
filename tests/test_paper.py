"""El motor de papel debe producir las MISMAS operaciones que el backtest.

Es la propiedad que hace comparable la puerta 4 con las anteriores: si las
reglas divergieran, un paper peor que el backtest no diría nada sobre el
mercado, solo sobre la diferencia entre dos implementaciones.
"""

import json
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from shortbot.backtest import BacktestConfig, CostModel, ShortBacktester
from shortbot.data import synthetic_perp
from shortbot.paper import EstadoPapel, PaperBroker, resumen
from shortbot.strategies import build


def _config(**kw):
    return BacktestConfig(risk_per_trade=0.01,
                          costs=CostModel(4.5, 5.0, -9.2, 365), **kw)


@pytest.mark.parametrize("nombre", ["pullback_to_ema_short", "squeeze_breakdown"])
def test_el_papel_reproduce_las_operaciones_del_backtest(nombre):
    df = synthetic_perp(n=1500, seed=21)
    est = build(nombre)
    cfg = _config()

    back = ShortBacktester(cfg).run(df, est.generate_signals(df))

    # El papel arranca marcando la primera barra y avanza desde ahí, así que se
    # le da el mismo punto de partida que al backtest.
    estado = EstadoPapel(creado="test", equity_inicial=cfg.initial_equity,
                         equity=cfg.initial_equity)
    estado.ultima_barra[f"{nombre}|SYN"] = str(df.index[0])
    PaperBroker(cfg).procesar(estado, est, "SYN", df)

    papel = pd.DataFrame(estado.cerradas)
    assert not back.trades.empty, "el caso de prueba no genera operaciones"
    assert len(papel) == len(back.trades), (
        f"{nombre}: papel {len(papel)} operaciones, backtest {len(back.trades)}")

    for (_, a), (_, b) in zip(papel.iterrows(), back.trades.iterrows()):
        assert a["precio_entrada"] == pytest.approx(b["entry_price"], rel=1e-9)
        assert a["precio_salida"] == pytest.approx(b["exit_price"], rel=1e-9)
        assert a["motivo"] == b["reason"]
        assert a["barras"] == b["bars_held"]
        assert a["cantidad"] == pytest.approx(b["qty"], rel=1e-9)
        assert a["pnl"] == pytest.approx(b["pnl"], rel=1e-6)
        assert a["r_multiple"] == pytest.approx(b["r_multiple"], rel=1e-6)


def test_el_papel_no_opera_el_historico_en_el_primer_arranque():
    """Procesar todo el pasado en la primera ejecución sería un backtest
    disfrazado de paper: la primera pasada solo marca desde dónde contar."""
    df = synthetic_perp(n=800, seed=4)
    estado = EstadoPapel(creado="test", equity_inicial=100_000.0, equity=100_000.0)
    PaperBroker(_config()).procesar(estado, build("pullback_to_ema_short"), "SYN", df)

    assert estado.cerradas == []
    assert estado.abiertas == []
    assert estado.ultima_barra["pullback_to_ema_short|SYN"] == str(df.index[-1])


def test_el_retraso_de_ejecucion_se_respeta_en_papel():
    df = synthetic_perp(n=1200, seed=7)
    est = build("pullback_to_ema_short")
    resultados = {}
    for retraso in (0, 2):
        estado = EstadoPapel(creado="t", equity_inicial=100_000.0, equity=100_000.0)
        estado.ultima_barra[f"{est.name}|SYN"] = str(df.index[0])
        PaperBroker(_config(entry_delay_bars=retraso)).procesar(estado, est, "SYN", df)
        resultados[retraso] = pd.DataFrame(estado.cerradas)

    assert not resultados[0].empty and not resultados[2].empty
    # Con retraso, las entradas caen en fechas posteriores.
    assert (pd.to_datetime(resultados[2]["fecha_entrada"]).iloc[0]
            > pd.to_datetime(resultados[0]["fecha_entrada"]).iloc[0])


def test_el_resumen_no_falla_sin_operaciones():
    estado = EstadoPapel(creado="t", equity_inicial=100_000.0, equity=100_000.0)
    r = resumen(estado)
    assert r["operaciones"] == 0 and r["retorno"] == 0.0


def test_registrar_snapshot_es_idempotente_por_dia():
    """Correr paper_run dos veces el mismo día no debe duplicar el punto de
    la curva de equity: se reemplaza, no se acumula."""
    estado = EstadoPapel(creado="t", equity_inicial=100_000.0, equity=100_000.0)
    estado.registrar_snapshot("2026-08-31")
    estado.equity = 100_500.0
    estado.registrar_snapshot("2026-08-31")

    assert len(estado.historial) == 1
    assert estado.historial[0]["equity"] == 100_500.0

    estado.registrar_snapshot("2026-09-01")
    assert len(estado.historial) == 2


def test_cargar_completa_historial_para_estados_previos_a_esta_funcion():
    """state/paper.json ya existía en producción antes de que existiera
    'historial': cargar un estado antiguo no debe romperse por la clave
    ausente."""
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "paper.json")
        json.dump({"creado": "t", "equity_inicial": 100_000.0, "equity": 100_000.0},
                  open(path, "w"))
        estado = EstadoPapel.cargar(path)
        assert estado.historial == []


def test_el_snapshot_incluye_el_valor_de_lo_abierto():
    """La curva realizada es una escalera; la de mercado no.

    Sin esto, medir volatilidad o correlacion sobre el historial produce
    numeros que no corresponden al valor real de la cuenta -el 67% de los
    dias la curva realizada no se movia aunque hubiera 20 posiciones vivas.
    """
    from shortbot.paper import EstadoPapel

    e = EstadoPapel(creado="2026-01-01", equity_inicial=1000.0, equity=1000.0)
    e.abiertas = [{"estrategia": "x", "simbolo": "BTC", "precio_entrada": 100.0,
                   "cantidad": 2.0, "direccion": -1}]
    e.registrar_snapshot("2026-01-02", {"BTC": 90.0})   # corto ganando 10 por unidad
    p = e.historial[-1]
    assert p["equity"] == 1000.0                        # realizado intacto
    assert p["equity_mercado"] == 1020.0                # +2 x 10 de no realizado

    e.registrar_snapshot("2026-01-03", {"BTC": 110.0})  # ahora el corto pierde
    assert e.historial[-1]["equity_mercado"] == 980.0

    e.registrar_snapshot("2026-01-04")                  # sin precios: no inventa
    assert e.historial[-1]["equity_mercado"] == 1000.0


def test_la_configuracion_sobrevive_al_guardado(tmp_path):
    """Un registro sin procedencia no sirve para nada.

    `guardar` usa asdict(), que solo serializa CAMPOS del dataclass: si
    `configuracion` se pusiera como atributo suelto se perderia al escribir
    sin dar ningun error, y el registro nuevo pareceria estar declarando su
    sistema sin declararlo.
    """
    path = tmp_path / "paper.json"
    EstadoPapel(creado="2026-01-01T00:00:00+00:00", equity_inicial=1000.0, equity=1000.0,
                configuracion={"estrategias": ["a", "b"], "filtro_eventos_macro": True}
                ).guardar(str(path))

    assert json.loads(path.read_text())["configuracion"]["estrategias"] == ["a", "b"]
    # Y un estado anterior a que el campo existiera tiene que seguir cargando.
    path.write_text(json.dumps({"creado": "x", "equity_inicial": 1.0, "equity": 1.0}))
    assert EstadoPapel.cargar(str(path)).configuracion == {}
