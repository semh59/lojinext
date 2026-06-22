"""Offline batch model training (Phase 4.0).

Bu paket eğitim/yeniden kalibrasyon işlerini içerir. Production inference
hot path bu paketi import ETMEZ — runtime sadece
``app.core.ml.predictors`` kullanır.

Modüller:
- ``trainer.Trainer.train_for_vehicle(arac_id)``: tek araç model eğitimi
- ``trainer.Trainer.train_general_model()``: filo seviyesi cold-start model
- ``scheduler_task``: Celery beat haftalık retrain task'ı
"""

from app.core.ml.training.trainer import Trainer

__all__ = ["Trainer"]
