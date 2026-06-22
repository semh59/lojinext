"""
LojiNext AI Performance Benchmark Suite
Run: python scripts/benchmark.py
"""

import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List

# Ensure app directory is in path
APP_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(APP_DIR))


@dataclass
class BenchmarkResult:
    """Benchmark result container."""

    name: str
    iterations: int
    mean_ms: float
    median_ms: float
    stdev_ms: float
    min_ms: float
    max_ms: float
    p95_ms: float
    passed: bool
    threshold_ms: float


class Benchmark:
    """Individual benchmark runner."""

    def __init__(
        self,
        name: str,
        func: Callable,
        iterations: int = 100,
        threshold_ms: float = 100.0,
    ):
        self.name = name
        self.func = func
        self.iterations = iterations
        self.threshold_ms = threshold_ms
        self.results: List[float] = []

    def run(self) -> BenchmarkResult:
        """Execute the benchmark."""
        # Warmup
        for _ in range(min(5, self.iterations // 10)):
            try:
                self.func()
            except Exception:
                pass

        # Actual benchmark
        self.results = []
        for _ in range(self.iterations):
            start = time.perf_counter()
            try:
                self.func()
            except Exception as e:
                print(f"  Warning: {self.name} raised {e}")
                continue
            end = time.perf_counter()
            self.results.append((end - start) * 1000)  # Convert to ms

        if not self.results:
            return BenchmarkResult(
                name=self.name,
                iterations=0,
                mean_ms=0,
                median_ms=0,
                stdev_ms=0,
                min_ms=0,
                max_ms=0,
                p95_ms=0,
                passed=False,
                threshold_ms=self.threshold_ms,
            )

        mean = statistics.mean(self.results)
        p95 = self._percentile(95)

        return BenchmarkResult(
            name=self.name,
            iterations=len(self.results),
            mean_ms=round(mean, 3),
            median_ms=round(statistics.median(self.results), 3),
            stdev_ms=round(statistics.stdev(self.results), 3)
            if len(self.results) > 1
            else 0,
            min_ms=round(min(self.results), 3),
            max_ms=round(max(self.results), 3),
            p95_ms=round(p95, 3),
            passed=p95 <= self.threshold_ms,
            threshold_ms=self.threshold_ms,
        )

    def _percentile(self, p: int) -> float:
        """Calculate percentile."""
        sorted_results = sorted(self.results)
        k = (len(sorted_results) - 1) * p / 100
        f = int(k)
        c = f + 1 if f + 1 < len(sorted_results) else f
        return sorted_results[f] + (k - f) * (sorted_results[c] - sorted_results[f])


def create_benchmarks() -> List[Benchmark]:
    """Create benchmark suite."""
    from app.core.services.arac_service import get_arac_service
    from app.core.services.report_service import get_report_service
    from app.core.services.sefer_service import get_sefer_service
    from app.database.connection import get_connection

    return [
        Benchmark(
            "Database Connection",
            lambda: get_connection().__enter__(),
            iterations=50,
            threshold_ms=10.0,
        ),
        Benchmark(
            "Get All Trips (limit=100)",
            lambda: get_sefer_service().get_all_trips(limit=100),
            iterations=30,
            threshold_ms=100.0,
        ),
        Benchmark(
            "Get All Vehicles",
            lambda: get_arac_service().get_all_vehicles(),
            iterations=50,
            threshold_ms=50.0,
        ),
        Benchmark(
            "Monthly Trend Report",
            lambda: get_report_service().generate_monthly_trend(),
            iterations=20,
            threshold_ms=200.0,
        ),
        Benchmark(
            "Fleet Summary",
            lambda: get_report_service().generate_fleet_summary(days=30),
            iterations=20,
            threshold_ms=200.0,
        ),
    ]


def print_results(results: List[BenchmarkResult]) -> None:
    """Print benchmark results in a table format."""
    print("\n" + "=" * 80)
    print("🚀 LojiNext AI Performance Benchmark Results")
    print("=" * 80)

    # Header
    print(
        f"{'Benchmark':<30} {'Mean':>10} {'P95':>10} {'Threshold':>10} {'Status':>10}"
    )
    print("-" * 80)

    passed_count = 0
    for r in results:
        status = "✅ PASS" if r.passed else "❌ FAIL"
        if r.passed:
            passed_count += 1

        print(
            f"{r.name:<30} {r.mean_ms:>9.2f}ms {r.p95_ms:>9.2f}ms {r.threshold_ms:>9.1f}ms {status:>10}"
        )

    print("-" * 80)
    print(
        f"Total: {len(results)} benchmarks | Passed: {passed_count} | Failed: {len(results) - passed_count}"
    )
    print("=" * 80)

    # Detailed results
    print("\n📊 Detailed Results:\n")
    for r in results:
        print(f"  {r.name}:")
        print(f"    Iterations: {r.iterations}")
        print(
            f"    Mean: {r.mean_ms:.3f}ms | Median: {r.median_ms:.3f}ms | Stdev: {r.stdev_ms:.3f}ms"
        )
        print(
            f"    Min: {r.min_ms:.3f}ms | Max: {r.max_ms:.3f}ms | P95: {r.p95_ms:.3f}ms"
        )
        print()


def main():
    """Run all benchmarks."""
    print("\n🔧 Initializing benchmark suite...")

    try:
        benchmarks = create_benchmarks()
    except Exception as e:
        print(f"❌ Failed to create benchmarks: {e}")
        return 1

    print(f"📋 Running {len(benchmarks)} benchmarks...\n")

    results = []
    for b in benchmarks:
        print(f"  Running: {b.name}...", end=" ", flush=True)
        result = b.run()
        results.append(result)
        status = "✅" if result.passed else "❌"
        print(f"{status} ({result.mean_ms:.2f}ms)")

    print_results(results)

    # Return exit code based on results
    failed = sum(1 for r in results if not r.passed)
    return 1 if failed > 0 else 0


if __name__ == "__main__":
    exit(main())
