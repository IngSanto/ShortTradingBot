"""Contrato comun de las estrategias.

Una estrategia solo decide *cuando* ponerse corto y con que distancia de stop
en unidades de ATR. El tamano de la posicion, los costes y la ejecucion son
responsabilidad del motor: asi todas las estrategias son comparables entre si.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import pandas as pd


@dataclass
class Strategy:
    """Clase base. Las subclases implementan ``_signals``."""

    name: str = "base"
    family: str = "sin_clasificar"
    thesis: str = ""
    params: dict[str, Any] = field(default_factory=dict)

    def generate_signals(
        self, df: pd.DataFrame, benchmark: Optional[pd.Series] = None
    ) -> pd.DataFrame:
        sig = self._signals(df, benchmark)
        required = {"entry", "atr"}
        missing = required - set(sig.columns)
        if missing:
            raise ValueError(f"{self.name}: la senal no incluye {sorted(missing)}")
        sig["entry"] = sig["entry"].fillna(False).astype(bool)
        # Cinturon de seguridad: sin ATR valido no hay dimensionamiento posible.
        sig.loc[~(sig["atr"] > 0), "entry"] = False
        return sig

    def _signals(self, df: pd.DataFrame, benchmark: Optional[pd.Series]) -> pd.DataFrame:
        raise NotImplementedError

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "family": self.family,
            "thesis": self.thesis,
            "params": dict(self.params),
        }

    def with_params(self, **overrides) -> "Strategy":
        """Copia con parametros cambiados: la base del barrido de robustez."""
        clone = self.__class__()
        clone.params = {**self.params, **overrides}
        return clone


def frame(index, **columns) -> pd.DataFrame:
    """Atajo para construir el DataFrame de senales."""
    return pd.DataFrame(columns, index=index)
