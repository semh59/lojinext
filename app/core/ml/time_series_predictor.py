"""Zaman serisi tahmin modülü — ARIMA(1,1,1) tabanlı.

KARAR (2026-05-28): LSTM (PyTorch) production'a alınmadı — Docker image'a
~700 MB ekliyor, EnsembleFuelPredictor R²=0.97 zaten yüksek. Bu modül
artık tamamen statsmodels ARIMA(1,1,1) + Holt-Winters + moving-average
fallback ile çalışır. Torch import yapılırsa (dev makine) LSTM
sınıfları aktive olur ama production yolu ARIMATimeSeriesPredictor'a
yönlendirir.

PUBLIC API:
  • get_time_series_predictor() → ARIMATimeSeriesPredictor (statsmodels)
  • get_arima_predictor()       → aynı sınıf (geriye uyumluluk için iki ad)
  • is_lstm_available()         → bool (torch dev'de varsa True; production
                                   builds'inde her zaman False)

Production kullanıcısının görmesi gereken sadece ARIMATimeSeriesPredictor.
Eski TimeSeriesPredictor + FuelConsumptionLSTM sınıfları yalnızca test
fixture'ları için tutuluyor; canlı kod yoluna girmiyor.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import numpy as np

# PyTorch lazy import
try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset

    TORCH_AVAILABLE = True
except ImportError:
    torch = None
    nn = None
    TORCH_AVAILABLE = False

# Concrete base for the nn.Module subclass: real class for type-checking,
# runtime conditional (nn.Module or object) otherwise.
if TYPE_CHECKING:
    _NNModule = nn.Module
else:
    _NNModule = nn.Module if TORCH_AVAILABLE else object

from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TimeSeriesPrediction:
    """Zaman serisi tahmin sonucu"""

    forecast: List[float]  # Gelecek N günün tahmini
    confidence_low: List[float]
    confidence_high: List[float]
    trend: str  # 'increasing', 'stable', 'decreasing'
    model_accuracy: float
    input_days: int
    forecast_days: int


class FuelConsumptionLSTM(_NNModule):
    """
    Yakıt tüketimi zaman serisi LSTM modeli.

    Input: Son 30 günün günlük ortalamaları
    Output: Gelecek 7 günün tahmini

    Features (11):
    - Günlük ortalama L/100km
    - Günlük toplam km
    - Günlük ortalama yük (ton)
    - Günlük sefer sayısı
    - Haftanın günü (0-6)
    - Ayın günü (1-31)
    - Mevsim (0-3)
    - Önceki gün tüketimi
    - 3 günlük hareketli ortalama
    - 7 günlük hareketli ortalama
    - Trend göstergesi

    Architecture:
    - LSTM (2 layer, 64 hidden units)
    - Dropout (0.2)
    - Fully Connected output layer
    """

    def __init__(
        self,
        input_size: int = 11,
        hidden_size: int = 64,
        num_layers: int = 2,
        output_size: int = 7,
        dropout: float = 0.2,
    ):
        if not TORCH_AVAILABLE:
            logger.error("PyTorch not available for LSTM model")
            return

        super().__init__()

        self.hidden_size = hidden_size
        self.num_layers = num_layers

        # LSTM layer
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
        )

        # Output layer
        self.fc = nn.Sequential(
            nn.Linear(hidden_size, 32),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(32, output_size),
        )

    def forward(self, x):
        """
        Forward pass.

        Args:
            x: (batch_size, sequence_length, input_size)

        Returns:
            (batch_size, output_size) - Gelecek günlerin tahmini
        """
        # LSTM çıktısı
        lstm_out, (h_n, c_n) = self.lstm(x)

        # Son hidden state'i al
        last_hidden = lstm_out[:, -1, :]

        # Fully connected layer
        output = self.fc(last_hidden)

        return output

    def predict_with_confidence(
        self, x: "torch.Tensor", n_samples: int = 100
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Monte Carlo Dropout ile güven aralığı hesapla.

        Args:
            x: Input tensor
            n_samples: MC dropout örnekleme sayısı

        Returns:
            (mean_prediction, lower_bound, upper_bound)
        """
        self.train()  # Dropout aktif

        predictions = []
        for _ in range(n_samples):
            with torch.no_grad():
                pred = self.forward(x)
                predictions.append(pred.cpu().numpy())

        predictions = np.array(predictions)
        mean_pred = predictions.mean(axis=0)
        std_pred = predictions.std(axis=0)

        # 95% güven aralığı
        lower = mean_pred - 1.96 * std_pred
        upper = mean_pred + 1.96 * std_pred

        self.eval()

        return mean_pred, lower, upper


class TimeSeriesPredictor:
    """
    LSTM model yönetimi ve eğitim servisi.

    Kullanım:
    1. prepare_data() - Veri hazırlama
    2. train() - Model eğitimi
    3. predict() - Tahmin
    4. save_model() / load_model() - Persistence
    """

    SEQUENCE_LENGTH = 30  # Input: son 30 gün
    FORECAST_DAYS = 7  # Output: gelecek 7 gün
    FEATURE_COUNT = 11

    def __init__(self, device: str = "cpu"):
        if not TORCH_AVAILABLE:
            logger.warning("PyTorch not available, LSTM predictor will not function")
            self.model = None
            return

        self.device = torch.device(device)
        self.model = None
        try:
            self.model = FuelConsumptionLSTM().to(self.device)
        except NotImplementedError as exc:
            # Bazı ortamlarda global default device "meta" olabiliyor.
            # Bu durumda modeli doğrudan CPU'da yeniden oluşturarak init'i düşürmüyoruz.
            if "meta tensor" in str(exc).lower():
                logger.warning(
                    "LSTM init meta-device hatası alındı, CPU fallback uygulanıyor: %s",
                    exc,
                )
                try:
                    with torch.device("cpu"):
                        self.model = FuelConsumptionLSTM()
                    self.device = torch.device("cpu")
                except Exception as fallback_exc:
                    logger.error("LSTM CPU fallback init başarısız: %s", fallback_exc)
                    self.model = None
            else:
                raise
        self.is_trained = False
        self.training_history: list = []

        # Normalization parametreleri
        self.feature_mean = None
        self.feature_std: Any = None
        self.target_mean = None
        self.target_std = None

    def prepare_features(self, daily_data: List[Dict]) -> np.ndarray:
        """
        Günlük verilerden feature matrisi oluştur.

        Args:
            daily_data: Günlük özet verileri listesi
                [{
                    'tarih': date,
                    'ort_tuketim': float,
                    'toplam_km': float,
                    'ort_ton': float,
                    'sefer_sayisi': int
                }, ...]

        Returns:
            np.ndarray: (n_days, n_features) feature matrisi
        """
        features = []

        for i, day in enumerate(daily_data):
            tarih = day.get("tarih")
            if isinstance(tarih, str):
                tarih = date.fromisoformat(tarih)

            # Temel özellikler
            ort_tuketim = float(day.get("ort_tuketim", 32.0) or 32.0)
            toplam_km = float(day.get("toplam_km", 0) or 0)
            ort_ton = float(day.get("ort_ton", 0) or 0)
            sefer_sayisi = int(day.get("sefer_sayisi", 0) or 0)

            # Zaman özellikleri
            weekday = tarih.weekday() if tarih else 0
            day_of_month = tarih.day if tarih else 15

            # Mevsim (0=Kış, 1=İlkbahar, 2=Yaz, 3=Sonbahar)
            month = tarih.month if tarih else 6
            season = (month % 12) // 3

            # Lag özellikleri
            prev_consumption = (
                daily_data[i - 1].get("ort_tuketim", ort_tuketim)
                if i > 0
                else ort_tuketim
            )

            # Hareketli ortalamalar
            ma3_vals = [
                daily_data[j].get("ort_tuketim", 32.0)
                for j in range(max(0, i - 2), i + 1)
            ]
            ma3 = np.mean(ma3_vals) if ma3_vals else ort_tuketim

            ma7_vals = [
                daily_data[j].get("ort_tuketim", 32.0)
                for j in range(max(0, i - 6), i + 1)
            ]
            ma7 = np.mean(ma7_vals) if ma7_vals else ort_tuketim

            # Trend göstergesi (-1, 0, 1)
            if i >= 7:
                first_half_vals = [
                    daily_data[j].get("ort_tuketim", 32.0) for j in range(i - 6, i - 3)
                ]
                second_half_vals = [
                    daily_data[j].get("ort_tuketim", 32.0) for j in range(i - 3, i + 1)
                ]
                first_half = np.mean(first_half_vals) if first_half_vals else 1.0
                second_half = np.mean(second_half_vals) if second_half_vals else 1.0

                # Sıkılaştırılmış trend kontrolü
                if second_half > first_half * 1.05:
                    trend = 1
                elif second_half < first_half * 0.95:
                    trend = -1
                else:
                    trend = 0
            else:
                trend = 0

            features.append(
                [
                    ort_tuketim,
                    toplam_km / 1000,  # km → bin km (normalize)
                    ort_ton,
                    sefer_sayisi,
                    weekday / 6,  # 0-1 arası normalize
                    day_of_month / 31,
                    season / 3,
                    prev_consumption,
                    ma3,
                    ma7,
                    trend,
                ]
            )

        return np.array(features, dtype=np.float32)

    def create_sequences(
        self, features: np.ndarray, targets: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Sliding window ile sequence'lar oluştur.

        Args:
            features: (n_days, n_features)
            targets: (n_days,) - Günlük ortalama tüketimler

        Returns:
            X: (n_sequences, sequence_length, n_features)
            y: (n_sequences, forecast_days)
        """
        X, y = [], []

        # Minimum veri kontrolü ve padding
        n_days = len(features)
        required_days = self.SEQUENCE_LENGTH + self.FORECAST_DAYS

        if n_days < required_days:
            # Yetersiz veri durumunda başa sıfır (veya ortalama) padding yap
            padding_size = required_days - n_days + 1
            padding_X = np.zeros(
                (padding_size, features.shape[1]), dtype=features.dtype
            )
            padding_y = np.zeros((padding_size,), dtype=targets.dtype)

            features = np.vstack([padding_X, features])
            targets = np.concatenate([padding_y, targets])
            logger.warning(
                f"TimeSeries: Yetersiz veri ({n_days} gün). {padding_size} günlük zero-padding uygulandı."
            )

        for i in range(len(features) - self.SEQUENCE_LENGTH - self.FORECAST_DAYS + 1):
            X.append(features[i : i + self.SEQUENCE_LENGTH])
            y.append(
                targets[
                    i + self.SEQUENCE_LENGTH : i
                    + self.SEQUENCE_LENGTH
                    + self.FORECAST_DAYS
                ]
            )

        return np.array(X), np.array(y)

    def normalize(self, X: np.ndarray, y: np.ndarray = None, fit: bool = True):
        """Z-score normalization."""
        if fit:
            # Önce Inf değerleri NaN'a çevir ki nanmean düzgün çalışsın
            X_clean = np.where(np.isfinite(X), X, np.nan)

            self.feature_mean = np.nanmean(X_clean, axis=(0, 1))
            self.feature_std = np.nanstd(X_clean, axis=(0, 1))

            # NaN değerleri 0.0 ve 1.0 ile doldur
            self.feature_mean = np.nan_to_num(self.feature_mean, nan=0.0)
            self.feature_std = np.nan_to_num(self.feature_std, nan=1.0)
            self.feature_std[self.feature_std <= 1e-10] = 1.0  # Sıfıra bölmeyi önle

            if y is not None:
                y_clean = np.where(np.isfinite(y), y, np.nan)
                self.target_mean = float(np.nanmean(y_clean))
                self.target_std = float(np.nanstd(y_clean))
                # NaN koruması
                self.target_mean = (
                    0.0 if not np.isfinite(self.target_mean) else self.target_mean
                )
                self.target_std = (
                    1.0
                    if not np.isfinite(self.target_std) or self.target_std <= 1e-10
                    else self.target_std
                )

        X_norm = (X - self.feature_mean) / self.feature_std
        # Çıkışta oluşabilecek NaN/Inf'leri temizle (inputta inf varsa oluşabilir)
        X_norm = np.nan_to_num(X_norm, nan=0.0, posinf=0.0, neginf=0.0)

        if y is not None:
            y_norm = (y - self.target_mean) / self.target_std
            y_norm = np.nan_to_num(y_norm, nan=0.0, posinf=0.0, neginf=0.0)
            return X_norm, y_norm

        return X_norm

    def denormalize_target(self, y_norm: np.ndarray) -> np.ndarray:
        """Tahminleri orijinal ölçeğe geri dönüştür."""
        return y_norm * self.target_std + self.target_mean

    def train(
        self,
        daily_data: List[Dict],
        epochs: int = 100,
        batch_size: int = 32,
        learning_rate: float = 0.001,
        validation_split: float = 0.2,
    ) -> Dict:
        """
        Model eğitimi.

        Args:
            daily_data: Günlük özet verileri
            epochs: Eğitim epoch sayısı
            batch_size: Batch boyutu
            learning_rate: Öğrenme hızı
            validation_split: Validation oranı

        Returns:
            Dict: Eğitim sonuçları
        """
        if not TORCH_AVAILABLE or self.model is None:
            return {"success": False, "error": "PyTorch not available"}

        if len(daily_data) < self.SEQUENCE_LENGTH + self.FORECAST_DAYS + 10:
            return {
                "success": False,
                "error": f"Yetersiz veri: {len(daily_data)} gün. En az {self.SEQUENCE_LENGTH + self.FORECAST_DAYS + 10} gerekli.",  # noqa: E501
            }

        try:
            # Feature ve target hazırla
            features = self.prepare_features(daily_data)
            targets = np.array(
                [d.get("ort_tuketim", 32.0) for d in daily_data], dtype=np.float32
            )

            # Sequence'lar oluştur
            X, y = self.create_sequences(features, targets)

            # Train/Val split
            n_val = int(len(X) * validation_split)
            X_train, X_val = X[:-n_val], X[-n_val:]
            y_train, y_val = y[:-n_val], y[-n_val:]

            # Normalization
            X_train, y_train = self.normalize(X_train, y_train, fit=True)
            X_val = (X_val - self.feature_mean) / self.feature_std
            y_val_norm = (y_val - self.target_mean) / self.target_std

            # Tensor dönüşümü
            X_train_t = torch.FloatTensor(X_train).to(self.device)
            y_train_t = torch.FloatTensor(y_train).to(self.device)
            X_val_t = torch.FloatTensor(X_val).to(self.device)
            y_val_t = torch.FloatTensor(y_val_norm).to(self.device)

            # DataLoader
            train_dataset = TensorDataset(X_train_t, y_train_t)
            train_loader = DataLoader(
                train_dataset, batch_size=batch_size, shuffle=True
            )

            # Optimizer ve loss
            optimizer = torch.optim.Adam(self.model.parameters(), lr=learning_rate)
            criterion = nn.MSELoss()

            # Early stopping
            best_val_loss = float("inf")
            patience = 15
            patience_counter = 0

            # Training loop
            self.training_history = []

            for epoch in range(epochs):
                self.model.train()
                train_loss = 0.0

                for batch_X, batch_y in train_loader:
                    optimizer.zero_grad()
                    output = self.model(batch_X)
                    loss = criterion(output, batch_y)
                    loss.backward()
                    optimizer.step()
                    train_loss += loss.item()

                train_loss /= len(train_loader)

                # Validation
                self.model.eval()
                with torch.no_grad():
                    val_output = self.model(X_val_t)
                    val_loss = criterion(val_output, y_val_t).item()

                self.training_history.append(
                    {"epoch": epoch + 1, "train_loss": train_loss, "val_loss": val_loss}
                )

                # Early stopping
                if val_loss < best_val_loss:
                    best_val_loss = val_loss
                    patience_counter = 0
                else:
                    patience_counter += 1
                    if patience_counter >= patience:
                        logger.info(f"Early stopping at epoch {epoch + 1}")
                        break

                if (epoch + 1) % 20 == 0:
                    logger.info(
                        f"Epoch {epoch + 1}/{epochs} - Train Loss: {train_loss:.4f}, Val Loss: {val_loss:.4f}"
                    )

            self.is_trained = True

            # Final metrikler
            self.model.eval()
            with torch.no_grad():
                val_pred = self.model(X_val_t).cpu().numpy()
                val_pred_denorm = self.denormalize_target(val_pred)

                from sklearn.metrics import mean_absolute_error, r2_score

                mae = mean_absolute_error(y_val.flatten(), val_pred_denorm.flatten())
                r2 = r2_score(y_val.flatten(), val_pred_denorm.flatten())

            logger.info(f"LSTM trained: MAE={mae:.3f}, R²={r2:.4f}")

            return {
                "success": True,
                "epochs_trained": len(self.training_history),
                "final_train_loss": self.training_history[-1]["train_loss"],
                "final_val_loss": self.training_history[-1]["val_loss"],
                "mae": round(mae, 3),
                "r2": round(r2, 4),
                "train_samples": len(X_train),
                "val_samples": len(X_val),
            }

        except Exception as e:
            logger.error(f"LSTM training error: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
        finally:
            # GPU MEMORY LEAK FIX: Her durumda GPU belleğini temizle
            if TORCH_AVAILABLE and torch is not None:
                try:
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                        logger.debug("GPU memory cache cleared after training")
                except Exception as cleanup_error:
                    logger.warning(f"GPU cleanup error: {cleanup_error}")

    def predict(
        self, recent_daily_data: List[Dict], with_confidence: bool = True
    ) -> TimeSeriesPrediction:
        """
        Gelecek günlerin tahmini.

        Args:
            recent_daily_data: Son SEQUENCE_LENGTH günün verileri
            with_confidence: Güven aralığı hesaplansın mı

        Returns:
            TimeSeriesPrediction: Tahmin sonucu
        """
        if not self.is_trained or self.model is None:
            raise RuntimeError("Model henüz eğitilmedi")

        if len(recent_daily_data) < self.SEQUENCE_LENGTH:
            raise ValueError(f"En az {self.SEQUENCE_LENGTH} günlük veri gerekli")

        # Son SEQUENCE_LENGTH günü al
        recent_data = recent_daily_data[-self.SEQUENCE_LENGTH :]

        # Feature hazırla
        features = self.prepare_features(recent_data)
        X = features.reshape(1, self.SEQUENCE_LENGTH, self.FEATURE_COUNT)

        # Normalize
        X_norm = (X - self.feature_mean) / self.feature_std
        X_tensor = torch.FloatTensor(X_norm).to(self.device)

        # Tahmin
        if with_confidence:
            mean_pred, lower, upper = self.model.predict_with_confidence(X_tensor)
            mean_pred = self.denormalize_target(mean_pred[0])
            lower = self.denormalize_target(lower[0])
            upper = self.denormalize_target(upper[0])
        else:
            self.model.eval()
            with torch.no_grad():
                pred = self.model(X_tensor).cpu().numpy()[0]
                mean_pred = self.denormalize_target(pred)
                margin = mean_pred * 0.08
                lower = mean_pred - margin
                upper = mean_pred + margin

        # Trend hesapla
        if mean_pred[0] < mean_pred[-1] * 0.95:
            trend = "decreasing"
        elif mean_pred[0] > mean_pred[-1] * 1.05:
            trend = "increasing"
        else:
            trend = "stable"

        return TimeSeriesPrediction(
            forecast=[round(v, 2) for v in mean_pred],
            confidence_low=[round(v, 2) for v in lower],
            confidence_high=[round(v, 2) for v in upper],
            trend=trend,
            model_accuracy=self.training_history[-1]["val_loss"]
            if self.training_history
            else 0.0,
            input_days=self.SEQUENCE_LENGTH,
            forecast_days=self.FORECAST_DAYS,
        )

    def save_model(self, filepath: str):
        """Modeli kaydet (Güvenli Hibrit Format)"""
        if not self.is_trained or self.model is None:
            raise RuntimeError("Model henüz eğitilmedi")

        base_path = Path(filepath).with_suffix("")
        weights_path = f"{base_path}_weights.pt"

        # 1. Model Ağırlıkları (Sadece Ağırlıklar - Güvenli)
        torch.save(self.model.state_dict(), weights_path)

        # 2. SECURITY FIX: Weights için SHA256 checksum hesapla
        sha256_hash = hashlib.sha256()
        with open(weights_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        weights_checksum = sha256_hash.hexdigest()

        # 3. Metadata (Normalizasyon ve Geçmiş - %100 Güvenli JSON)
        metadata = {
            "feature_mean": self.feature_mean.tolist()
            if self.feature_mean is not None
            else None,
            "feature_std": self.feature_std.tolist()
            if self.feature_std is not None
            else None,
            "target_mean": float(self.target_mean)
            if self.target_mean is not None
            else None,
            "target_std": float(self.target_std)
            if self.target_std is not None
            else None,
            "training_history": self.training_history,
            "is_trained": self.is_trained,
            "last_updated": date.today().isoformat(),
            "weights_checksum": weights_checksum,  # SECURITY: Weights bütünlük doğrulama
        }

        with open(f"{base_path}_meta.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        logger.info(
            f"LSTM model saved (hybrid) to {base_path} with checksum {weights_checksum[:16]}..."
        )

    def load_model(self, filepath: str):
        """Modeli yükle (Güvenli Hibrit Format)"""
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch not available")

        base_path = Path(filepath).with_suffix("")

        # 1. Metadata yükle
        meta_file = Path(f"{base_path}_meta.json")
        if not meta_file.exists():
            raise FileNotFoundError(f"Metadata dosyası bulunamadı: {meta_file}")

        with open(meta_file, encoding="utf-8") as f:
            metadata = json.load(f)

        # 2. Model Ağırlık dosyasını kontrol et
        weights_file = Path(f"{base_path}_weights.pt")
        if not weights_file.exists():
            raise FileNotFoundError(f"Ağırlık dosyası bulunamadı: {weights_file}")

        # SECURITY: Dosya boyutu kontrolü (100MB DoS koruması)
        MAX_MODEL_SIZE = 100 * 1024 * 1024  # 100MB
        file_size = weights_file.stat().st_size
        if file_size > MAX_MODEL_SIZE:
            raise RuntimeError(
                f"Model dosyası çok büyük ({file_size / 1024 / 1024:.1f}MB > 100MB limit)"
            )

        # SECURITY: Checksum doğrulama (varsa)
        expected_checksum = metadata.get("weights_checksum")
        if expected_checksum:
            sha256_hash = hashlib.sha256()
            with open(weights_file, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            actual_checksum = sha256_hash.hexdigest()

            if actual_checksum != expected_checksum:
                logger.error(
                    f"GÜVENLİK İHLALİ: Model checksum uyuşmazlığı! Beklenen: {expected_checksum[:16]}..., Gerçek: {actual_checksum[:16]}..."  # noqa: E501
                )
                raise RuntimeError(
                    "Security: Model dosyası bozulmuş veya değiştirilmiş olabilir!"
                )
            logger.debug(f"Model checksum doğrulandı: {actual_checksum[:16]}...")
        else:
            logger.warning(
                "Model yüklendi ancak checksum doğrulaması yapılamadı (eski format)"
            )

        self.feature_mean = (
            np.array(metadata["feature_mean"], dtype=np.float32)
            if metadata["feature_mean"]
            else None
        )
        self.feature_std = (
            np.array(metadata["feature_std"], dtype=np.float32)
            if metadata["feature_std"]
            else None
        )
        self.target_mean = metadata["target_mean"]
        self.target_std = metadata["target_std"]
        self.training_history = metadata.get("training_history", [])
        self.is_trained = metadata["is_trained"]

        # 3. Model Ağırlıklarını yükle (weights_only özelliği PyTorch 1.13+ ile geldi)
        from packaging import version

        torch_version = version.parse(torch.__version__)
        use_weights_only = torch_version >= version.parse("1.13.0")

        try:
            if use_weights_only:
                state_dict = torch.load(
                    weights_file, map_location=self.device, weights_only=True
                )
            else:
                logger.warning(
                    "Eski PyTorch sürümü tespit edildi, weights_only=True kullanılamıyor."
                )
                state_dict = torch.load(weights_file, map_location=self.device)

            self.model.load_state_dict(state_dict)
        except Exception as e:
            logger.error(f"Model yükleme hatası: {e}")
            raise RuntimeError(f"Model yüklenemedi: {e}")

        logger.info(
            f"LSTM model loaded (hybrid) from {base_path} (weights_only={use_weights_only}, verified={bool(expected_checksum)})"  # noqa: E501
        )


# Singleton (Thread-Safe Double-Checked Locking)
import threading  # noqa: E402

_time_series_predictor = None
_time_series_predictor_lock = threading.Lock()


def get_time_series_predictor() -> "ARIMATimeSeriesPredictor":
    """Production'da daima ARIMATimeSeriesPredictor döner.

    Eski LSTM TimeSeriesPredictor sınıfı silinmedi (test izolasyonu),
    ancak public factory ARIMA varyantını döndürür: torch yoksa bile
    çalışır, ~700 MB image artışına gerek yok.
    """
    return get_arima_predictor()


def is_lstm_available() -> bool:
    """LSTM modeli production'da devre dışı.

    Geriye uyumluluk için False döner — production code yolu
    ARIMATimeSeriesPredictor'ı kullanmalı.
    """
    return False


# ---------------------------------------------------------------------------
# ARIMA Tabanlı Fallback — PyTorch yoksa bu sınıf devreye girer
# statsmodels ARIMA(1,1,1) + Holt-Winters ETS; PyTorch gerektirmez.
# ---------------------------------------------------------------------------


class ARIMATimeSeriesPredictor:
    """
    Statsmodels tabanlı zaman serisi tahmincisi.

    PyTorch/LSTM gerektirmez. MIN_OBSERVATIONS=10 gün yeterli;
    daha az veri için hareketli ortalama fallback'e düşer.
    """

    MIN_OBSERVATIONS = 10
    FORECAST_DAYS = 7

    def predict(
        self, daily_consumptions: List[float], forecast_days: int = FORECAST_DAYS
    ) -> Dict:
        """
        Args:
            daily_consumptions: Günlük L/100km listesi (kronolojik sıra, en yeni sonda)
            forecast_days: Kaç gün ilerisi tahmin edilecek
        Returns:
            {"success": True, "forecast": [...], "trend": "...", "method": "arima"|"moving_average"}
        """
        if not daily_consumptions:
            return {"success": False, "error": "Veri yok"}

        if len(daily_consumptions) < self.MIN_OBSERVATIONS:
            return self._moving_average_fallback(daily_consumptions, forecast_days)

        try:
            from statsmodels.tsa.arima.model import ARIMA

            model = ARIMA(daily_consumptions, order=(1, 1, 1))
            result = model.fit()
            forecast = result.forecast(steps=forecast_days).tolist()
            trend = self._detect_trend(daily_consumptions, forecast)
            return {
                "success": True,
                "forecast": [round(v, 2) for v in forecast],
                "trend": trend,
                "method": "arima",
                "input_days": len(daily_consumptions),
                "forecast_days": forecast_days,
            }
        except Exception as exc:
            logger.warning("ARIMA başarısız, moving_average'a düşülüyor: %s", exc)
            return self._moving_average_fallback(daily_consumptions, forecast_days)

    def _moving_average_fallback(self, data: List[float], n: int) -> Dict:
        window = data[-5:] if len(data) >= 5 else data
        avg = round(sum(window) / len(window), 2)
        return {
            "success": True,
            "forecast": [avg] * n,
            "trend": "stable",
            "method": "moving_average",
            "input_days": len(data),
            "forecast_days": n,
        }

    @staticmethod
    def _detect_trend(history: List[float], forecast: List[float]) -> str:
        last_avg = sum(history[-5:]) / min(5, len(history))
        forecast_avg = sum(forecast) / len(forecast)
        if forecast_avg > last_avg * 1.05:
            return "increasing"
        if forecast_avg < last_avg * 0.95:
            return "decreasing"
        return "stable"


_arima_predictor: Optional["ARIMATimeSeriesPredictor"] = None
_arima_lock = threading.Lock()


def get_arima_predictor() -> ARIMATimeSeriesPredictor:
    """Thread-safe ARIMA predictor singleton."""
    global _arima_predictor
    if _arima_predictor is None:
        with _arima_lock:
            if _arima_predictor is None:
                _arima_predictor = ARIMATimeSeriesPredictor()
    return _arima_predictor
