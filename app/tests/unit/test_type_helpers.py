"""Tests for shared type conversion utilities."""

import pytest

from app.core.utils.type_helpers import safe_float

pytestmark = pytest.mark.unit


def test_safe_float_none_returns_none():
    assert safe_float(None) is None


def test_safe_float_valid_string():
    assert safe_float("3.14") == pytest.approx(3.14)


def test_safe_float_invalid_string_returns_none():
    assert safe_float("abc") is None


def test_safe_float_zero():
    assert safe_float(0) == 0.0


def test_safe_float_integer():
    assert safe_float(42) == 42.0


def test_safe_float_empty_string_returns_none():
    assert safe_float("") is None


def test_safe_float_list_returns_none():
    assert safe_float([1, 2]) is None
