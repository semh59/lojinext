import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException

_INTERNAL_SECRET = os.environ.get("INTERNAL_API_SECRET", "")

_bg_tasks: set[asyncio.Task] = set()


def check_internal_auth(x_internal_token: str | None = Header(default=None)) -> None:
    """Validate X-Internal-Token when INTERNAL_API_SECRET is configured.

    Mirrors admin_platform/api/internal_routes.py's existing check --
    same secret, same header name, so no new auth mechanism is introduced.
    """
    if not _INTERNAL_SECRET:
        return  # Auth disabled (dev / unset)
    if x_internal_token != _INTERNAL_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from prediction_ml_service.application.model_training_handler import (
        get_model_training_handler,
    )
    from prediction_ml_service.application.model_warmup import (
        schedule_predictor_warmup,
    )
    from prediction_ml_service.application.physics_handler import (
        get_physics_handler,
    )

    get_model_training_handler().setup()
    get_physics_handler().register()

    task = schedule_predictor_warmup()
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)

    yield

    for t in list(_bg_tasks):
        if not t.done():
            t.cancel()


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


# Routers import `check_internal_auth` from this module -- must come
# after it (and `app`) are defined above.
from prediction_ml_service.routers import (  # noqa: E402
    predict_routes,
    status_routes,
    train_routes,
)

app.include_router(predict_routes.router)
app.include_router(train_routes.router)
app.include_router(status_routes.router)
