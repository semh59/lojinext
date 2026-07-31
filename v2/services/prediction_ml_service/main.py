import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException

_INTERNAL_SECRET = os.environ.get("INTERNAL_API_SECRET", "")


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
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
