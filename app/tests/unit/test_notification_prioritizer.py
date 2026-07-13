"""NotificationPrioritizer testleri."""

import pytest

from v2.modules.notification.domain.prioritizer import score_priority

pytestmark = pytest.mark.unit


def test_high_read_rate_is_high_priority():
    # 8/10 okunmuş bir olay tipi → önemli (high)
    assert score_priority(read=8, total=10) == "high"


def test_low_read_rate_is_low_priority():
    # 1/20 okunmuş → kullanıcı umursamıyor (low)
    assert score_priority(read=1, total=20) == "low"


def test_insufficient_history_is_normal():
    # az veri → normal (varsayılan)
    assert score_priority(read=0, total=2) == "normal"
    assert score_priority(read=0, total=0) == "normal"


def test_mid_read_rate_is_normal():
    # 5/10 = 0.5 → ne high (>=0.6) ne low (<=0.2) → normal
    assert score_priority(read=5, total=10) == "normal"
