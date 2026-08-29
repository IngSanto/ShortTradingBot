"""Catalogo de estrategias candidatas para operar en corto.

Cada entrada del registro es una hipotesis falsable, no una promesa. El objetivo
de la fase de laboratorio es *descartar* la mayoria.
"""

from .base import Strategy
from .crypto import FundingFadeShort, OpenInterestFlushShort
from .mean_reversion import (
    BollingerUpperFade,
    GapUpFade,
    ParabolicExtensionFade,
    RSI2Fade,
)
from .structure import (
    FailedBreakoutShort,
    SqueezeBreakdown,
    VolatilitySpikeExhaustion,
)
from .trend import DonchianBreakdown, PullbackToEMAShort, RelativeWeaknessShort

STRATEGY_REGISTRY: dict[str, type[Strategy]] = {
    "rsi2_fade": RSI2Fade,
    "gap_up_fade": GapUpFade,
    "parabolic_extension_fade": ParabolicExtensionFade,
    "bollinger_upper_fade": BollingerUpperFade,
    "donchian_breakdown": DonchianBreakdown,
    "pullback_to_ema_short": PullbackToEMAShort,
    "relative_weakness_short": RelativeWeaknessShort,
    "failed_breakout_short": FailedBreakoutShort,
    "squeeze_breakdown": SqueezeBreakdown,
    "volatility_spike_exhaustion": VolatilitySpikeExhaustion,
    # Familia cripto: requieren funding / open interest en el DataFrame.
    "funding_fade_short": FundingFadeShort,
    "oi_flush_short": OpenInterestFlushShort,
}


def build_all(**overrides) -> list[Strategy]:
    """Instancia todas las estrategias del registro con parametros por defecto."""
    return [cls(**overrides.get(key, {})) for key, cls in STRATEGY_REGISTRY.items()]


def build(name: str, **params) -> Strategy:
    if name not in STRATEGY_REGISTRY:
        raise KeyError(f"Estrategia desconocida '{name}'. Disponibles: {sorted(STRATEGY_REGISTRY)}")
    return STRATEGY_REGISTRY[name](**params)


__all__ = ["Strategy", "STRATEGY_REGISTRY", "build", "build_all"]
