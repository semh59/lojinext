"""
ML Model Benchmark ve A/B Test Framework
Performans karşılaştırma ve model seçimi
"""

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import mean, stdev
from typing import Any, Callable, Dict, List, Optional

import numpy as np

from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


@dataclass
class BenchmarkResult:
    """Benchmark sonucu"""

    model_name: str
    metric_name: str
    value: float
    lower_is_better: bool = True
    sample_count: int = 0
    std_dev: float = 0.0
    execution_time_ms: float = 0.0


@dataclass
class ABTestResult:
    """A/B test sonucu"""

    test_name: str
    model_a: str
    model_b: str
    metric_name: str
    model_a_value: float
    model_b_value: float
    winner: str
    improvement_percent: float
    statistically_significant: bool
    p_value: float = 0.0
    sample_count: int = 0
    test_type: str = "T-Test"


@dataclass
class ModelPerformanceReport:
    """Model performans raporu"""

    model_name: str
    benchmarks: List[BenchmarkResult] = field(default_factory=list)
    ab_tests: List[ABTestResult] = field(default_factory=list)
    overall_score: float = 0.0
    recommendation: str = ""


class MLBenchmark:
    """
    ML model benchmark framework.

    Ölçümler:
    - MAE (Mean Absolute Error)
    - RMSE (Root Mean Square Error)
    - R² (Coefficient of Determination)
    - Inference Time
    - Memory Usage
    """

    def __init__(self):
        self.results: List[BenchmarkResult] = []

    def benchmark_prediction_accuracy(
        self, model_name: str, predictions: np.ndarray, actuals: np.ndarray
    ) -> List[BenchmarkResult]:
        """
        Tahmin doğruluğu benchmark'ı.

        Args:
            model_name: Model adı
            predictions: Tahmin değerleri
            actuals: Gerçek değerler

        Returns:
            List[BenchmarkResult]: Benchmark sonuçları
        """
        results = []

        # MAE
        errors = np.abs(predictions - actuals)
        mae = np.mean(errors) if len(errors) > 0 else 0
        mae = float(mae) if np.isfinite(mae) else 0.0

        results.append(
            BenchmarkResult(
                model_name=model_name,
                metric_name="MAE",
                value=round(mae, 4),
                lower_is_better=True,
                sample_count=len(predictions),
            )
        )

        # RMSE
        mse = np.mean((predictions - actuals) ** 2) if len(predictions) > 0 else 0
        rmse = np.sqrt(mse) if mse >= 0 else 0
        rmse = float(rmse) if np.isfinite(rmse) else 0.0

        results.append(
            BenchmarkResult(
                model_name=model_name,
                metric_name="RMSE",
                value=round(rmse, 4),
                lower_is_better=True,
                sample_count=len(predictions),
            )
        )

        # R²
        ss_res = np.sum((actuals - predictions) ** 2)
        ss_tot = np.sum((actuals - np.mean(actuals)) ** 2)
        if ss_tot > 1e-10:
            r2 = 1 - (ss_res / ss_tot)
        else:
            r2 = 0.0
        r2 = float(r2) if np.isfinite(r2) else 0.0

        results.append(
            BenchmarkResult(
                model_name=model_name,
                metric_name="R²",
                value=round(r2, 4),
                lower_is_better=False,
                sample_count=len(predictions),
            )
        )

        # MAPE (Mean Absolute Percentage Error)
        non_zero_mask = (actuals != 0) & np.isfinite(actuals) & np.isfinite(predictions)
        if np.any(non_zero_mask):
            mape = (
                np.mean(
                    np.abs(
                        (actuals[non_zero_mask] - predictions[non_zero_mask])
                        / actuals[non_zero_mask]
                    )
                )
                * 100
            )
            mape = float(mape) if np.isfinite(mape) else 0.0

            results.append(
                BenchmarkResult(
                    model_name=model_name,
                    metric_name="MAPE",
                    value=round(mape, 2),
                    lower_is_better=True,
                    sample_count=int(np.sum(non_zero_mask)),
                )
            )

        self.results.extend(results)
        return results

    def benchmark_inference_time(
        self,
        model_name: str,
        predict_func: Callable,
        input_data: Any,
        n_runs: int = 100,
    ) -> BenchmarkResult:
        """
        Inference süresi benchmark'ı.

        Args:
            model_name: Model adı
            predict_func: Tahmin fonksiyonu
            input_data: Test input
            n_runs: Çalıştırma sayısı

        Returns:
            BenchmarkResult: Benchmark sonucu
        """
        times = []

        # Warm-up
        for _ in range(5):
            predict_func(input_data)

        # Benchmark
        for _ in range(n_runs):
            start = time.perf_counter()
            predict_func(input_data)
            end = time.perf_counter()
            times.append((end - start) * 1000)  # ms

        avg_time = mean(times)
        std_time = stdev(times) if len(times) > 1 else 0

        result = BenchmarkResult(
            model_name=model_name,
            metric_name="Inference Time (ms)",
            value=round(avg_time, 3),
            lower_is_better=True,
            sample_count=n_runs,
            std_dev=round(std_time, 3),
        )

        self.results.append(result)
        return result

    def compare_models(self, metric_name: str) -> Dict[str, float]:
        """
        Modelleri belirli bir metriğe göre karşılaştır.

        Returns:
            Dict[str, float]: Model adı -> değer mapping
        """
        comparison = {}

        for result in self.results:
            if result.metric_name == metric_name:
                comparison[result.model_name] = result.value

        return comparison

    def get_best_model(self, metric_name: str) -> Optional[str]:
        """Belirli metrik için en iyi modeli bul."""
        comparison = self.compare_models(metric_name)

        if not comparison:
            return None

        # İlk sonuçtan lower_is_better bilgisini al
        lower_is_better = True
        for result in self.results:
            if result.metric_name == metric_name:
                lower_is_better = result.lower_is_better
                break

        if lower_is_better:
            return min(comparison, key=comparison.get)
        else:
            return max(comparison, key=comparison.get)

    def generate_report(self) -> str:
        """Markdown formatında benchmark raporu oluştur."""
        if not self.results:
            return "Henüz benchmark sonucu yok."

        lines = ["# ML Model Benchmark Raporu", ""]
        lines.append(
            f"**Tarih:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}"
        )
        lines.append("")

        # Metrik bazında grupla
        metrics: Dict[str, list] = {}
        for result in self.results:
            if result.metric_name not in metrics:
                metrics[result.metric_name] = []
            metrics[result.metric_name].append(result)

        for metric_name, results in metrics.items():
            lines.append(f"## {metric_name}")
            lines.append("")
            lines.append("| Model | Değer | Std Dev | Örnek Sayısı |")
            lines.append("|-------|-------|---------|--------------|")

            # lower_is_better değerini al
            lower_is_better = results[0].lower_is_better if results else True

            for result in sorted(
                results, key=lambda x: x.value, reverse=not lower_is_better
            ):
                lines.append(
                    f"| {result.model_name} | {result.value} | {result.std_dev} | {result.sample_count} |"
                )

            best = self.get_best_model(metric_name)
            if best:
                lines.append(f"\n**En İyi:** {best}")

            lines.append("")

        return "\n".join(lines)


class ABTestFramework:
    """
    A/B Test Framework.

    İki modeli karşılaştırma ve istatistiksel anlamlılık testi.
    """

    def __init__(self):
        self.tests: List[ABTestResult] = []

    def run_ab_test(
        self,
        test_name: str,
        model_a_name: str,
        model_a_predictions: np.ndarray,
        model_b_name: str,
        model_b_predictions: np.ndarray,
        actuals: np.ndarray,
        metric: str = "MAE",
    ) -> ABTestResult:
        """
        A/B test çalıştır.

        Args:
            test_name: Test adı
            model_a_name: Model A adı
            model_a_predictions: Model A tahminleri
            model_b_name: Model B adı
            model_b_predictions: Model B tahminleri
            actuals: Gerçek değerler
            metric: Karşılaştırma metriği

        Returns:
            ABTestResult: Test sonucu
        """
        # Metrik hesapla
        if metric == "MAE":
            a_value = float(np.mean(np.abs(model_a_predictions - actuals)))
            b_value = float(np.mean(np.abs(model_b_predictions - actuals)))
            lower_is_better = True
        elif metric == "RMSE":
            a_value = float(np.sqrt(np.mean((model_a_predictions - actuals) ** 2)))
            b_value = float(np.sqrt(np.mean((model_b_predictions - actuals) ** 2)))
            lower_is_better = True
        elif metric == "R²":
            ss_res_a = np.sum((actuals - model_a_predictions) ** 2)
            ss_res_b = np.sum((actuals - model_b_predictions) ** 2)
            ss_tot = np.sum((actuals - np.mean(actuals)) ** 2)
            a_value = float(1 - (ss_res_a / ss_tot) if ss_tot > 0 else 0)
            b_value = float(1 - (ss_res_b / ss_tot) if ss_tot > 0 else 0)
            lower_is_better = False
        else:
            raise ValueError(f"Unknown metric: {metric}")

        # Kazanan belirle
        if lower_is_better:
            winner = model_a_name if a_value < b_value else model_b_name
            if b_value != 0:
                improvement = (
                    ((b_value - a_value) / b_value * 100)
                    if a_value < b_value
                    else ((a_value - b_value) / a_value * 100)
                )
            elif a_value != 0:
                improvement = 100.0
            else:
                improvement = 0.0
        else:
            winner = model_a_name if a_value > b_value else model_b_name
            if b_value != 0:
                improvement = (
                    ((a_value - b_value) / b_value * 100)
                    if a_value > b_value
                    else ((b_value - a_value) / a_value * 100)
                )
            elif a_value != 0:  # b is 0, a is not
                improvement = 100.0  # Infinite improvement actually
            else:
                improvement = 0.0

        # İstatistiksel anlamlılık (paired t-test)
        errors_a = np.abs(model_a_predictions - actuals)
        errors_b = np.abs(model_b_predictions - actuals)

        try:
            import warnings

            from scipy import stats

            # Suppress RuntimeWarnings from scipy stats for edge cases (e.g., identical data)
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=RuntimeWarning)

                # 1. Normallik Kontrolü (Shapiro-Wilk)
                # Eğer örneklem sayısı küçükse (<5000), normalliği kontrol et
                is_normal = True
                if len(errors_a) >= 3 and len(errors_a) < 5000:
                    _, p_norm_a = stats.shapiro(errors_a)
                    _, p_norm_b = stats.shapiro(errors_b)
                    is_normal = bool(p_norm_a > 0.05 and p_norm_b > 0.05)

                # 2. Uygun Testi Seç
                if is_normal:
                    # Parametrik: Paired T-Test
                    t_stat, p_value = stats.ttest_rel(errors_a, errors_b)
                    test_type = "Paired T-Test"
                else:
                    # Parametrik Olmayan: Wilcoxon Signed-Rank Test (Uç değerlere dirençli)
                    # Farkların tamamı sıfırsa wilcoxon hata verebilir
                    diff = errors_a - errors_b
                    if np.all(diff == 0):
                        p_value = 1.0
                    else:
                        _, p_value = stats.wilcoxon(errors_a, errors_b)
                    test_type = "Wilcoxon Signed-Rank Test"

            statistically_significant = bool(p_value < 0.05)
            p_value = float(p_value)
            logger.info(
                f"A/B Test ({test_name}): Used {test_type} (Normal: {is_normal}), p={p_value:.4f}"
            )
        except (ImportError, ValueError) as e:
            p_value = 0.0
            statistically_significant = False
            test_type = "None"
            logger.warning(f"Statistical test failed: {e}")

        result = ABTestResult(
            test_name=test_name,
            model_a=model_a_name,
            model_b=model_b_name,
            metric_name=metric,
            model_a_value=round(a_value, 4),
            model_b_value=round(b_value, 4),
            winner=winner,
            improvement_percent=round(improvement, 2),
            statistically_significant=statistically_significant,
            p_value=round(p_value, 4) if p_value else 0.0,
            sample_count=len(actuals),
            test_type=test_type,
        )

        self.tests.append(result)
        return result

    def generate_report(self) -> str:
        """A/B test raporu oluştur."""
        if not self.tests:
            return "Henüz A/B test sonucu yok."

        lines = ["# A/B Test Raporu", ""]
        lines.append(
            f"**Tarih:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}"
        )
        lines.append("")
        lines.append(
            "| Test Adı | Model A | Model B | Metrik | Kazanan | Fark % | Anlamlı mı? | Test Tipi | p-value |"
        )
        lines.append(
            "|----------|---------|---------|--------|---------|---------|-------------|-----------|---------|"
        )

        for test in self.tests:
            sig_str = "EVET" if test.statistically_significant else "HAYIR"
            lines.append(
                f"| {test.test_name} | {test.model_a} | {test.model_b} | {test.metric_name} | {test.winner} | {test.improvement_percent}% | {sig_str} | {test.test_type} | {test.p_value} |"  # noqa: E501
            )

        lines.append("")  # Add an empty line after the table for better readability

        return "\n".join(lines)


class EnsembleBenchmark:
    """
    Ensemble model özel benchmark'ları.

    4-model vs 5-model (LightGBM dahil) karşılaştırması.
    """

    @staticmethod
    async def benchmark_ensemble_models(
        seferler: List[Dict], actuals: np.ndarray
    ) -> Dict:
        """
        Ensemble modelleri benchmark'la.

        Args:
            seferler: Sefer verileri
            actuals: Gerçek tüketim değerleri

        Returns:
            Dict: Benchmark sonuçları
        """
        from app.core.ml.ensemble_predictor import (
            LIGHTGBM_AVAILABLE,
            EnsembleFuelPredictor,
        )

        benchmark = MLBenchmark()
        ABTestFramework()

        # LightGBM dahil ensemble
        predictor_5 = EnsembleFuelPredictor()
        predictor_5.fit(seferler, actuals)

        predictions_5: Any = []
        for sefer in seferler:
            pred = predictor_5.predict(sefer)
            predictions_5.append(pred.tahmin_l_100km)
        predictions_5 = np.array(predictions_5)

        # Benchmark
        benchmark.benchmark_prediction_accuracy(
            "5-Model Ensemble", predictions_5, actuals
        )

        # Inference time
        benchmark.benchmark_inference_time(
            "5-Model Ensemble", lambda x: predictor_5.predict(x), seferler[0], n_runs=50
        )

        logger.info("Ensemble benchmark completed")

        return {
            "benchmark_report": benchmark.generate_report(),
            "results": benchmark.results,
            "lightgbm_available": LIGHTGBM_AVAILABLE,
        }


# Convenience functions
def run_quick_benchmark(
    model_name: str, predictions: np.ndarray, actuals: np.ndarray
) -> Dict:
    """Hızlı benchmark çalıştır."""
    benchmark = MLBenchmark()
    results = benchmark.benchmark_prediction_accuracy(model_name, predictions, actuals)

    return {
        "model": model_name,
        "mae": next((r.value for r in results if r.metric_name == "MAE"), None),
        "rmse": next((r.value for r in results if r.metric_name == "RMSE"), None),
        "r2": next((r.value for r in results if r.metric_name == "R²"), None),
        "mape": next((r.value for r in results if r.metric_name == "MAPE"), None),
    }


def run_quick_ab_test(
    model_a_name: str,
    model_a_preds: np.ndarray,
    model_b_name: str,
    model_b_preds: np.ndarray,
    actuals: np.ndarray,
) -> ABTestResult:
    """Hızlı A/B test çalıştır."""
    framework = ABTestFramework()
    return framework.run_ab_test(
        test_name=f"{model_a_name} vs {model_b_name}",
        model_a_name=model_a_name,
        model_a_predictions=model_a_preds,
        model_b_name=model_b_name,
        model_b_predictions=model_b_preds,
        actuals=actuals,
        metric="MAE",
    )
