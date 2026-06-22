import glob
import os
import pickle
import shutil
import sys
from datetime import datetime

_MIN_MODEL_BYTES = 1024  # Reject obviously empty/corrupt files


def _validate_model(filepath: str) -> str | None:
    """Return an error string if the pkl file is invalid, else None."""
    try:
        size = os.path.getsize(filepath)
    except OSError as exc:
        return f"cannot stat: {exc}"
    if size < _MIN_MODEL_BYTES:
        return f"file too small ({size} bytes) — likely corrupt"
    try:
        with open(filepath, "rb") as fh:
            pickle.load(fh)  # noqa: S301
    except Exception as exc:
        return f"pickle load failed: {exc}"
    return None


def deploy_models(dry_run: bool = False) -> bool:
    """
    Yeni modelleri production klasörüne deploy et.

    Returns True if all models validated and (when not dry_run) deployed.
    """
    mode = "DRY-RUN" if dry_run else "LIVE"
    print(f"\nDEPLOYING NEW MODELS (v3) [{mode}]...")

    model_dir = "app/core/ml/models"
    backup_dir = f"app/core/ml/models/backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    v3_models = glob.glob(f"{model_dir}/vehicle_*_v3.pkl")
    if not v3_models:
        print("No v3 models found. Nothing to deploy.")
        return False

    # Validation gate — run before any file is touched.
    errors = []
    for v3_file in v3_models:
        err = _validate_model(v3_file)
        if err:
            errors.append(f"  FAIL {v3_file}: {err}")
    if errors:
        print("Validation FAILED — aborting deployment:")
        for e in errors:
            print(e)
        return False
    print(f"Validation OK: {len(v3_models)} model(s) passed.")

    if dry_run:
        for v3_file in v3_models:
            base_name = os.path.basename(v3_file).replace("_v3", "")
            dest = os.path.join(model_dir, base_name)
            print(f"  [dry-run] would promote: {v3_file} -> {dest}")
        return True

    # 1. Backup existing models.
    if os.path.exists(model_dir):
        os.makedirs(backup_dir, exist_ok=True)
        for f in glob.glob(f"{model_dir}/vehicle_*.pkl"):
            if "_v3" not in f:
                shutil.copy(f, backup_dir)
        print(f"Backed up existing models to {backup_dir}")

    # 2. Promote validated v3 models.
    for v3_file in v3_models:
        base_name = os.path.basename(v3_file).replace("_v3", "")
        dest = os.path.join(model_dir, base_name)
        shutil.copy(v3_file, dest)
        print(f"  Promoted: {v3_file} -> {dest}")

    print("\nDEPLOYMENT COMPLETE!")
    return True


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    ok = deploy_models(dry_run=dry)
    sys.exit(0 if ok else 1)
