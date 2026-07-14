"""Shared in-process locks for driver write use-cases.

``SOFOR_WRITE_LOCK`` is a friendly fast-path guard for the
``ad_soyad`` pre-check shared by ``add_sofor``/``update_sofor`` — the real
guard is the DB ``UNIQUE(ad_soyad_bidx)`` constraint (a losing concurrent
insert surfaces as ``IntegrityError``, mapped to 400 by the API layer).

Module-level (not per-call/per-instance): the pre-migration
``SoforService.__init__``'s ``self._lock`` was recreated on every
per-request service instantiation (``get_sofor_service()`` dependency),
making it effectively a no-op across concurrent requests — the same
ineffective-instance-lock finding as fleet's TOCTOU plate-uniqueness guard
(dalga 3). This module-level lock actually serializes callers within one
process, which is a behavioural improvement, not a regression.
"""

import asyncio

SOFOR_WRITE_LOCK = asyncio.Lock()
