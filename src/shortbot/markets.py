"""Perfiles de mercado.

La misma estrategia no cuesta lo mismo en acciones que en perpetuos de cripto.
Y en el lado corto esa diferencia no es un matiz: es la que decide si un sistema
es rentable o no. Estos perfiles centralizan los supuestos para que ninguna
comparacion entre mercados se haga con costes de otro.

Los valores son puntos de partida razonables, NO verdades. En cuanto haya datos
reales hay que sustituirlos por los del broker/exchange concreto: sobre todo el
coste de prestamo en acciones y el funding en cripto.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .backtest import BacktestConfig, CostModel


@dataclass(frozen=True)
class MarketProfile:
    key: str
    nombre: str
    periods_per_year: int
    costs: CostModel
    universo_sugerido: tuple[str, ...]
    fuente: str
    notas: str

    def config(self, risk_per_trade: float = 0.01, **overrides) -> BacktestConfig:
        return BacktestConfig(
            risk_per_trade=risk_per_trade,
            costs=self.costs,
            **overrides,
        )


# --------------------------------------------------------------------------- #
# Acciones: la deriva alcista y el prestamo juegan en contra del corto.
# --------------------------------------------------------------------------- #
ACCIONES_US = MarketProfile(
    key="acciones",
    nombre="Acciones EEUU (liquidas)",
    periods_per_year=252,
    costs=CostModel(
        commission_bps=1.0,      # brokers con comision cero: queda el spread
        slippage_bps=5.0,
        borrow_annual_pct=3.0,   # valor liquido; un 'hard to borrow' pasa de 50%
        periods_per_year=252,
    ),
    universo_sugerido=(
        "SPY", "QQQ", "IWM", "XLF", "XLE",
        "AAPL", "MSFT", "NVDA", "TSLA", "AMD",
        "META", "AMZN", "COIN", "PLTR", "SMCI",
    ),
    fuente="yfinance",
    notas=(
        "Riesgo de hueco nocturno, uptick rule, recall del prestamo y "
        "prohibiciones de cortos en panicos. El coste de prestamo sube justo "
        "cuando el corto es mas atractivo."
    ),
)

# --------------------------------------------------------------------------- #
# Cripto perpetuos: el unico mercado donde el tiempo puede jugar A FAVOR
# del corto, porque con funding positivo son los largos quienes pagan.
# --------------------------------------------------------------------------- #
CRIPTO_PERP = MarketProfile(
    key="cripto",
    nombre="Cripto perpetuos",
    periods_per_year=365,        # 24/7: no hay dias no habiles
    costs=CostModel(
        commission_bps=4.5,      # taker; con maker se reduce mucho
        slippage_bps=5.0,
        # NEGATIVO = ingreso: con funding positivo, el corto COBRA por mantener
        # la posicion. Ya no es un supuesto: es la mediana medida sobre 10
        # perpetuos de Binance entre 2020 y 2026 (+9,2% anual, positivo el
        # 70-88% de los dias). Se usa la MEDIANA y no la media porque eventos
        # como el colapso de FTX (-17% de funding diario en SOL) distorsionan
        # la media hasta dejarla en cero.
        # Excepcion medida: BNBUSDT publica funding cero la mayoria de los dias.
        borrow_annual_pct=-9.2,
        periods_per_year=365,
    ),
    universo_sugerido=(
        "BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT", "BNB/USDT:USDT",
        "XRP/USDT:USDT", "DOGE/USDT:USDT", "AVAX/USDT:USDT", "LINK/USDT:USDT",
    ),
    fuente="ccxt (binance/bybit)",
    notas=(
        "Sin huecos (24/7) y sin restricciones regulatorias al corto. A cambio: "
        "riesgo de contraparte del exchange y liquidaciones en cascada que "
        "mueven el precio mucho mas de lo que justifica el flujo real."
    ),
)

# --------------------------------------------------------------------------- #
# Futuros: coste de estar corto practicamente nulo y sin restricciones.
# --------------------------------------------------------------------------- #
FUTUROS = MarketProfile(
    key="futuros",
    nombre="Futuros (indices y materias primas)",
    periods_per_year=252,
    costs=CostModel(
        commission_bps=1.0,
        slippage_bps=3.0,
        borrow_annual_pct=0.0,   # no hay prestamo: el coste va en la base
        periods_per_year=252,
    ),
    universo_sugerido=(
        "ES=F", "NQ=F", "YM=F", "RTY=F",      # indices
        "CL=F", "NG=F", "GC=F", "SI=F", "HG=F",  # materias primas
        "ZB=F", "ZN=F",                        # tipos
    ),
    fuente="yfinance (continuos)",
    notas=(
        "Estar corto es simetrico a estar largo: sin prestamo, sin recall y sin "
        "uptick rule. El riesgo se concentra en el apalancamiento implicito y en "
        "los huecos de fin de semana en energia."
    ),
)

MERCADOS: dict[str, MarketProfile] = {
    p.key: p for p in (ACCIONES_US, CRIPTO_PERP, FUTUROS)
}


def get_market(key: str) -> MarketProfile:
    if key not in MERCADOS:
        raise KeyError(f"Mercado desconocido '{key}'. Disponibles: {sorted(MERCADOS)}")
    return MERCADOS[key]
