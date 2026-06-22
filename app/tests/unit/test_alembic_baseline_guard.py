from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


def test_baseline_downgrade_raises() -> None:
    migration_path = Path("alembic/versions/0001_baseline_manual.py")
    spec = spec_from_file_location("baseline_manual_migration", migration_path)
    assert spec is not None and spec.loader is not None

    module = module_from_spec(spec)
    spec.loader.exec_module(module)

    with pytest.raises(NotImplementedError):
        module.downgrade()
