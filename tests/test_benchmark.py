"""
Benchmark Framework Unit Tests
"""

import sys

import numpy as np
import pytest

sys.path.insert(0, ".")

from app.core.ml.benchmark import (
    ABTestFramework,
    ABTestResult,
    BenchmarkResult,
    MLBenchmark,
    run_quick_ab_test,
    run_quick_benchmark,
)


class TestBenchmarkResult:
    """BenchmarkResult dataclass testleri"""

    def test_benchmark_result_creation(self):
        """Benchmark sonucu oluşturma testi"""
        result = BenchmarkResult(
            model_name="TestModel",
            metric_name="MAE",
            value=1.5,
            lower_is_better=True,
            sample_count=100,
            std_dev=0.2,
        )

        assert result.model_name == "TestModel"
        assert result.metric_name == "MAE"
        assert result.value == 1.5
        assert result.lower_is_better is True


class TestMLBenchmark:
    """MLBenchmark sınıf testleri"""

    @pytest.fixture
    def benchmark(self):
        return MLBenchmark()

    @pytest.fixture
    def sample_data(self):
        np.random.seed(42)
        actuals = np.random.uniform(28, 38, 100)
        predictions = actuals + np.random.normal(0, 2, 100)
        return predictions, actuals

    def test_init(self, benchmark):
        """Benchmark başlatma testi"""
        assert benchmark is not None
        assert len(benchmark.results) == 0

    def test_benchmark_prediction_accuracy(self, benchmark, sample_data):
        """Tahmin doğruluğu benchmark testi"""
        predictions, actuals = sample_data

        results = benchmark.benchmark_prediction_accuracy(
            "TestModel", predictions, actuals
        )

        assert len(results) >= 3  # MAE, RMSE, R²

        # Metrik tipleri kontrol
        metric_names = [r.metric_name for r in results]
        assert "MAE" in metric_names
        assert "RMSE" in metric_names
        assert "R²" in metric_names

    def test_benchmark_mae_value(self, benchmark, sample_data):
        """MAE değer doğruluğu testi"""
        predictions, actuals = sample_data

        results = benchmark.benchmark_prediction_accuracy(
            "TestModel", predictions, actuals
        )

        mae_result = next(r for r in results if r.metric_name == "MAE")
        expected_mae = np.mean(np.abs(predictions - actuals))

        assert abs(mae_result.value - expected_mae) < 0.001

    def test_benchmark_rmse_value(self, benchmark, sample_data):
        """RMSE değer doğruluğu testi"""
        predictions, actuals = sample_data

        results = benchmark.benchmark_prediction_accuracy(
            "TestModel", predictions, actuals
        )

        rmse_result = next(r for r in results if r.metric_name == "RMSE")
        expected_rmse = np.sqrt(np.mean((predictions - actuals) ** 2))

        assert abs(rmse_result.value - expected_rmse) < 0.001

    def test_benchmark_r2_value(self, benchmark, sample_data):
        """R² değer doğruluğu testi"""
        predictions, actuals = sample_data

        results = benchmark.benchmark_prediction_accuracy(
            "TestModel", predictions, actuals
        )

        r2_result = next(r for r in results if r.metric_name == "R²")

        ss_res = np.sum((actuals - predictions) ** 2)
        ss_tot = np.sum((actuals - np.mean(actuals)) ** 2)
        expected_r2 = 1 - (ss_res / ss_tot)

        assert abs(r2_result.value - expected_r2) < 0.001

    def test_benchmark_inference_time(self, benchmark):
        """Inference time benchmark testi"""

        def dummy_predict(x):
            return x * 2

        result = benchmark.benchmark_inference_time(
            "DummyModel", dummy_predict, 10, n_runs=50
        )

        assert result.metric_name == "Inference Time (ms)"
        assert result.value >= 0
        assert result.sample_count == 50

    def test_compare_models(self, benchmark, sample_data):
        """Model karşılaştırma testi"""
        predictions, actuals = sample_data

        # İki model benchmark'la
        benchmark.benchmark_prediction_accuracy("ModelA", predictions, actuals)
        benchmark.benchmark_prediction_accuracy("ModelB", predictions * 1.1, actuals)

        comparison = benchmark.compare_models("MAE")

        assert "ModelA" in comparison
        assert "ModelB" in comparison

    def test_get_best_model(self, benchmark, sample_data):
        """En iyi model bulma testi"""
        predictions, actuals = sample_data

        # Daha iyi ve daha kötü modeller
        benchmark.benchmark_prediction_accuracy("BetterModel", predictions, actuals)
        benchmark.benchmark_prediction_accuracy("WorseModel", predictions + 5, actuals)

        best = benchmark.get_best_model("MAE")

        assert best == "BetterModel"

    def test_generate_report(self, benchmark, sample_data):
        """Rapor oluşturma testi"""
        predictions, actuals = sample_data
        benchmark.benchmark_prediction_accuracy("TestModel", predictions, actuals)

        report = benchmark.generate_report()

        assert "# ML Model Benchmark Raporu" in report
        assert "TestModel" in report
        assert "MAE" in report


class TestABTestFramework:
    """ABTestFramework sınıf testleri"""

    @pytest.fixture
    def framework(self):
        return ABTestFramework()

    @pytest.fixture
    def sample_data(self):
        np.random.seed(42)
        actuals = np.random.uniform(28, 38, 100)
        preds_a = actuals + np.random.normal(0, 1.5, 100)  # Daha iyi
        preds_b = actuals + np.random.normal(0, 3.0, 100)  # Daha kötü
        return preds_a, preds_b, actuals

    def test_init(self, framework):
        """Framework başlatma testi"""
        assert framework is not None
        assert len(framework.tests) == 0

    def test_run_ab_test_mae(self, framework, sample_data):
        """MAE metriği ile A/B test testi"""
        preds_a, preds_b, actuals = sample_data

        result = framework.run_ab_test(
            test_name="TestAB",
            model_a_name="ModelA",
            model_a_predictions=preds_a,
            model_b_name="ModelB",
            model_b_predictions=preds_b,
            actuals=actuals,
            metric="MAE",
        )

        assert isinstance(result, ABTestResult)
        assert result.winner == "ModelA"  # Daha düşük hata
        assert result.improvement_percent > 0

    def test_run_ab_test_rmse(self, framework, sample_data):
        """RMSE metriği ile A/B test testi"""
        preds_a, preds_b, actuals = sample_data

        result = framework.run_ab_test(
            test_name="TestAB_RMSE",
            model_a_name="ModelA",
            model_a_predictions=preds_a,
            model_b_name="ModelB",
            model_b_predictions=preds_b,
            actuals=actuals,
            metric="RMSE",
        )

        assert result.winner == "ModelA"

    def test_run_ab_test_r2(self, framework, sample_data):
        """R² metriği ile A/B test testi"""
        preds_a, preds_b, actuals = sample_data

        result = framework.run_ab_test(
            test_name="TestAB_R2",
            model_a_name="ModelA",
            model_a_predictions=preds_a,
            model_b_name="ModelB",
            model_b_predictions=preds_b,
            actuals=actuals,
            metric="R²",
        )

        assert result.winner == "ModelA"  # Daha yüksek R²

    def test_statistical_significance(self, framework):
        """İstatistiksel anlamlılık testi"""
        # Kendi verisini oluştur - fixture kullanmadan
        np.random.seed(1234)  # Farklı seed
        actuals = np.random.uniform(28, 38, 100)
        preds_a = actuals + np.random.normal(0, 1, 100)
        preds_b = actuals + np.random.normal(0, 5, 100)  # Çok daha kötü

        result = framework.run_ab_test(
            test_name="SignificanceTest",
            model_a_name="ModelA",
            model_a_predictions=preds_a,
            model_b_name="ModelB",
            model_b_predictions=preds_b,
            actuals=actuals,
            metric="MAE",
        )

        # p_value ve statistically_significant doğru tipte olmalı
        assert isinstance(result.p_value, float)
        assert isinstance(result.statistically_significant, bool)

    def test_generate_report(self, framework, sample_data):
        """A/B test rapor oluşturma testi"""
        preds_a, preds_b, actuals = sample_data

        framework.run_ab_test(
            test_name="ReportTest",
            model_a_name="ModelA",
            model_a_predictions=preds_a,
            model_b_name="ModelB",
            model_b_predictions=preds_b,
            actuals=actuals,
            metric="MAE",
        )

        report = framework.generate_report()

        assert "# A/B Test Raporu" in report
        assert "ReportTest" in report
        assert "Kazanan" in report


class TestConvenienceFunctions:
    """Yardımcı fonksiyon testleri"""

    def test_run_quick_benchmark(self):
        """Hızlı benchmark testi"""
        np.random.seed(42)
        actuals = np.random.uniform(28, 38, 50)
        predictions = actuals + np.random.normal(0, 2, 50)

        result = run_quick_benchmark("QuickModel", predictions, actuals)

        assert "model" in result
        assert "mae" in result
        assert "rmse" in result
        assert "r2" in result
        assert result["model"] == "QuickModel"

    def test_run_quick_ab_test(self):
        """Hızlı A/B test testi"""
        np.random.seed(42)
        actuals = np.random.uniform(28, 38, 50)
        preds_a = actuals + np.random.normal(0, 1, 50)
        preds_b = actuals + np.random.normal(0, 3, 50)

        result = run_quick_ab_test("ModelA", preds_a, "ModelB", preds_b, actuals)

        assert isinstance(result, ABTestResult)
        assert result.winner in ["ModelA", "ModelB"]


class TestIntegration:
    """Entegrasyon testleri"""

    def test_full_benchmark_workflow(self):
        """Tam benchmark workflow testi"""
        np.random.seed(42)

        # Gerçekçi veri oluştur
        actuals = np.random.uniform(28, 38, 200)

        # Farklı kalitede modeller simüle et
        model_good = actuals + np.random.normal(0, 1, 200)
        model_medium = actuals + np.random.normal(0, 2, 200)
        model_poor = actuals + np.random.normal(0, 4, 200)

        benchmark = MLBenchmark()

        # Benchmark'la
        benchmark.benchmark_prediction_accuracy("GoodModel", model_good, actuals)
        benchmark.benchmark_prediction_accuracy("MediumModel", model_medium, actuals)
        benchmark.benchmark_prediction_accuracy("PoorModel", model_poor, actuals)

        # En iyi modeli bul
        best_mae = benchmark.get_best_model("MAE")
        best_r2 = benchmark.get_best_model("R²")

        assert best_mae == "GoodModel"
        assert best_r2 == "GoodModel"

        # Rapor oluştur
        report = benchmark.generate_report()
        assert len(report) > 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
