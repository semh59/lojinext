"""Celery app config — broker visibility_timeout vs. task time_limit sanity check.

2026-07-01 prod-grade denetimi P0 #4: broker `visibility_timeout` TÜM
task'lar için tek bir global değerdir (Redis broker, per-task override
edilemez). Bu değer, app'teki en uzun `time_limit`'e sahip task'ın altında
kalırsa, o task normal şekilde bitmeden broker onu "kayıp" sayıp başka bir
worker'a yeniden dağıtır — duplike çalıştırma. Bu test, mevcut/gelecekteki
tüm task time_limit'lerinin `visibility_timeout`'un altında kaldığını
garanti eder (regresyon guard'ı — biri gelecekte daha uzun bir task eklerse
bu test onu yakalar).
"""

import re
from pathlib import Path

import pytest

from app.infrastructure.background.celery_app import get_celery_app

pytestmark = pytest.mark.unit


def test_visibility_timeout_exceeds_longest_task_time_limit():
    app = get_celery_app()
    visibility_timeout = app.conf.broker_transport_options["visibility_timeout"]

    # Tüm @celery_app.task(...) dekoratörlerindeki time_limit= değerlerini
    # (varsa) tara — kod tabanı büyüdükçe yeni bir uzun task eklenirse bu
    # test onu yakalasın diye statik/dinamik değil, dosya taraması yapılır.
    tasks_dir = Path(__file__).resolve().parents[4] / "app" / "workers" / "tasks"
    longest_time_limit = 90  # global task_time_limit varsayılanı (celery_app.py)
    offending: list[str] = []

    for py_file in tasks_dir.glob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        for match in re.finditer(r"time_limit\s*=\s*([A-Za-z_][\w]*|\d+)", text):
            raw = match.group(1)
            if raw.isdigit():
                value = int(raw)
            else:
                # Modül seviyesinde tanımlı bir sabite (ör.
                # WEEKLY_DIGEST_HARD_LIMIT = 3900) işaret ediyor olabilir.
                const_match = re.search(rf"^{raw}\s*=\s*(\d+)", text, re.MULTILINE)
                if not const_match:
                    continue
                value = int(const_match.group(1))
            if value > longest_time_limit:
                longest_time_limit = value
            if value >= visibility_timeout:
                offending.append(f"{py_file.name}: time_limit={value}")

    assert visibility_timeout > longest_time_limit, (
        f"broker visibility_timeout ({visibility_timeout}s) en uzun task "
        f"time_limit'inin ({longest_time_limit}s) üzerinde olmalı — aksi "
        f"halde task normal bitmeden broker onu kayıp sayıp başka worker'a "
        f"yeniden dağıtır (duplike çalıştırma). Sorunlu task'lar: {offending}"
    )
