"""Phase 4.0 — predictors / training ayrım smoke testleri.

Hedefler:
1. ``predictors`` paketi import edildiğinde **xgboost/lightgbm/sklearn**
   modül-seviyesinde yüklenmemiş olmalı (lazy import garantisi).
2. ``training`` paketi inference path'inden ASLA import edilmemeli.
3. ``EnsemblePredictor`` constructor diskten model yükleyebilmeli (mock'lu
   pickle ile).
4. ``Trainer`` lazy: constructor xgboost vs. yüklemez, sadece run() çağrısı
   yükler.

Notlar:
- Bu testler **import side-effects'i** ölçer; gerçek model dosyası yok.
- Lazy import kontrolü: ``sys.modules`` içinde anahtarın YOK olmasıyla.
"""

from __future__ import annotations

import importlib
import sys

import pytest


def _purge(*names: str) -> None:
    """Test öncesi modül cache'i temizler (önceki test'ler import etmiş olabilir)."""
    for n in list(sys.modules):
        if any(n == name or n.startswith(name + ".") for name in names):
            del sys.modules[n]


def test_importing_predictors_does_not_trigger_ml_heavy_libs():
    """``predictors`` paketi sadece sayfa açılınca hot-load olmamalı."""
    _purge("app.core.ml.predictors", "xgboost", "lightgbm", "sklearn")

    importlib.import_module("app.core.ml.predictors")

    # ML libs henüz constructor çağrılmadığı için yüklenmemeli
    assert "xgboost" not in sys.modules, (
        "predictors import etmek xgboost'u modül seviyesinde yüklemiş — "
        "lazy import bozulmuş"
    )
    assert "lightgbm" not in sys.modules


def test_importing_training_does_not_trigger_ensemble_core_at_module_level():
    """``training`` paketi de aynı şekilde lazy olmalı."""
    _purge("app.core.ml.training", "app.core.ml.ensemble_core", "xgboost", "lightgbm")

    importlib.import_module("app.core.ml.training")

    # Trainer constructor henüz çağrılmadığı için service ve ensemble_core
    # yüklenmemeli
    assert "app.core.ml.ensemble_core" not in sys.modules


def test_predictors_package_does_not_import_training():
    """Inference path training paketine ASLA bağımlı olmamalı."""
    _purge("app.core.ml.predictors", "app.core.ml.training")
    importlib.import_module("app.core.ml.predictors")
    assert "app.core.ml.training" not in sys.modules, (
        "predictors training paketini import etti — Phase 4.0 ayrım kuralı ihlali"
    )


def test_ensemble_predictor_lazy_imports_ensemble_core_in_constructor():
    """``EnsemblePredictor()`` constructor diskten yüklerken lazy import yapar."""
    _purge("app.core.ml.ensemble_core")
    from app.core.ml.predictors.ensemble_predictor import EnsemblePredictor

    # Constructor çağrılmadan ensemble_core import edilmemeli
    assert "app.core.ml.ensemble_core" not in sys.modules

    # Olmayan path → FileNotFoundError + ensemble_core yine yüklenir
    with pytest.raises(FileNotFoundError):
        EnsemblePredictor(model_path="/tmp/nonexistent_model_path_xyz")

    # Constructor çağrıldıktan sonra lazy import gerçekleşmiş olmalı
    assert "app.core.ml.ensemble_core" in sys.modules


def test_ensemble_predictor_has_no_training_methods():
    """API type-level enforcement: fit/save/train metodları YOK."""
    from app.core.ml.predictors.ensemble_predictor import EnsemblePredictor

    assert not hasattr(EnsemblePredictor, "fit")
    assert not hasattr(EnsemblePredictor, "save_model")
    assert not hasattr(EnsemblePredictor, "train")
    assert not hasattr(EnsemblePredictor, "train_for_vehicle")
    # Inference API present
    assert hasattr(EnsemblePredictor, "predict")


def test_trainer_lazy_loads_service():
    """``Trainer()`` constructor lightweight — service lazy."""
    from app.core.ml.training.trainer import Trainer

    t = Trainer()
    assert t._service is None  # noqa: SLF001 — internal smoke

    # service property çağrılmadan ensemble_service yüklenmemiş olmalı
    # (zaten önceki test'ler import etmiş olabilir, sadece _service None kontrolü)
