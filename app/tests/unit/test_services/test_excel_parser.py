"""SafeColumnMapper (excel_column_map.py) unit tests — two-pass strategy."""

import pytest

pytestmark = pytest.mark.unit


class TestExcelParser:
    def test_service_exists(self):
        """SafeColumnMapper class is importable."""
        from v2.modules.import_excel.infrastructure.column_mapper import (
            SafeColumnMapper,
        )

        assert SafeColumnMapper is not None
        assert hasattr(SafeColumnMapper, "map_columns")

    def test_basic_initialization(self):
        """SafeColumnMapper.COLS has entries for key domain columns."""
        from v2.modules.import_excel.infrastructure.column_mapper import (
            SafeColumnMapper,
        )

        assert "plaka" in SafeColumnMapper.COLS
        assert "tarih" in SafeColumnMapper.COLS
        assert "litre" in SafeColumnMapper.COLS

    def test_happy_path_exact_match(self):
        """Exact-match aliases are resolved in the first pass."""
        from v2.modules.import_excel.infrastructure.column_mapper import (
            SafeColumnMapper,
        )

        df_cols = ["tarih", "plaka", "litre", "tutar"]
        mapping = SafeColumnMapper.map_columns(df_cols)

        assert mapping.get("tarih") == "tarih"
        assert mapping.get("plaka") == "plaka"
        assert mapping.get("litre") == "litre"

    def test_exact_match_precedence_over_fuzzy(self):
        """'Plaka' exact-match must NOT be re-mapped to dorse_plakasi by fuzzy."""
        from v2.modules.import_excel.infrastructure.column_mapper import (
            SafeColumnMapper,
        )

        # Both 'Plaka' and 'Dorse Plaka' are present — exact wins.
        df_cols = ["Plaka", "Dorse Plaka"]
        mapping = SafeColumnMapper.map_columns(df_cols)

        assert mapping.get("Plaka") == "plaka"
        if "Dorse Plaka" in mapping:
            assert mapping["Dorse Plaka"] == "dorse_plakasi"

    def test_fuzzy_match_km(self):
        """'km sayacı' should fuzzy-map to km_sayac."""
        from v2.modules.import_excel.infrastructure.column_mapper import (
            SafeColumnMapper,
        )

        df_cols = ["km sayacı"]
        mapping = SafeColumnMapper.map_columns(df_cols)
        assert mapping.get("km sayacı") == "km_sayac"

    def test_error_handling_empty_columns(self):
        """Empty column list returns empty mapping without raising."""
        from v2.modules.import_excel.infrastructure.column_mapper import (
            SafeColumnMapper,
        )

        result = SafeColumnMapper.map_columns([])
        assert result == {}

    def test_edge_case_unknown_columns_not_mapped(self):
        """Columns with no good match are not added to the mapping."""
        from v2.modules.import_excel.infrastructure.column_mapper import (
            SafeColumnMapper,
        )

        df_cols = ["completely_unknown_xyz_column_999"]
        mapping = SafeColumnMapper.map_columns(df_cols)
        # Should not be in mapping at all
        assert "completely_unknown_xyz_column_999" not in mapping

    def test_edge_case_none_like_columns(self):
        """Numeric column names are coerced to strings and processed."""
        from v2.modules.import_excel.infrastructure.column_mapper import (
            SafeColumnMapper,
        )

        # Pandas sometimes yields integer column names for headerless files
        df_cols = [0, 1, 2]
        result = SafeColumnMapper.map_columns(df_cols)
        assert isinstance(result, dict)

    def test_return_type_validation(self):
        """map_columns always returns a dict."""
        from v2.modules.import_excel.infrastructure.column_mapper import (
            SafeColumnMapper,
        )

        result = SafeColumnMapper.map_columns(["tarih", "plaka"])
        assert isinstance(result, dict)

    def test_case_insensitive_exact_match(self):
        """Matching is case-insensitive (lowercased before compare)."""
        from v2.modules.import_excel.infrastructure.column_mapper import (
            SafeColumnMapper,
        )

        df_cols = ["PLAKA", "LITRE", "TARIH"]
        mapping = SafeColumnMapper.map_columns(df_cols)
        assert mapping.get("PLAKA") == "plaka"

    def test_two_pass_no_double_claim(self):
        """A column claimed by exact-match is not also claimed by fuzzy."""
        from v2.modules.import_excel.infrastructure.column_mapper import (
            SafeColumnMapper,
        )

        df_cols = ["plaka", "dorse plaka"]
        mapping = SafeColumnMapper.map_columns(df_cols)

        # Both columns should map to distinct internal keys
        values = list(mapping.values())
        assert len(values) == len(set(values)), "Duplicate internal key assignments"

    async def test_integration_with_mock(self):
        """map_columns works correctly for a typical sefer upload scenario."""
        from v2.modules.import_excel.infrastructure.column_mapper import (
            SafeColumnMapper,
        )

        df_cols = ["tarih", "sofor adi", "plaka", "cikis yeri", "varis yeri", "km"]
        mapping = SafeColumnMapper.map_columns(df_cols)

        assert "tarih" in mapping
        assert mapping["tarih"] == "tarih"
        assert mapping.get("plaka") == "plaka"
