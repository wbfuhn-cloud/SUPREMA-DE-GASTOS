"""
Módulo: ml_predictor.py
Descripción: Sistema de Machine Learning (GradientBoostingClassifier) para predecir
             la probabilidad de éxito de recomendaciones boursátiles en /bolsa.
Autor: Antigravity AI
Última modificación: 2026-09-05
Versión: 1.0
"""

import os
import sys
import json
import logging
import sqlite3
import math
import hashlib
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional

from ml_validation import OODProfile, audit_legacy_artifact, phase5_approval

import numpy as np
try:
    import joblib
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import Pipeline
    from sklearn.model_selection import TimeSeriesSplit
    from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

# Logging
log = logging.getLogger(__name__)

FEATURE_NAMES = [
    "score",
    "rsi",
    "macd",
    "macd_signal",
    "macd_hist",
    "bb_position",
    "bb_width_pct",
    "vol_ratio",
    "volatility_pct",
    "market_cap_log",
    "ind_rsi_optimal",
    "ind_trend_sma",
    "ind_macd_bullish",
    "ind_volume_high",
    "ind_bb_oversold",
    "ind_momentum_pos",
    "ind_support_bounce",
    "price_level_log"
]

MODEL_CONTRACT_VERSION = "5.0"


class StockMLPredictor:
    """
    Modelo de Machine Learning supervisado para clasificar la efectividad
    de recomendaciones de compra de acciones basadas en el histórico de learner.db.
    """

    def __init__(self, db_path: Optional[str] = None, model_path: Optional[str] = None):
        base_dir = Path(__file__).resolve().parent
        self.db_path = Path(db_path) if db_path else base_dir / "learner.db"
        self.model_path = Path(model_path) if model_path else base_dir / "stock_ml_model.joblib"
        
        self.model: Optional[Any] = None
        self.experimental_model: Optional[Any] = None
        self.metrics: Dict[str, Any] = {}
        self.last_trained: Optional[str] = None
        self.model_version = "unavailable"
        self.model_hash: Optional[str] = None
        self.ood_profile: Optional[OODProfile] = None
        self.production_approved = False
        self.degraded_reason = "model_not_loaded"
        self.audit: Dict[str, Any] = {}
        
        if SKLEARN_AVAILABLE and self.model_path.exists():
            self.load_model()

    def _extract_feature_vector(self, row: Dict[str, Any]) -> List[float]:
        """Extrae el vector de 18 características desde un diccionario o registro SQL."""
        score = float(row.get("score") or 0.0)
        rsi = float(row.get("rsi") or 50.0)
        macd = float(row.get("macd") or 0.0)
        macd_signal = float(row.get("macd_signal") or 0.0)
        macd_hist = float(row.get("macd_hist") or (macd - macd_signal))
        
        price = float(row.get("price_at_rec") or row.get("price") or 1.0)
        bb_upper = float(row.get("bb_upper") or price * 1.05)
        bb_lower = float(row.get("bb_lower") or price * 0.95)
        
        bb_denom = (bb_upper - bb_lower)
        bb_position = (price - bb_lower) / bb_denom if bb_denom > 1e-6 else 0.5
        bb_width_pct = bb_denom / price if price > 0 else 0.1
        
        vol_ratio = float(row.get("vol_ratio") or 1.0)
        volatility_pct = float(row.get("volatility_pct") or 0.02)
        market_cap = float(row.get("market_cap") or 1e9)
        market_cap_log = math.log10(max(market_cap, 1.0))
        price_level_log = math.log10(max(price, 0.01))
        
        # Parse active indicators
        active_ind = row.get("active_indicators") or []
        if isinstance(active_ind, str):
            try:
                active_ind = json.loads(active_ind)
            except Exception:
                active_ind = []
                
        ind_set = set(active_ind) if isinstance(active_ind, list) else set()
        
        ind_rsi_optimal = 1.0 if "rsi_optimal" in ind_set else 0.0
        ind_trend_sma = 1.0 if "trend_sma" in ind_set else 0.0
        ind_macd_bullish = 1.0 if "macd_bullish" in ind_set else 0.0
        ind_volume_high = 1.0 if "volume_high" in ind_set else 0.0
        ind_bb_oversold = 1.0 if "bb_oversold" in ind_set else 0.0
        ind_momentum_pos = 1.0 if "momentum_pos" in ind_set else 0.0
        ind_support_bounce = 1.0 if "support_bounce" in ind_set else 0.0
        
        return [
            score, rsi, macd, macd_signal, macd_hist,
            bb_position, bb_width_pct, vol_ratio, volatility_pct,
            market_cap_log, ind_rsi_optimal, ind_trend_sma,
            ind_macd_bullish, ind_volume_high, ind_bb_oversold,
            ind_momentum_pos, ind_support_bounce, price_level_log
        ]

    def fetch_training_dataset(self) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """Recupera registros verificados de learner.db y genera X e y."""
        if not self.db_path.exists():
            log.warning(f"Base de datos {self.db_path} no existe.")
            return np.array([]), np.array([]), []

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = """
            SELECT ticker, scan_date, score, price_at_rec, rsi, macd, macd_signal,
                   macd_hist, bb_upper, bb_lower, vol_ratio, volatility_pct,
                   market_cap, sector, active_indicators, verified, outcome, change_pct_1d
            FROM recommendations
            WHERE verified = 1 AND outcome IS NOT NULL
            ORDER BY scan_date ASC, id ASC
        """
        cursor.execute(query)
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()

        X_list = []
        y_list = []
        dates_list = []

        for r in rows:
            feat = self._extract_feature_vector(r)
            outcome = str(r.get("outcome") or "").upper()
            change_1d = float(r.get("change_pct_1d") or 0.0)
            
            # Criterio positivo: WIN u ganancia > 1.5%
            target = 1 if outcome == "WIN" or change_1d >= 1.5 else 0
            
            X_list.append(feat)
            y_list.append(target)
            dates_list.append(r.get("scan_date") or "")

        return np.array(X_list, dtype=np.float64), np.array(y_list, dtype=np.int32), dates_list

    def train_model(self) -> Dict[str, Any]:
        """Entrena el GradientBoostingClassifier usando TimeSeriesSplit."""
        if not SKLEARN_AVAILABLE:
            raise RuntimeError("scikit-learn o joblib no están instalados.")

        X, y, dates = self.fetch_training_dataset()
        if len(X) < 50:
            log.warning(f"Muestras insuficientes para entrenar: {len(X)} < 50.")
            return {"status": "error", "message": f"Datos insuficientes ({len(X)} muestras)"}

        log.info(f"Iniciando entrenamiento ML con {len(X)} muestras (Positivos: {int(np.sum(y))}).")

        # Pipeline con escalamiento y Gradient Boosting
        clf = Pipeline([
            ('scaler', StandardScaler()),
            ('gbm', GradientBoostingClassifier(
                n_estimators=150,
                learning_rate=0.03,
                max_depth=4,
                subsample=0.8,
                min_samples_split=15,
                min_samples_leaf=5,
                random_state=42
            ))
        ])

        # Validación cruzada temporal (TimeSeriesSplit)
        tscv = TimeSeriesSplit(n_splits=4)
        cv_precisions, cv_recalls, cv_f1s = [], [], []

        for train_idx, val_idx in tscv.split(X):
            X_train_cv, X_val_cv = X[train_idx], X[val_idx]
            y_train_cv, y_val_cv = y[train_idx], y[val_idx]
            
            # Ajustar pesos de clases si el conjunto de entrenamiento tiene positivos
            if np.sum(y_train_cv) > 0:
                sample_weights = np.where(y_train_cv == 1, (len(y_train_cv) - np.sum(y_train_cv)) / max(np.sum(y_train_cv), 1), 1.0)
                clf.fit(X_train_cv, y_train_cv, sample_weight=sample_weights)
            else:
                clf.fit(X_train_cv, y_train_cv)
                
            y_pred_cv = clf.predict(X_val_cv)
            cv_precisions.append(precision_score(y_val_cv, y_pred_cv, zero_division=0))
            cv_recalls.append(recall_score(y_val_cv, y_pred_cv, zero_division=0))
            cv_f1s.append(f1_score(y_val_cv, y_pred_cv, zero_division=0))

        # Entrenamiento final con todo el dataset
        sample_weights_full = np.where(y == 1, (len(y) - np.sum(y)) / max(np.sum(y), 1), 1.0)
        clf.fit(X, y, gbm__sample_weight=sample_weights_full)

        y_prob = clf.predict_proba(X)[:, 1]
        y_pred_full = (y_prob >= 0.5).astype(int)

        # Matriz e importancias de características (del paso GBM)
        gbm = clf.named_steps['gbm']
        feature_importances = dict(zip(FEATURE_NAMES, gbm.feature_importances_.round(4).tolist()))

        metrics = {
            "status": "success",
            "samples_total": len(X),
            "positive_cases": int(np.sum(y)),
            "positive_ratio_pct": round(float(np.mean(y) * 100), 2),
            "cv_precision_mean": round(float(np.mean(cv_precisions) * 100), 2),
            "cv_recall_mean": round(float(np.mean(cv_recalls) * 100), 2),
            "cv_f1_mean": round(float(np.mean(cv_f1s) * 100), 2),
            "full_precision": round(float(precision_score(y, y_pred_full, zero_division=0) * 100), 2),
            "auc_score": round(float(roc_auc_score(y, y_prob) * 100), 2) if len(np.unique(y)) > 1 else 50.0,
            "feature_importances": feature_importances,
            "trained_at": datetime.now().isoformat()
        }

        # El entrenamiento heredado no incluye calibración separada, benchmarks,
        # purga/embargo completa ni OOD. Se conserva solo como experimento.
        self.experimental_model = clf
        self.model = None
        self.production_approved = False
        self.degraded_reason = "training_pipeline_not_phase5_validated"
        self.metrics = metrics
        self.last_trained = metrics["trained_at"]

        self.save_model()
        log.info(f"Entrenamiento ML finalizado. Precisión CV: {metrics['cv_precision_mean']}%, Full Precision: {metrics['full_precision']}%")
        return metrics

    def save_model(self) -> None:
        """Guarda el modelo, escalador y métricas en disco."""
        payload = {
            "model": self.model or self.experimental_model,
            "metrics": self.metrics,
            "last_trained": self.last_trained,
            "feature_names": FEATURE_NAMES,
            "model_version": self.model_version,
            "phase5_validation": {"approved": False, "reason": self.degraded_reason},
        }
        joblib.dump(payload, self.model_path)
        log.info(f"Modelo ML guardado en {self.model_path}")

    def load_model(self) -> bool:
        """Carga artefactos, pero solo activa los que acreditan la fase 5."""
        if not SKLEARN_AVAILABLE or not self.model_path.exists():
            return False

        try:
            payload = joblib.load(self.model_path)
            candidate = payload.get("model")
            self.metrics = payload.get("metrics", {})
            self.last_trained = payload.get("last_trained")
            self.model_hash = hashlib.sha256(self.model_path.read_bytes()).hexdigest()
            self.model_version = str(payload.get("model_version") or "legacy-1.0")
            validation = payload.get("phase5_validation") or {}
            reconstructed = self._reconstructed_sample_count()
            self.audit = audit_legacy_artifact(self.metrics, reconstructed)
            if validation:
                approval = phase5_approval(validation)
                provenance_ok = int(validation.get("samples_total") or 0) == reconstructed
                self.production_approved = bool(approval["approved"] and provenance_ok)
                profile = payload.get("ood_profile") or {}
                if profile.get("lower") is not None and profile.get("upper") is not None:
                    self.ood_profile = OODProfile(np.asarray(profile["lower"]), np.asarray(profile["upper"]))
            if self.production_approved:
                self.model = candidate
                self.degraded_reason = ""
                log.info("Modelo ML fase 5 aprobado y cargado: %s", self.model_version)
            else:
                self.experimental_model = candidate
                self.model = None
                self.degraded_reason = "legacy_model_not_reproducible_or_unvalidated"
                log.warning("Modelo ML retenido solo como experimento: %s", self.audit.get("reasons"))
            return True
        except Exception as e:
            log.error(f"Error cargando modelo ML: {e}")
            return False

    def _reconstructed_sample_count(self) -> int:
        try:
            X, _y, _dates = self.fetch_training_dataset()
            return int(len(X))
        except Exception:
            return 0

    def predict_score(self, ticker_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dada la información técnica de una acción, retorna un diccionario con
        la predicción estructurada, la probabilidad, intervalos y top features.
        """
        result = {
            "ml_score": None,
            "probability": None,
            "model_prediction": None,
            "calibrated_probability": None,
            "model_version": self.model_version,
            "confidence_level": "NO DISPONIBLE",
            "feature_breakdown": {},
            "top_features": {},
            "buy_score": None,
            "exit_score": None,
            "ood_detected": False,
            "degraded_reason": self.degraded_reason,
            "source": "heuristic_fallback"
        }
        
        if not SKLEARN_AVAILABLE or self.model is None:
            return result

        try:
            feat_vec = self._extract_feature_vector(ticker_data)
            X_in = np.array([feat_vec], dtype=np.float64)
            expected_features = getattr(self.model, "n_features_in_", len(FEATURE_NAMES))
            if int(expected_features) != len(FEATURE_NAMES):
                result["degraded_reason"] = "model_feature_contract_mismatch"
                log.warning(
                    "Modelo ML incompatible: esperaba %s variables y el contrato actual entrega %s.",
                    expected_features,
                    len(FEATURE_NAMES),
                )
                return result
            if self.ood_profile is None:
                result["ood_detected"] = True
                result["degraded_reason"] = "ood_profile_missing"
                return result
            is_ood, indices = self.ood_profile.detect(X_in[0])
            if is_ood:
                result["ood_detected"] = True
                result["ood_features"] = [FEATURE_NAMES[index] for index in indices]
                result["degraded_reason"] = "out_of_distribution"
                return result
            proba_win = float(self.model.predict_proba(X_in)[0, 1])

            # Convertir probabilidad a ML Score (0 a 100)
            ml_score = round(proba_win * 100.0, 1)

            if proba_win >= 0.70:
                conf = "MUY ALTA"
            elif proba_win >= 0.60:
                conf = "ALTA"
            elif proba_win >= 0.45:
                conf = "MEDIA"
            else:
                conf = "BAJA"

            # Los artefactos históricos pueden ser un estimador directo; los
            # actuales normalmente son Pipeline. La explicación es compatible
            # con ambos formatos y nunca invalida una predicción correcta.
            named_steps = getattr(self.model, "named_steps", {})
            estimator = named_steps.get("gbm") if named_steps else self.model
            scaler = named_steps.get("scaler") if named_steps else None
            f_imp = getattr(estimator, "feature_importances_", None)
            explained_features = scaler.transform(X_in)[0] if scaler is not None else X_in[0]
            contributions = (
                explained_features * np.asarray(f_imp)
                if f_imp is not None and len(f_imp) == len(FEATURE_NAMES)
                else np.zeros(len(FEATURE_NAMES), dtype=np.float64)
            )

            top_indices = np.argsort(np.abs(contributions))[-3:][::-1] if np.any(contributions) else []
            breakdown = {}
            for idx in top_indices:
                feature = FEATURE_NAMES[idx]
                val = float(contributions[idx])
                breakdown[feature] = round(val, 4)

            return {
                "ml_score": ml_score,
                "probability": proba_win,
                "model_prediction": "BUY" if proba_win >= 0.5 else "NO_BUY",
                "calibrated_probability": proba_win,
                "model_version": self.model_version,
                "confidence_level": conf,
                "feature_breakdown": breakdown,
                "top_features": breakdown,
                "buy_score": ml_score,
                "exit_score": None,
                "ood_detected": False,
                "degraded_reason": "",
                "source": "validated_ml_model"
            }
        except Exception as e:
            log.error(f"Error prediciendo con modelo ML: {e}")
            return result

    def get_status(self) -> Dict[str, Any]:
        """Retorna el estado actual del modelo de Machine Learning."""
        return {
            "available": SKLEARN_AVAILABLE,
            "trained": self.model is not None,
            "production_approved": self.production_approved,
            "decision": "production" if self.production_approved else "experiment_only",
            "degraded_reason": self.degraded_reason,
            "model_version": self.model_version,
            "model_hash": self.model_hash,
            "last_trained": self.last_trained,
            "metrics": self.metrics,
            "phase5_audit": self.audit,
            "database_configured": self.db_path.exists(),
            "model_artifact": self.model_path.name
        }


# Instancia singleton para fácil reutilización
_predictor_instance: Optional[StockMLPredictor] = None
_predictor_lock = threading.Lock()


def get_ml_predictor() -> StockMLPredictor:
    global _predictor_instance
    if _predictor_instance is None:
        with _predictor_lock:
            if _predictor_instance is None:
                _predictor_instance = StockMLPredictor()
    return _predictor_instance
