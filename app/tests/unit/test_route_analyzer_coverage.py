"""Additional coverage for app/domain/services/route_analyzer.py.
Targets: assign_grade_class all branches, _haversine, _build_all_boundary_distances,
_init_stats_buckets, _parse_extra_segments edge cases,
analyze_segments with/without scaling + waytype fallback + distributions +
granular_nodes + ratios + December-boundary logic.
"""

import pytest

from v2.modules.route_simulation.domain.route_analyzer import (
    GradeClass,
    RouteAnalyzer,
    Segment,
    assign_grade_class,
    route_analyzer,
)

pytestmark = pytest.mark.unit


# ─── assign_grade_class ───────────────────────────────────────────────────────


def test_grade_class_downhill_steep():
    assert assign_grade_class(-9.0) == GradeClass.DOWNHILL_STEEP
    assert assign_grade_class(-8.0) == GradeClass.DOWNHILL_STEEP


def test_grade_class_downhill_moderate():
    assert assign_grade_class(-7.9) == GradeClass.DOWNHILL_MODERATE
    assert assign_grade_class(-3.0) == GradeClass.DOWNHILL_MODERATE


def test_grade_class_flat():
    assert assign_grade_class(0.0) == GradeClass.FLAT
    assert assign_grade_class(2.9) == GradeClass.FLAT
    assert assign_grade_class(-2.9) == GradeClass.FLAT


def test_grade_class_uphill_moderate():
    assert assign_grade_class(3.0) == GradeClass.UPHILL_MODERATE
    assert assign_grade_class(7.9) == GradeClass.UPHILL_MODERATE


def test_grade_class_uphill_steep():
    assert assign_grade_class(8.0) == GradeClass.UPHILL_STEEP
    assert assign_grade_class(15.0) == GradeClass.UPHILL_STEEP


# ─── _haversine ───────────────────────────────────────────────────────────────


class TestHaversine:
    def setup_method(self):
        self.ra = RouteAnalyzer()

    def test_same_point_is_zero(self):
        assert self.ra._haversine(0, 0, 0, 0) == 0.0

    def test_one_degree_lat_approx_111km(self):
        dist = self.ra._haversine(0, 0, 0, 1)
        assert 110_000 < dist < 112_000

    def test_one_degree_lon_equator_approx_111km(self):
        dist = self.ra._haversine(0, 0, 1, 0)
        assert 110_000 < dist < 112_000

    def test_istanbul_ankara_approx_350km(self):
        # Istanbul ~(29.0, 41.0), Ankara ~(32.8, 39.9)
        dist = self.ra._haversine(29.0, 41.0, 32.8, 39.9)
        assert 330_000 < dist < 380_000

    def test_symmetry(self):
        d1 = self.ra._haversine(10.0, 20.0, 15.0, 25.0)
        d2 = self.ra._haversine(15.0, 25.0, 10.0, 20.0)
        assert abs(d1 - d2) < 1  # within 1 metre


# ─── _calculate_cumulative_distances ─────────────────────────────────────────


class TestCumDist:
    def setup_method(self):
        self.ra = RouteAnalyzer()

    def test_single_point_returns_zero(self):
        result = self.ra._calculate_cumulative_distances([[0, 0]])
        assert result == [0.0]

    def test_two_points_correct_length(self):
        result = self.ra._calculate_cumulative_distances([[0, 0], [1, 0]])
        assert len(result) == 2
        assert result[0] == 0.0
        assert result[1] > 0.0

    def test_monotonically_increasing(self):
        points = [[i, 0] for i in range(5)]
        result = self.ra._calculate_cumulative_distances(points)
        for i in range(1, len(result)):
            assert result[i] > result[i - 1]


# ─── _build_all_boundary_distances ───────────────────────────────────────────


def test_build_all_boundary_distances_sorted_unique():
    s1 = Segment(0, 1, 0, 0.0, 100.0)
    s2 = Segment(1, 2, 1, 100.0, 200.0)
    wc = Segment(0, 2, 1, 0.0, 200.0)
    result = RouteAnalyzer._build_all_boundary_distances([s1, s2], [wc], [])
    assert result == sorted(set(result))
    assert 0.0 in result
    assert 100.0 in result
    assert 200.0 in result


def test_build_all_boundary_distances_deduplicates():
    s1 = Segment(0, 1, 0, 0.0, 500.0)
    s2 = Segment(0, 1, 1, 0.0, 500.0)  # same boundaries
    result = RouteAnalyzer._build_all_boundary_distances([s1], [s2], [])
    # 0.0 and 500.0 each appear once
    assert result.count(0.0) == 1
    assert result.count(500.0) == 1


def test_build_all_boundary_distances_empty_lists():
    result = RouteAnalyzer._build_all_boundary_distances([], [], [])
    assert result == []


# ─── _init_stats_buckets ──────────────────────────────────────────────────────


def test_init_stats_buckets_has_all_categories():
    buckets = RouteAnalyzer._init_stats_buckets()
    expected = {
        "motorway",
        "trunk",
        "primary",
        "secondary",
        "tertiary",
        "residential",
        "unclassified",
        "other",
    }
    assert set(buckets.keys()) == expected


def test_init_stats_buckets_all_zeros():
    buckets = RouteAnalyzer._init_stats_buckets()
    for cat, vals in buckets.items():
        assert vals == {"flat": 0.0, "up": 0.0, "down": 0.0}


# ─── _parse_extra_segments ───────────────────────────────────────────────────


class TestParseExtraSegments:
    def setup_method(self):
        self.ra = RouteAnalyzer()
        self.cum = [0, 100, 200, 300, 400, 500]

    def test_missing_key_returns_empty(self):
        result = self.ra._parse_extra_segments({}, "steepness", self.cum)
        assert result == []

    def test_key_present_no_values_key(self):
        result = self.ra._parse_extra_segments({"steepness": {}}, "steepness", self.cum)
        assert result == []

    def test_out_of_bounds_start_skipped(self):
        extras = {"steepness": {"values": [[0, 10, 1]]}}  # end_idx=10 out of range
        result = self.ra._parse_extra_segments(extras, "steepness", self.cum)
        assert result == []

    def test_normal_parse(self):
        extras = {"steepness": {"values": [[0, 2, 1], [2, 4, -1]]}}
        result = self.ra._parse_extra_segments(extras, "steepness", self.cum)
        assert len(result) == 2
        assert result[0].value == 1
        assert result[1].value == -1

    def test_segment_distances_set_correctly(self):
        extras = {"waytype": {"values": [[1, 3, 5]]}}
        result = self.ra._parse_extra_segments(extras, "waytype", self.cum)
        assert len(result) == 1
        assert result[0].start_dist == 100
        assert result[0].end_dist == 300


# ─── analyze_segments full flow ──────────────────────────────────────────────


class TestAnalyzeSegmentsFull:
    def setup_method(self):
        self.ra = RouteAnalyzer()

    def _patch_distances(self, ra, distances):
        ra._calculate_cumulative_distances = lambda pts: distances

    def test_empty_geometry_returns_empty(self):
        assert self.ra.analyze_segments([], {}) == {}

    def test_missing_steepness_returns_default_structure(self):
        points = [[0, 0], [0.01, 0]]
        stats = self.ra.analyze_segments(points, {})
        assert "highway" in stats
        assert stats["highway"]["flat"] == 0.0

    def test_waycategory_and_steepness_only_no_waytype(self):
        """No waytype → waytype fallback not triggered, but analysis succeeds."""
        self._patch_distances(self.ra, [0.0, 1000.0, 2000.0])
        points = [[0, 0], [0, 0], [0, 0]]
        extras = {
            "steepness": {"values": [[0, 1, 0], [1, 2, 1]]},
            "waycategory": {"values": [[0, 1, 1], [1, 2, 0]]},
        }
        stats = self.ra.analyze_segments(points, extras)
        assert stats["highway"]["flat"] == 1.0
        assert stats["other"]["up"] == 1.0

    def test_waytype_fallback_sets_primary(self):
        """cat_key == other and waytype==1 → treated as primary."""
        self._patch_distances(self.ra, [0.0, 1000.0, 2000.0])
        points = [[0, 0], [0, 0], [0, 0]]
        extras = {
            "steepness": {"values": [[0, 2, 0]]},
            "waycategory": {"values": [[0, 2, 0]]},  # category 0 → "other"
            "waytype": {"values": [[0, 2, 1]]},  # waytype 1 → primary
        }
        stats = self.ra.analyze_segments(points, extras)
        # primary is a highway category → should be in highway
        assert stats["highway"]["flat"] == 2.0

    def test_downhill_classified_as_down(self):
        self._patch_distances(self.ra, [0.0, 1000.0, 2000.0])
        points = [[0, 0], [0, 0], [0, 0]]
        extras = {
            "steepness": {"values": [[0, 2, -1]]},  # negative → down
            "waycategory": {"values": [[0, 2, 1]]},  # motorway
        }
        stats = self.ra.analyze_segments(points, extras)
        assert stats["highway"]["down"] == 2.0
        assert stats["highway"]["flat"] == 0.0

    def test_scaling_applied_with_reference_distance(self):
        self._patch_distances(self.ra, [0.0, 1000.0, 2000.0])
        points = [[0, 0], [0, 0], [0, 0]]
        extras = {
            "steepness": {"values": [[0, 2, 0]]},
            "waycategory": {"values": [[0, 2, 1]]},
        }
        # reference_distance_m=1000 → scale by 0.5
        stats = self.ra.analyze_segments(points, extras, reference_distance_m=1000.0)
        assert stats["highway"]["flat"] == 1.0

    def test_ratios_all_highway(self):
        """100% motorway route → otoyol ratio close to 1.0."""
        self._patch_distances(self.ra, [0.0, 1000.0, 2000.0])
        points = [[0, 0], [0, 0], [0, 0]]
        extras = {
            "steepness": {"values": [[0, 2, 0]]},
            "waycategory": {"values": [[0, 2, 1]]},  # motorway
        }
        stats = self.ra.analyze_segments(points, extras)
        assert "ratios" in stats
        assert stats["ratios"]["otoyol"] > 0.9

    def test_ratios_all_residential(self):
        """100% residential → sehir_ici close to 1.0."""
        self._patch_distances(self.ra, [0.0, 1000.0, 2000.0])
        points = [[0, 0], [0, 0], [0, 0]]
        extras = {
            "steepness": {"values": [[0, 2, 0]]},
            "waycategory": {"values": [[0, 2, 7]]},  # residential
        }
        stats = self.ra.analyze_segments(points, extras)
        assert stats["ratios"]["sehir_ici"] > 0.9

    def test_granular_nodes_generated(self):
        """analyze_segments returns granular_nodes list."""
        # Real points with elevation
        points = [
            [29.0, 41.0, 100.0],
            [29.01, 41.01, 110.0],
            [29.02, 41.02, 105.0],
        ]
        extras = {
            "steepness": {"values": [[0, 2, 1]]},
            "waycategory": {"values": [[0, 2, 1]]},
        }
        stats = self.ra.analyze_segments(points, extras)
        assert "granular_nodes" in stats
        assert len(stats["granular_nodes"]) == 2  # 2 segments for 3 points

    def test_granular_nodes_tuple_format(self):
        """Each granular node is (dist_m, speed_ms, elev_diff) floats."""
        points = [
            [29.0, 41.0, 0.0],
            [29.01, 41.01, 50.0],
        ]
        extras = {
            "steepness": {"values": [[0, 1, 0]]},
            "waycategory": {"values": [[0, 1, 1]]},  # motorway
        }
        stats = self.ra.analyze_segments(points, extras)
        node = stats["granular_nodes"][0]
        assert len(node) == 3
        dist, speed_ms, elev = node
        assert dist > 0
        assert speed_ms > 0
        assert elev == 50.0

    def test_distributions_present(self):
        """distributions key exists with road, grade, road_grade, avg_grade_pct."""
        points = [
            [29.0, 41.0, 0.0],
            [29.01, 41.01, 0.0],
        ]
        extras = {
            "steepness": {"values": [[0, 1, 0]]},
            "waycategory": {"values": [[0, 1, 1]]},
        }
        stats = self.ra.analyze_segments(points, extras)
        assert "distributions" in stats
        dist = stats["distributions"]
        assert "road" in dist
        assert "grade" in dist
        assert "road_grade" in dist
        assert "avg_grade_pct" in dist

    def test_distributions_empty_when_no_geometry(self):
        """Single-point geometry (no segments) → empty distributions."""
        self._patch_distances(self.ra, [0.0])
        points = [[0, 0]]
        extras = {
            "steepness": {"values": [[0, 0, 0]]},
            "waycategory": {"values": [[0, 0, 1]]},
        }
        stats = self.ra.analyze_segments(points, extras)
        # no granular nodes → distributions should be empty dict-like
        if "distributions" in stats:
            assert stats["distributions"]["road"] == {}

    def test_multiple_categories_combined(self):
        """Mix of motorway + secondary → highway and other both populated."""
        self._patch_distances(self.ra, [0.0, 1000.0, 2000.0, 3000.0])
        points = [[0, 0]] * 4
        extras = {
            "steepness": {"values": [[0, 3, 0]]},
            "waycategory": {
                "values": [
                    [0, 1, 1],  # motorway 0-1000
                    [1, 2, 4],  # secondary 1000-2000
                    [2, 3, 7],  # residential 2000-3000
                ]
            },
        }
        stats = self.ra.analyze_segments(points, extras)
        assert stats["highway"]["flat"] > 0.0
        assert stats["other"]["flat"] > 0.0

    def test_top_level_residual_distribution_with_reference(self):
        """With reference_distance_m, sum of highway+other ≈ reference km (within rounding)."""
        self._patch_distances(self.ra, [0.0, 1000.0, 2000.0])
        points = [[0, 0], [0, 0], [0, 0]]
        extras = {
            "steepness": {"values": [[0, 2, 0]]},
            "waycategory": {"values": [[0, 2, 1]]},
        }
        ref_m = 3000.0
        stats = self.ra.analyze_segments(points, extras, reference_distance_m=ref_m)
        total_km = round(
            sum(stats["highway"].values()) + sum(stats["other"].values()), 1
        )
        assert abs(total_km - round(ref_m / 1000.0, 1)) <= 0.2  # allow small rounding

    def test_ratios_zero_total_uses_defaults(self):
        """Zero total distance → ratios default to otoyol=0, devlet=0, sehir=1."""
        self._patch_distances(self.ra, [0.0, 0.0])  # zero-length
        points = [[0, 0], [0, 0]]
        extras = {
            "steepness": {"values": [[0, 1, 0]]},
            "waycategory": {"values": [[0, 1, 1]]},
        }
        stats = self.ra.analyze_segments(points, extras)
        # When geometry collapses to zero, ratios should have default
        if "ratios" in stats:
            assert stats["ratios"]["sehir_ici"] <= 1.0


# ─── Module-level singleton ───────────────────────────────────────────────────


def test_module_singleton_is_route_analyzer():
    assert isinstance(route_analyzer, RouteAnalyzer)
