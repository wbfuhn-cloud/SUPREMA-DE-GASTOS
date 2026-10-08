"""Fusión determinista, explicable y consciente de riesgo para Inversiones IA 3.0."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from typing import Any, Iterable


FUSION_VERSION = "1.0.0"
VALID_STATES = {"COMPRAR", "ESPERAR", "MANTENER", "REDUCIR", "SALIR", "SIN SEÑAL"}
MINIMUM_DATA_QUALITY = 0.90


@dataclass(frozen=True)
class FusionInput:
    symbol: str
    horizon: str
    heuristic_score: float
    heuristic_state: str
    data_quality: float
    regime: str
    price: float
    atr: float
    capital: float = 10_000.0
    has_position: bool = False
    calibrated_prob_up: float | None = None
    calibrated_prob_down: float | None = None
    model_approved: bool = False
    ml_ood: bool = False
    spectral_score: float | None = None
    spectral_validated: bool = False
    round_trip_cost: float = 0.0015
    uncertainty_penalty: float = 0.005
    expected_return: float | None = None
    stop_triggered: bool = False
    trailing_stop_triggered: bool = False
    profit_take_triggered: bool = False
    position_concentration: float = 0.0
    aggregate_open_risk: float = 0.0
    leveraged_etf: bool = False
    risk_pct: float = 0.01


def _finite(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _risk_plan(data: FusionInput) -> dict[str, Any]:
    risk_pct = min(max(float(data.risk_pct), 0.005), 0.01)
    stop_distance = max(2.0 * data.atr, data.price * 0.005)
    stop = max(0.01, data.price - stop_distance)
    max_loss = data.capital * risk_pct
    shares_by_risk = int(max_loss / stop_distance)
    shares_by_capital = int(data.capital / data.price)
    shares = max(0, min(shares_by_risk, shares_by_capital))
    return {
        "position_size_shares": shares,
        "entry_price": round(data.price, 4),
        "stop_price": round(stop, 4),
        "maximum_loss": round(shares * stop_distance, 2),
        "risk_budget": round(max_loss, 2),
        "risk_pct": risk_pct,
        "horizon": data.horizon,
    }


def fuse_signal(data: FusionInput) -> dict[str, Any]:
    """Produce exactamente un estado final y una explicación completa."""
    favorable: list[str] = []
    adverse: list[str] = []
    invalidation: list[str] = []
    risk_plan = None
    spectral_adjustment = float(data.spectral_score or 0.0) if data.spectral_validated else 0.0
    volatility_floor = 0.25 * data.atr / data.price if _finite(data.price) and data.price > 0 and _finite(data.atr) else math.inf
    minimum_edge = max(data.round_trip_cost * 2.0, volatility_floor)
    expected = data.expected_return
    if expected is None and data.calibrated_prob_up is not None:
        expected = (data.calibrated_prob_up - 0.5) * (data.atr / data.price) * 2.0
    buy_edge = None if expected is None else expected + spectral_adjustment - data.round_trip_cost - data.uncertainty_penalty

    if data.data_quality < MINIMUM_DATA_QUALITY:
        state = "SIN SEÑAL"
        adverse.append(f"calidad de datos {data.data_quality:.1%} menor al {MINIMUM_DATA_QUALITY:.0%}")
    elif data.ml_ood:
        state = "SIN SEÑAL"
        adverse.append("entrada fuera de distribución del modelo")
    elif not (_finite(data.price) and data.price > 0 and _finite(data.atr) and data.atr > 0):
        state = "SIN SEÑAL"
        adverse.append("precio o ATR no disponible")
    elif data.stop_triggered or data.trailing_stop_triggered:
        state = "SALIR" if data.has_position else "SIN SEÑAL"
        adverse.append("stop de riesgo activado")
    elif data.has_position and data.calibrated_prob_down is not None and data.calibrated_prob_down >= 0.60:
        state = "SALIR"
        adverse.append(f"probabilidad calibrada de caída {data.calibrated_prob_down:.1%}")
    elif data.has_position and (data.aggregate_open_risk > 0.05 or data.position_concentration > 0.25):
        state = "REDUCIR"
        adverse.append("riesgo agregado o concentración excede el límite")
    elif data.has_position and data.profit_take_triggered:
        state = "REDUCIR"
        adverse.append("objetivo de toma parcial de ganancias activado")
    elif data.has_position and data.regime == "crisis":
        state = "REDUCIR"
        adverse.append("régimen de crisis: reducir exposición")
    elif data.has_position and data.heuristic_score <= -0.50:
        state = "SALIR"
        adverse.append("deterioro heurístico severo")
    elif data.has_position and data.heuristic_score <= -0.15:
        state = "REDUCIR"
        adverse.append("edge heurístico deteriorado")
    else:
        eligible_buy = (
            data.model_approved and data.calibrated_prob_up is not None
            and data.calibrated_prob_up >= 0.65 and buy_edge is not None
            and buy_edge > minimum_edge and data.heuristic_score > 0
            and data.regime not in {"bajista", "crisis"}
            and data.aggregate_open_risk + min(max(data.risk_pct, 0.005), 0.01) <= 0.05
            and not data.leveraged_etf
        )
        if eligible_buy:
            state = "MANTENER" if data.has_position else "COMPRAR"
            favorable.extend([
                f"probabilidad calibrada al alza {data.calibrated_prob_up:.1%}",
                f"edge neto {buy_edge:.4f} superior al mínimo {minimum_edge:.4f}",
                f"heurística favorable {data.heuristic_score:+.3f}",
            ])
            if state == "COMPRAR":
                risk_plan = _risk_plan(data)
                if risk_plan["position_size_shares"] <= 0:
                    state = "SIN SEÑAL"
                    adverse.append("capital insuficiente para respetar el riesgo")
                    risk_plan = None
        elif data.has_position:
            state = "MANTENER"
            favorable.append("posición sin gatillo confirmado de salida")
            if not data.model_approved:
                adverse.append("modelo ML no aprobado; decisión limitada a riesgo y heurística")
        else:
            state = "ESPERAR"
            adverse.append("no existe probabilidad calibrada y edge suficiente para comprar")
            if data.leveraged_etf:
                adverse.append("ETF apalancado: no se permite compra estructural")

    if not data.spectral_validated:
        adverse.append("Fourier experimental excluido del veredicto")
    invalidation.extend([
        f"invalidar si la calidad de datos cae por debajo de {MINIMUM_DATA_QUALITY:.0%}",
        "invalidar ante stop, cambio de régimen o exceso de riesgo",
    ])
    if state in {"COMPRAR", "MANTENER"}:
        invalidation.append("invalidar si la probabilidad de caída alcanza 60%")
    if not favorable:
        favorable.append("ningún factor favorable suficiente")
    if not adverse:
        adverse.append("sin factores adversos materiales")
    payload = {
        "fusion_version": FUSION_VERSION,
        "symbol": data.symbol.upper(),
        "horizon": data.horizon,
        "state": state,
        "factors_for": favorable,
        "factors_against": adverse,
        "invalidation_triggers": invalidation,
        "risk_plan": risk_plan,
        "buy_edge": None if buy_edge is None else round(float(buy_edge), 8),
        "minimum_edge": None if not math.isfinite(minimum_edge) else round(float(minimum_edge), 8),
        "spectral_used": bool(data.spectral_validated),
        "model_used": bool(data.model_approved and not data.ml_ood),
    }
    canonical = json.dumps({"input": asdict(data), "output": payload}, sort_keys=True, separators=(",", ":"))
    payload["decision_hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return payload


def calibration_by_band(observations: Iterable[tuple[float, int]], width: float = 0.10) -> dict[str, Any]:
    rows = list(observations)
    bands = []
    calibrated = True
    for lower_index in range(int(1.0 / width)):
        lower = lower_index * width
        upper = min(1.0, lower + width)
        selected = [
            (prob, outcome) for prob, outcome in rows
            if (lower <= prob <= upper if upper == 1.0 else lower <= prob < upper)
        ]
        if not selected:
            continue
        predicted = sum(prob for prob, _ in selected) / len(selected)
        observed = sum(outcome for _, outcome in selected) / len(selected)
        error = abs(predicted - observed)
        calibrated = calibrated and error <= 0.05
        bands.append({"lower": lower, "upper": upper, "count": len(selected),
                      "predicted": predicted, "observed": observed, "absolute_error": error})
    return {"bands": bands, "all_within_5pp": calibrated and bool(bands)}
