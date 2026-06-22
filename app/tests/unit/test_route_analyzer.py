from app.domain.services.route_analyzer import RouteAnalyzer


class TestRouteAnalyzer:
    def setup_method(self):
        self.analyzer = RouteAnalyzer()

    def test_calculate_cumulative_distances(self):
        # A simple straight line on equator: (0,0) -> (0,1) -> (0,2) degree longitude
        # 1 degree lat/lon is roughly 111km, but let's trust the haversine implementation
        points = [[0, 0], [1, 0], [2, 0]]
        cum_dists = self.analyzer._calculate_cumulative_distances(points)
        assert len(cum_dists) == 3
        assert cum_dists[0] == 0.0
        assert cum_dists[1] > 0
        assert cum_dists[2] > cum_dists[1]

    def test_analyze_segments_empty(self):
        stats = self.analyzer.analyze_segments([], {})
        assert stats == {}

    def test_analyze_segments_missing_extras(self):
        # 3 points, 2 segments
        points = [[0, 0], [0.01, 0], [0.02, 0]]
        stats = self.analyzer.analyze_segments(points, {})
        # Should return default structure with zeros
        assert stats["highway"]["flat"] == 0.0
        assert stats["other"]["up"] == 0.0

    def test_analyze_segments_logic(self):
        # Create a mock scenario
        # Total distance approx: 2000m
        # 0-1000m: Highway, Flat
        # 1000-2000m: Other, Uphill

        # We need to mock _calculate_cumulative_distances to return exact values for testing
        # Or we can just mock the internal call, but let's rely on points that give approx distances
        # For precise testing of INTERSECTION logic, it's better to bypass distance calc if possible
        # or use the internal methods directly.

        # Let's mock the cumulative distances by overriding the method on the instance for this test?
        # No, let's just use a monkeypatch or mock.

        pass

    def test_parse_extra_segments(self):
        # Test parsing logic
        cum_dists = [0, 100, 200, 300, 400]
        extras = {
            "steepness": {
                "values": [
                    [0, 2, 0],  # 0-200m: Flat (0)
                    [2, 4, 1],  # 200-400m: Up (1)
                ]
            }
        }

        segments = self.analyzer._parse_extra_segments(extras, "steepness", cum_dists)
        assert len(segments) == 2
        assert segments[0].start_dist == 0
        assert segments[0].end_dist == 200
        assert segments[0].value == 0

        assert segments[1].start_dist == 200
        assert segments[1].end_dist == 400
        assert segments[1].value == 1

    def test_intersection_logic(self):
        # This is the core logic.
        # We can test private method behavior implicitly via analyze_segments
        # but mocking cum_distances makes it deterministic.

        # Mocking:
        original_calc = self.analyzer._calculate_cumulative_distances
        self.analyzer._calculate_cumulative_distances = lambda pts: [0, 1000, 2000]

        points = [[0, 0], [0, 0], [0, 0]]  # Dummy points
        extras = {
            "waycategory": {
                "values": [
                    [0, 1, 1],  # 0-1000m: Highway (1)
                    [1, 2, 0],  # 1000-2000m: Other (0)
                ]
            },
            "steepness": {
                "values": [
                    [0, 1, 0],  # 0-1000m: Flat (0)
                    [1, 2, 1],  # 1000-2000m: Up (1)
                ]
            },
        }

        stats = self.analyzer.analyze_segments(points, extras)

        # Restore
        self.analyzer._calculate_cumulative_distances = original_calc

        # Expected:
        # Highway (0-1000) & Flat (0-1000) -> 1000m -> 1.0 km
        # Other (1000-2000) & Up (1000-2000) -> 1000m -> 1.0 km

        assert stats["highway"]["flat"] == 1.0
        assert stats["other"]["up"] == 1.0
        assert stats["highway"]["up"] == 0.0

    def test_analyze_segments_scaling(self):
        # Mocking cumulative distances
        original_calc = self.analyzer._calculate_cumulative_distances
        # Override to return [0, 1000, 2000] for 3 points
        self.analyzer._calculate_cumulative_distances = lambda pts: [
            0.0,
            1000.0,
            2000.0,
        ]

        points = [[0, 0], [0, 0], [0, 0]]
        extras = {
            "waycategory": {
                "values": [
                    [0, 2, 1],  # 0-2000m: Category 1 (Highway)
                ]
            },
            "steepness": {
                "values": [
                    [0, 2, 0],  # 0-2000m: Flat
                ]
            },
        }

        # Case 1: No scaling (reference = None)
        stats = self.analyzer.analyze_segments(points, extras)
        # Expected: 2.0 km
        assert stats["highway"]["flat"] == 2.0

        # Case 2: Scaling (reference = 1000m, i.e. 0.5x)
        # We need to pass reference_distance_m to analyze_segments
        # analyze_segments(self, geometry_points, extras, reference_distance_m=None)
        # But wait, my previous edit added this argument.
        stats_scaled = self.analyzer.analyze_segments(
            points, extras, reference_distance_m=1000.0
        )
        # Expected: 1.0 km
        assert stats_scaled["highway"]["flat"] == 1.0

        # Restore
        self.analyzer._calculate_cumulative_distances = original_calc
