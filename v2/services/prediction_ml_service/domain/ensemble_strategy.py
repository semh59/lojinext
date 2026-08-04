"""
Ensemble Strategy Pattern Implementation
Defines different strategies for weighting sub-models in the EnsemblePredictor.
"""

from abc import ABC, abstractmethod
from typing import Dict

from v2.modules.platform_infra.logging.logger import get_logger

logger = get_logger(__name__)


class EnsembleStrategy(ABC):
    """Abstract base class for ensemble weighting strategies."""

    @abstractmethod
    def calculate_weights(
        self, metrics: Dict[str, Dict[str, float]], available_models: list
    ) -> Dict[str, float]:
        """
        Calculate weights for each model based on the strategy.

        Args:
            metrics: Dictionary of metrics (like R2, MSE) for each trained model.
            available_models: List of model keys that were successfully trained.

        Returns:
            Dict containing weights for each target model. E.g., {'rf': 0.4, 'xgb': 0.6}
        """
        pass


class DynamicWeightStrategy(EnsembleStrategy):
    """
    Assigns weights dynamically based on R2 scores from cross-validation.
    This is the default AI-driven strategy.
    """

    def calculate_weights(
        self, metrics: Dict[str, Dict[str, float]], available_models: list
    ) -> Dict[str, float]:
        weights: Dict[str, float] = {}
        total_r2 = 0.0
        r2_scores = {}

        # Safely extract R2 scores
        for model_name in available_models:
            if model_name in metrics and "r2" in metrics[model_name]:
                r2 = max(
                    0.01, metrics[model_name]["r2"]
                )  # Prevent negative/zero weights
                r2_scores[model_name] = r2
                total_r2 += r2
            else:
                r2_scores[model_name] = 0.01  # Minimum baseline weight
                total_r2 += 0.01

        if total_r2 > 0:
            for m in r2_scores:
                weights[m] = r2_scores[m] / total_r2
        else:
            # Fallback if everything is 0
            for m in available_models:
                weights[m] = 1.0 / len(available_models)

        logger.info(f"DynamicWeightStrategy calculated weights: {weights}")
        return weights


class EqualWeightStrategy(EnsembleStrategy):
    """
    Assigns equal weights to all available models.
    Useful for simple mean ensembling.
    """

    def calculate_weights(
        self, metrics: Dict[str, Dict[str, float]], available_models: list
    ) -> Dict[str, float]:
        weights: Dict[str, float] = {}
        if not available_models:
            return weights

        weight_val = 1.0 / len(available_models)
        for m in available_models:
            weights[m] = weight_val

        logger.info(f"EqualWeightStrategy calculated weights: {weights}")
        return weights


class PhysicsFirstStrategy(EnsembleStrategy):
    """Gradient booster-ağırlıklı ensemble stratejisi.

    İsim "PhysicsFirst" tarihsel; gerçekte bu stratejide ML yolu öne çıkar:
    XGBoost + LightGBM birlikte 0.8 ağırlık alır, kalan modeller (RF, GB)
    0.2'yi paylaşır. Physics tahmini ensemble dışında bir baseline olarak
    saklanır (predict() yolunda fizik fallback olarak kullanılır).
    """

    def calculate_weights(
        self, metrics: Dict[str, Dict[str, float]], available_models: list
    ) -> Dict[str, float]:
        weights: Dict[str, float] = {}
        target_models = available_models.copy()

        # Give higher weight to XGBoost and LightGBM if they exist
        advanced_boosters = [m for m in target_models if m in ["xgb", "lgb"]]
        others = [m for m in target_models if m not in ["xgb", "lgb"]]

        if advanced_boosters:
            booster_weight = 0.8 / len(advanced_boosters)
            for b in advanced_boosters:
                weights[b] = booster_weight

            if others:
                other_weight = 0.2 / len(others)
                for o in others:
                    weights[o] = other_weight
        else:
            # Fall back to equal
            w = 1.0 / len(target_models) if target_models else 0.0
            for m in target_models:
                weights[m] = w

        logger.info(f"PhysicsFirstStrategy calculated weights: {weights}")
        return weights
