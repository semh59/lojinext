"""
T7-A: Sofor score range constraint — CheckConstraint enforced.

Bug Açıklaması:
  Sofor modelinde score range constraint (0.1 <= score <= 2.0) tanımlı.
  Eğer constraint kaybolmuşsa, invalid score'lar insert edilebilir.

Beklenen: CheckConstraint enforce edilmeli (IntegrityError on violation).
"""

from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError


@pytest.mark.integration
async def test_sofor_score_range_constraint_enforced(db_session):
    """
    T7-A: Sofor score range constraint → 0.1 <= score <= 2.0.

    Senaryo:
    - score=-5.0 oluşturmayı dene (constraint violation)
    - IntegrityError beklenir (CheckConstraint violation)
    """

    from app.database.models import Sofor

    try:
        # Try to create with invalid score (violates constraint)
        sofor = Sofor(
            ad_soyad="Test Sofor T7A",
            telefon="0532 000 00 07",
            ise_baslama=date(2020, 1, 1),
            ehliyet_sinifi="E",
            aktif=True,
            score=-5.0,  # INVALID: must be >= 0.1
            manual_score=-5.0,  # INVALID
            hiz_disiplin_skoru=1.0,
            agresif_surus_faktoru=1.0,
        )

        db_session.add(sofor)
        await db_session.commit()

        # If we get here, constraint is not enforced
        assert False, (
            "T7-A: Score range constraint not enforced! "
            "Sofor allows score=-5.0 (should be >= 0.1). "
            "Sorun: CheckConstraint kayboluyor veya enforce edilmiyor."
        )

    except IntegrityError as e:
        # Expected: constraint violation
        error_text = str(e).lower()
        if "check" in error_text or "xor" in error_text or "constraint" in error_text:
            # Constraint properly enforced
            await db_session.rollback()
            pass
        else:
            await db_session.rollback()
            assert False, (
                f"T7-A: IntegrityError raised but not for XOR constraint. Error: {e}"
            )

    except Exception as e:
        await db_session.rollback()
        assert False, (
            f"T7-A: Unexpected exception: {type(e).__name__}: {e}. "
            f"Expected IntegrityError for constraint violation."
        )
