"""
Advanced Time-Series Forecasting Engine for TIR Fuel Consumption

Architecture stack (auto-selected by data availability):
  < 10 obs  → Exponential moving average
  10-30 obs → Holt-Winters ETS (additive)
  30-90 obs → SARIMA(1,1,1)(1,1,1,7) + Holt-Winters ensemble
  90+ obs   → BiLSTM-Attention + TCN ensemble (+ statistical fallback)

Model highlights:
  • BiLSTMAttention  — 2-layer bidirectional LSTM + 8-head self-attention +
                       layer norm + residual connections
  • TCN              — dilated causal convolutions (dilation 1..32), residual
                       blocks, weight normalization
  • HybridForecaster — blended BiLSTM + TCN with walk-forward CV weighting
  • MC Dropout       — 50 stochastic forward passes → 95 % confidence interval
  • Feature engine   — cyclical (sin/cos) day/month, multi-lag, rolling stats,
                       trend slope, calendar flags
"""

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

import numpy as np

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch.optim import AdamW
    from torch.optim.lr_scheduler import CosineAnnealingLR
    from torch.utils.data import DataLoader, TensorDataset

    TORCH_AVAILABLE = True
except ImportError:
    # Optional dependency: keep names bound so module imports without torch.
    torch = nn = F = AdamW = CosineAnnealingLR = DataLoader = TensorDataset = None  # type: ignore[misc]
    TORCH_AVAILABLE = False

# Concrete base for the nn.Module subclasses: the real class for type-checking,
# the runtime conditional (nn.Module or object) otherwise.
if TYPE_CHECKING:
    _NNModule = nn.Module
else:
    _NNModule = nn.Module if TORCH_AVAILABLE else object

from v2.modules.platform_infra.logging.logger import get_logger

logger = get_logger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

SEQ_LEN = 30  # look-back window (days)
FORECAST_DAYS = 7  # prediction horizon
N_FEATURES = 24  # engineered feature count (see FeatureEngine)
MC_SAMPLES = 50  # Monte Carlo dropout passes
DEVICE = "cpu"  # CPU-only (GPU available but not needed for this workload)


# ── Feature Engineering ────────────────────────────────────────────────────────


class FeatureEngine:
    """
    Transforms raw daily fuel records into a rich feature matrix.

    Input per day: {"date": date, "consumption": float (L/100km),
                    "km": float, "ton": float, "trips": int}
    Output: np.ndarray of shape (n_days, N_FEATURES)

    Features (24):
     0-1   sin/cos day-of-week          (cyclical)
     2-3   sin/cos day-of-month         (cyclical)
     4-5   sin/cos month                (cyclical)
     6     is_weekend                   (binary)
     7     is_month_start               (binary, day<=3)
     8     consumption_raw              (L/100km, z-normalised)
     9     km_raw                       (z-normalised)
    10     ton_raw                      (z-normalised)
    11     trips_raw                    (z-normalised)
    12     lag_1                        (prev-day consumption, normalised)
    13     lag_2
    14     lag_7                        (same weekday last week)
    15     lag_14
    16     roll_mean_3                  (3-day rolling mean)
    17     roll_std_3
    18     roll_mean_7
    19     roll_std_7
    20     roll_mean_14
    21     roll_min_14
    22     roll_max_14
    23     trend_slope                  (linear slope over last 14 days)
    """

    def __init__(self):
        self._mu: Optional[np.ndarray] = None
        self._sigma: Optional[np.ndarray] = None
        self._fitted = False

    # ── public API ─────────────────────────────────────────────────────────────

    def fit_transform(self, records: List[Dict]) -> np.ndarray:
        raw = self._build_raw(records)
        self._mu = raw.mean(axis=0)
        self._sigma = np.where(raw.std(axis=0) < 1e-8, 1.0, raw.std(axis=0))
        self._fitted = True
        return (raw - self._mu) / self._sigma

    def transform(self, records: List[Dict]) -> np.ndarray:
        raw = self._build_raw(records)
        if not self._fitted:
            return raw
        return (raw - self._mu) / self._sigma

    def inverse_target(self, y_norm: np.ndarray) -> np.ndarray:
        if not self._fitted:
            return y_norm
        return y_norm * self._sigma[8] + self._mu[8]

    # ── internals ──────────────────────────────────────────────────────────────

    def _build_raw(self, records: List[Dict]) -> np.ndarray:
        n = len(records)
        out = np.zeros((n, N_FEATURES), dtype=np.float32)

        consumptions = np.array(
            [r.get("consumption", 0.0) for r in records], dtype=np.float32
        )
        kms = np.array([r.get("km", 0.0) for r in records], dtype=np.float32)
        tons = np.array([r.get("ton", 0.0) for r in records], dtype=np.float32)
        trips = np.array([r.get("trips", 0) for r in records], dtype=np.float32)

        for i, rec in enumerate(records):
            d = rec.get("date")
            if d is None:
                d = date.today()
            elif isinstance(d, str):
                d = date.fromisoformat(d)

            dow = d.weekday()
            dom = d.day
            mon = d.month

            # cyclical
            out[i, 0] = math.sin(2 * math.pi * dow / 7)
            out[i, 1] = math.cos(2 * math.pi * dow / 7)
            out[i, 2] = math.sin(2 * math.pi * dom / 31)
            out[i, 3] = math.cos(2 * math.pi * dom / 31)
            out[i, 4] = math.sin(2 * math.pi * mon / 12)
            out[i, 5] = math.cos(2 * math.pi * mon / 12)

            # calendar flags
            out[i, 6] = 1.0 if dow >= 5 else 0.0
            out[i, 7] = 1.0 if dom <= 3 else 0.0

            # raw signals
            out[i, 8] = consumptions[i]
            out[i, 9] = kms[i]
            out[i, 10] = tons[i]
            out[i, 11] = trips[i]

            # lags (0 if not enough history)
            out[i, 12] = consumptions[i - 1] if i >= 1 else 0.0
            out[i, 13] = consumptions[i - 2] if i >= 2 else 0.0
            out[i, 14] = consumptions[i - 7] if i >= 7 else 0.0
            out[i, 15] = consumptions[i - 14] if i >= 14 else 0.0

            # rolling stats (3-day)
            w3 = consumptions[max(0, i - 2) : i + 1]
            out[i, 16] = w3.mean()
            out[i, 17] = w3.std() if len(w3) > 1 else 0.0

            # rolling stats (7-day)
            w7 = consumptions[max(0, i - 6) : i + 1]
            out[i, 18] = w7.mean()
            out[i, 19] = w7.std() if len(w7) > 1 else 0.0

            # rolling stats (14-day)
            w14 = consumptions[max(0, i - 13) : i + 1]
            out[i, 20] = w14.mean()
            out[i, 21] = w14.min()
            out[i, 22] = w14.max()

            # linear trend slope over last 14 days
            if i >= 3:
                seg = consumptions[max(0, i - 13) : i + 1]
                x = np.arange(len(seg), dtype=np.float32)
                slope = np.polyfit(x, seg, 1)[0] if len(seg) >= 2 else 0.0
                out[i, 23] = float(slope)

        return out


# ── BiLSTM with Multi-Head Self-Attention ─────────────────────────────────────


class BiLSTMAttention(_NNModule):
    """
    Bidirectional LSTM with multi-head self-attention.

    Architecture:
      Input  → Linear projection → 2-layer BiLSTM → Multi-head attn →
      LayerNorm → Dropout → Linear → output
    """

    def __init__(
        self,
        input_size: int = N_FEATURES,
        hidden_size: int = 128,
        num_layers: int = 2,
        n_heads: int = 8,
        dropout: float = 0.2,
        forecast_days: int = FORECAST_DAYS,
    ):
        if not TORCH_AVAILABLE:
            return
        super().__init__()

        self.hidden_size = hidden_size
        self.forecast_days = forecast_days
        self.dropout_p = dropout

        # Input projection
        self.input_proj = nn.Linear(input_size, hidden_size)

        # Bidirectional LSTM (output dim = 2 * hidden_size)
        self.bilstm = nn.LSTM(
            input_size=hidden_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            bidirectional=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )

        # Multi-head attention over LSTM outputs
        self.attention = nn.MultiheadAttention(
            embed_dim=hidden_size * 2,
            num_heads=n_heads,
            dropout=dropout,
            batch_first=True,
        )
        self.attn_norm = nn.LayerNorm(hidden_size * 2)
        self.dropout = nn.Dropout(dropout)

        # Residual projection (input → attn dim)
        self.res_proj = nn.Linear(hidden_size, hidden_size * 2)

        # Output head
        self.head = nn.Sequential(
            nn.Linear(hidden_size * 2, hidden_size),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size, forecast_days),
        )

    def forward(self, x: "torch.Tensor") -> "torch.Tensor":
        # x: (B, T, input_size)
        proj = F.gelu(self.input_proj(x))  # (B, T, H)
        lstm_out, _ = self.bilstm(proj)  # (B, T, 2H)

        # Self-attention with residual
        attn_out, _ = self.attention(lstm_out, lstm_out, lstm_out)
        attn_out = self.attn_norm(lstm_out + self.dropout(attn_out))

        # Global average pooling + last step
        pooled = attn_out.mean(dim=1)  # (B, 2H)
        return self.head(pooled)  # (B, forecast_days)

    def predict_mc(self, x: "torch.Tensor", n_samples: int = MC_SAMPLES) -> Tuple:
        """MC Dropout: n_samples stochastic forward passes → mean ± std."""
        self.train()  # enable dropout
        with torch.no_grad():
            preds = torch.stack([self(x) for _ in range(n_samples)], dim=0)
        self.eval()
        mean = preds.mean(dim=0)
        std = preds.std(dim=0)
        return mean, std


# ── Temporal Convolutional Network ────────────────────────────────────────────


class _CausalConvBlock(_NNModule):
    """Residual dilated causal conv block with weight normalization."""

    def __init__(self, n_channels: int, dilation: int, dropout: float):
        if not TORCH_AVAILABLE:
            return
        super().__init__()
        padding = dilation  # causal: pad only left
        self.conv1 = nn.utils.weight_norm(
            nn.Conv1d(n_channels, n_channels, 3, padding=padding * 2, dilation=dilation)
        )
        self.conv2 = nn.utils.weight_norm(
            nn.Conv1d(n_channels, n_channels, 3, padding=padding * 2, dilation=dilation)
        )
        self.relu = nn.GELU()
        self.dropout = nn.Dropout(dropout)
        self.causal_trim = padding * 2  # remove future leak on right side

    def forward(self, x: "torch.Tensor") -> "torch.Tensor":
        # x: (B, C, T)
        out = self.relu(self.conv1(x)[..., : -self.causal_trim or None])
        out = self.dropout(out)
        out = self.conv2(out)[..., : -self.causal_trim or None]
        out = self.dropout(out)
        return self.relu(x + out)  # residual


class TCN(_NNModule):
    """
    Temporal Convolutional Network with dilated causal convolutions.

    Dilations: 1, 2, 4, 8, 16, 32  → receptive field = 2*(1+2+4+8+16+32)*2 = 252 days
    """

    def __init__(
        self,
        input_size: int = N_FEATURES,
        n_channels: int = 64,
        n_layers: int = 6,
        dropout: float = 0.2,
        forecast_days: int = FORECAST_DAYS,
    ):
        if not TORCH_AVAILABLE:
            return
        super().__init__()
        self.input_proj = nn.Conv1d(input_size, n_channels, 1)
        self.blocks = nn.ModuleList(
            [
                _CausalConvBlock(n_channels, dilation=2**i, dropout=dropout)
                for i in range(n_layers)
            ]
        )
        self.head = nn.Sequential(
            nn.Linear(n_channels, n_channels),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(n_channels, forecast_days),
        )

    def forward(self, x: "torch.Tensor") -> "torch.Tensor":
        # x: (B, T, C) → transpose to (B, C, T)
        x = x.transpose(1, 2)
        x = self.input_proj(x)
        for block in self.blocks:
            x = block(x)
        x = x[..., -1]  # last time step (B, C)
        return self.head(x)  # (B, forecast_days)

    def predict_mc(self, x: "torch.Tensor", n_samples: int = MC_SAMPLES) -> Tuple:
        self.train()
        with torch.no_grad():
            preds = torch.stack([self(x) for _ in range(n_samples)], dim=0)
        self.eval()
        return preds.mean(dim=0), preds.std(dim=0)


# ── Walk-Forward Cross-Validation ─────────────────────────────────────────────


def walk_forward_cv(
    X: "torch.Tensor",
    y: "torch.Tensor",
    model_cls,
    model_kwargs: dict,
    n_splits: int = 5,
    epochs: int = 30,
) -> float:
    """Expanding-window CV → mean MAE across folds."""
    if not TORCH_AVAILABLE:
        return float("inf")

    n = len(X)
    min_train = max(10, n // (n_splits + 1))
    maes = []

    for fold in range(n_splits):
        split = min_train + fold * (n // (n_splits + 1))
        if split >= n - 1:
            break
        X_tr, y_tr = X[:split], y[:split]
        X_val, y_val = X[split : split + 1], y[split : split + 1]

        model = model_cls(**model_kwargs)
        opt = AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
        model.train()
        for _ in range(epochs):
            opt.zero_grad()
            loss = F.mse_loss(model(X_tr), y_tr)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()

        model.eval()
        with torch.no_grad():
            pred = model(X_val)
        mae = F.l1_loss(pred, y_val).item()
        maes.append(mae)

    return float(np.mean(maes)) if maes else float("inf")


# ── Training Helper ────────────────────────────────────────────────────────────


def train_model(
    model: "nn.Module",
    X: "torch.Tensor",
    y: "torch.Tensor",
    epochs: int = 150,
    lr: float = 1e-3,
    patience: int = 20,
) -> Dict:
    """Train with AdamW + cosine LR + early stopping. Returns training history."""
    if not TORCH_AVAILABLE:
        return {}

    opt = AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = CosineAnnealingLR(opt, T_max=epochs, eta_min=lr * 0.01)

    val_split = max(1, int(len(X) * 0.15))
    X_tr, y_tr = X[:-val_split], y[:-val_split]
    X_val, y_val = X[-val_split:], y[-val_split:]

    best_val = float("inf")
    best_state = None
    no_improve = 0
    history: Dict[str, list] = {"train_loss": [], "val_loss": []}

    dataset = TensorDataset(X_tr, y_tr)
    loader = DataLoader(dataset, batch_size=min(32, len(X_tr)), shuffle=True)

    model.train()
    for epoch in range(epochs):
        epoch_loss = 0.0
        for xb, yb in loader:
            opt.zero_grad()
            loss = F.huber_loss(model(xb), yb)  # robust to outliers
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            epoch_loss += loss.item()
        scheduler.step()

        model.eval()
        with torch.no_grad():
            val_loss = F.l1_loss(model(X_val), y_val).item()
        model.train()

        history["train_loss"].append(round(epoch_loss / len(loader), 4))
        history["val_loss"].append(round(val_loss, 4))

        if val_loss < best_val - 1e-4:
            best_val = val_loss
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            no_improve = 0
        else:
            no_improve += 1
            if no_improve >= patience:
                logger.info(
                    "Early stopping at epoch %d (best val MAE=%.4f)", epoch, best_val
                )
                break

    if best_state:
        model.load_state_dict(best_state)
    model.eval()
    return {"best_val_mae": round(best_val, 4), "epochs_trained": epoch + 1, **history}


# ── Statistical Fallback Stack ─────────────────────────────────────────────────


def _holt_winters(data: List[float], steps: int) -> Optional[Dict]:
    """Holt-Winters ETS with automatic trend/seasonal detection."""
    if len(data) < 14:
        return None
    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing

        trend = "add"
        seasonal = "add" if len(data) >= 21 else None
        sp = 7 if seasonal else None
        model = ExponentialSmoothing(
            data,
            trend=trend,
            seasonal=seasonal,
            seasonal_periods=sp,
            initialization_method="estimated",
        ).fit(optimized=True)
        fc = model.forecast(steps).tolist()
        ci_width = np.std(model.resid) * 1.96
        return {
            "forecast": fc,
            "lower": [v - ci_width for v in fc],
            "upper": [v + ci_width for v in fc],
            "method": "holt_winters",
        }
    except Exception as e:
        logger.debug("Holt-Winters failed: %s", e)
        return None


def _sarima(data: List[float], steps: int) -> Optional[Dict]:
    """SARIMA(1,1,1)(1,1,1,7) with automatic fallback to ARIMA(1,1,1)."""
    if len(data) < 30:
        return None
    try:
        from statsmodels.tsa.statespace.sarimax import SARIMAX

        order = (1, 1, 1)
        seasonal = (1, 1, 1, 7) if len(data) >= 21 else (0, 0, 0, 0)
        model = SARIMAX(
            data,
            order=order,
            seasonal_order=seasonal,
            enforce_stationarity=False,
            enforce_invertibility=False,
        )
        res = model.fit(disp=False, maxiter=100)
        fc = res.forecast(steps)
        ci = res.get_forecast(steps).conf_int(alpha=0.05)
        return {
            "forecast": fc.tolist(),
            "lower": ci.iloc[:, 0].tolist(),
            "upper": ci.iloc[:, 1].tolist(),
            "method": "sarima",
        }
    except Exception as e:
        logger.debug("SARIMA failed: %s", e)
        return None


def _ema_fallback(data: List[float], steps: int, alpha: float = 0.3) -> Dict:
    """Exponential moving average — always available."""
    ema = data[0]
    for v in data[1:]:
        ema = alpha * v + (1 - alpha) * ema
    std = float(np.std(data[-min(14, len(data)) :]))
    fc = [round(ema, 2)] * steps
    return {
        "forecast": fc,
        "lower": [round(ema - 1.96 * std, 2)] * steps,
        "upper": [round(ema + 1.96 * std, 2)] * steps,
        "method": "ema",
    }


def _ensemble_stat(data: List[float], steps: int) -> Dict:
    """
    Weighted ensemble of HW + SARIMA.
    Falls back gracefully at each level.
    """
    results = []
    weights = []

    hw = _holt_winters(data, steps)
    if hw:
        results.append(np.array(hw["forecast"]))
        weights.append(0.5)

    sar = _sarima(data, steps)
    if sar:
        results.append(np.array(sar["forecast"]))
        weights.append(0.5)

    if not results:
        return _ema_fallback(data, steps)

    weights = np.array(weights) / sum(weights)
    blended = sum(w * r for w, r in zip(weights, results))

    std = float(np.std(data[-min(14, len(data)) :]))
    parts = ([hw] if hw else []) + ([sar] if sar else [])
    method = "+".join(r["method"] for r in parts)
    return {
        "forecast": [round(float(v), 2) for v in blended],
        "lower": [round(float(v) - 1.96 * std, 2) for v in blended],
        "upper": [round(float(v) + 1.96 * std, 2) for v in blended],
        "method": method,
    }


def _detect_trend(history: List[float], forecast: List[float]) -> str:
    if not history or not forecast:
        return "stable"
    last_avg = np.mean(history[-5:])
    fc_avg = np.mean(forecast)
    delta = (fc_avg - last_avg) / (last_avg + 1e-6)
    if delta > 0.05:
        return "increasing"
    if delta < -0.05:
        return "decreasing"
    return "stable"


# ── Main Engine ────────────────────────────────────────────────────────────────


@dataclass
class ForecastResult:
    success: bool
    forecast: List[float] = field(default_factory=list)
    lower_95: List[float] = field(default_factory=list)
    upper_95: List[float] = field(default_factory=list)
    trend: str = "stable"
    method: str = "none"
    mae: Optional[float] = None
    is_trained: bool = False
    training_epochs: int = 0
    last_loss: Optional[float] = None
    input_days: int = 0
    forecast_days: int = FORECAST_DAYS
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class AdvancedTSEngine:
    """
    Unified time-series engine: auto-selects best model, trains, forecasts.

    Thread-safe; uses a lock during training so background rebuild
    doesn't interfere with concurrent inference.
    """

    MIN_DEEP = 90  # minimum days to use deep learning
    MIN_STAT = 30  # minimum days to use SARIMA
    MIN_HW = 14  # minimum days for Holt-Winters
    MIN_EMA = 3  # always available

    def __init__(self):
        self._lock = threading.Lock()
        self.engine = FeatureEngine()
        self.bilstm: Optional["BiLSTMAttention"] = None
        self.tcn: Optional["TCN"] = None
        self._bilstm_mae: float = float("inf")
        self._tcn_mae: float = float("inf")
        self._trained: bool = False
        self._training_epochs: int = 0
        self._last_loss: Optional[float] = None
        self._n_training_samples: int = 0
        self._train_time: float = 0.0
        self._X: Optional["torch.Tensor"] = None
        self._y: Optional["torch.Tensor"] = None

    # ── Public API ─────────────────────────────────────────────────────────────

    def train(self, records: List[Dict]) -> Dict:
        """
        Full training pipeline.

        Args:
            records: list of daily dicts (date, consumption, km, ton, trips)

        Returns:
            training metadata dict
        """
        with self._lock:
            return self._train(records)

    def forecast(
        self, records: List[Dict], steps: int = FORECAST_DAYS
    ) -> ForecastResult:
        """Run inference on the latest `records`."""
        return self._forecast(records, steps)

    def status(self) -> Dict:
        return {
            "is_trained": self._trained,
            "training_epochs": self._training_epochs,
            "last_loss": self._last_loss,
            "n_training_samples": self._n_training_samples,
            "train_time_s": round(self._train_time, 1),
            "bilstm_mae": None
            if self._bilstm_mae == float("inf")
            else round(self._bilstm_mae, 4),
            "tcn_mae": None
            if self._tcn_mae == float("inf")
            else round(self._tcn_mae, 4),
            "torch_available": TORCH_AVAILABLE,
            "deep_learning_active": TORCH_AVAILABLE and self._trained,
            "min_days_for_deep": self.MIN_DEEP,
        }

    # ── Training ───────────────────────────────────────────────────────────────

    def _train(self, records: List[Dict]) -> Dict:
        n = len(records)
        min_days = SEQ_LEN + FORECAST_DAYS + 5
        if n < min_days:
            return {
                "success": False,
                "error": f"Yetersiz veri ({n} gün, min {min_days} gerekli)",
            }

        t0 = time.time()
        consumptions = [r.get("consumption", 0.0) for r in records]

        if not TORCH_AVAILABLE or n < self.MIN_DEEP:
            self._trained = False
            return {
                "success": True,
                "method": "statistical_only",
                "note": (
                    "PyTorch unavailable"
                    if not TORCH_AVAILABLE
                    else f"skipped (< {self.MIN_DEEP} days)"
                ),
                "n_records": n,
            }

        # Build supervised dataset
        X_feat = self.engine.fit_transform(records)
        X_seqs, y_seqs = self._make_sequences(X_feat, consumptions)
        if len(X_seqs) < 10:
            return {"success": False, "error": "Sequence oluşturulamadı"}

        X_t = torch.tensor(X_seqs, dtype=torch.float32)
        y_t = torch.tensor(y_seqs, dtype=torch.float32)
        c_mean = float(np.mean(consumptions))
        c_std = float(np.std(consumptions)) + 1e-8
        y_t = (y_t - c_mean) / c_std

        self._X, self._y = X_t, y_t

        # Train BiLSTM
        logger.info("Training BiLSTM-Attention on %d sequences...", len(X_t))
        self.bilstm = BiLSTMAttention(
            input_size=N_FEATURES, forecast_days=FORECAST_DAYS
        )
        bilstm_hist = train_model(self.bilstm, X_t, y_t, epochs=200, patience=25)
        self._bilstm_mae = bilstm_hist.get("best_val_mae", float("inf"))

        # Train TCN
        logger.info("Training TCN on %d sequences...", len(X_t))
        self.tcn = TCN(input_size=N_FEATURES, forecast_days=FORECAST_DAYS)
        tcn_hist = train_model(self.tcn, X_t, y_t, epochs=200, patience=25)
        self._tcn_mae = tcn_hist.get("best_val_mae", float("inf"))

        self._trained = True
        self._n_training_samples = len(X_t)
        self._training_epochs = max(
            bilstm_hist.get("epochs_trained", 0), tcn_hist.get("epochs_trained", 0)
        )
        self._last_loss = min(self._bilstm_mae, self._tcn_mae)
        self._train_time = time.time() - t0

        logger.info(
            "Training done in %.1fs — BiLSTM MAE=%.4f, TCN MAE=%.4f",
            self._train_time,
            self._bilstm_mae,
            self._tcn_mae,
        )

        return {
            "success": True,
            "n_sequences": len(X_t),
            "bilstm_val_mae": self._bilstm_mae,
            "tcn_val_mae": self._tcn_mae,
            "best_model": "bilstm" if self._bilstm_mae <= self._tcn_mae else "tcn",
            "epochs_trained": self._training_epochs,
            "train_time_s": round(self._train_time, 1),
        }

    def _make_sequences(
        self, X: np.ndarray, targets: List[float]
    ) -> Tuple[np.ndarray, np.ndarray]:
        X_out, y_out = [], []
        tgt = np.array(targets, dtype=np.float32)
        for i in range(SEQ_LEN, len(X) - FORECAST_DAYS + 1):
            X_out.append(X[i - SEQ_LEN : i])
            y_out.append(tgt[i : i + FORECAST_DAYS])
        return np.array(X_out, dtype=np.float32), np.array(y_out, dtype=np.float32)

    # ── Forecasting ────────────────────────────────────────────────────────────

    def _forecast(self, records: List[Dict], steps: int) -> ForecastResult:
        n = len(records)
        consumptions = [r.get("consumption", 0.0) for r in records]

        # Deep learning path
        if TORCH_AVAILABLE and self._trained and n >= SEQ_LEN:
            try:
                return self._deep_forecast(records, consumptions, steps)
            except Exception as e:
                logger.warning("Deep forecast failed, falling back to stats: %s", e)

        # Statistical path
        return self._stat_forecast(consumptions, steps, n)

    def _deep_forecast(
        self, records: List[Dict], consumptions: List[float], steps: int
    ) -> ForecastResult:
        n_records = len(records)
        X_feat = self.engine.transform(records[-SEQ_LEN:])
        X_t = torch.tensor(X_feat[np.newaxis], dtype=torch.float32)

        c_mean = float(np.mean(consumptions))
        c_std = float(np.std(consumptions)) + 1e-8

        bilstm_pred = bilstm_std = tcn_pred = tcn_std = None

        if self.bilstm is not None:
            m, s = self.bilstm.predict_mc(X_t, MC_SAMPLES)
            bilstm_pred = m[0].numpy() * c_std + c_mean
            bilstm_std = s[0].numpy() * c_std

        if self.tcn is not None:
            m, s = self.tcn.predict_mc(X_t, MC_SAMPLES)
            tcn_pred = m[0].numpy() * c_std + c_mean
            tcn_std = s[0].numpy() * c_std

        # Weighted blend (inverse MAE weighting)
        if bilstm_pred is not None and tcn_pred is not None:
            w_b = 1.0 / (self._bilstm_mae + 1e-8)
            w_t = 1.0 / (self._tcn_mae + 1e-8)
            wsum = w_b + w_t
            blended = (w_b * bilstm_pred + w_t * tcn_pred) / wsum
            blended_std = (w_b * bilstm_std + w_t * tcn_std) / wsum
            method = "bilstm+tcn"
        elif bilstm_pred is not None:
            blended, blended_std = bilstm_pred, bilstm_std
            method = "bilstm"
        else:
            blended, blended_std = tcn_pred, tcn_std
            method = "tcn"

        # Trim to requested steps
        fc = [round(float(v), 2) for v in blended[:steps]]
        lower = [
            round(float(v - 1.96 * s), 2)
            for v, s in zip(blended[:steps], blended_std[:steps])
        ]
        upper = [
            round(float(v + 1.96 * s), 2)
            for v, s in zip(blended[:steps], blended_std[:steps])
        ]

        return ForecastResult(
            success=True,
            forecast=fc,
            lower_95=lower,
            upper_95=upper,
            trend=_detect_trend(consumptions, fc),
            method=method,
            mae=round(min(self._bilstm_mae, self._tcn_mae) * c_std, 3),
            is_trained=True,
            training_epochs=self._training_epochs,
            last_loss=self._last_loss,
            input_days=n_records,
            forecast_days=steps,
        )

    def _stat_forecast(
        self, consumptions: List[float], steps: int, n: int
    ) -> ForecastResult:
        if n < self.MIN_EMA:
            return ForecastResult(
                success=False,
                error_code="INSUFFICIENT_DATA",
                error_message=f"En az {self.MIN_EMA} günlük veri gerekli (mevcut: {n})",
            )

        result = _ensemble_stat(consumptions, steps)
        fc = result["forecast"]

        return ForecastResult(
            success=True,
            forecast=fc,
            lower_95=result.get("lower", fc),
            upper_95=result.get("upper", fc),
            trend=_detect_trend(consumptions, fc),
            method=result["method"],
            is_trained=False,
            input_days=n,
            forecast_days=steps,
        )


# ── Singleton ─────────────────────────────────────────────────────────────────

_engine: Optional[AdvancedTSEngine] = None
_engine_lock = threading.Lock()


def get_advanced_ts_engine() -> AdvancedTSEngine:
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = AdvancedTSEngine()
    return _engine
