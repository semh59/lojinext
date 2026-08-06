# Service: prediction_ml_service

Standalone FastAPI service hosting the fuel-consumption ML pipeline
(5-model ensemble, physics fallback, Kalman, ARIMA) previously in-process
inside `v2/modules/prediction_ml`. Reached by the main backend over HTTP
via `v2/modules/prediction_ml/public.py`'s thin client (feature-flagged:
`PREDICTION_ML_REMOTE`, see root CLAUDE.md).

Not publicly routed (no Traefik rule, no host port) -- internal Docker
network only, same pattern as `ocr_service`/`telegram_bot`.

Auth: `X-Internal-Token` header, matching `INTERNAL_API_SECRET` -- same
secret and mechanism the telegram bot services already use.

Owns its own Celery worker + beat schedule for training tasks (moved
from the main backend's `celery_app.py` in Task 8).
