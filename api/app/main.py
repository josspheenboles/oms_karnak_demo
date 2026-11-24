from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import health
from .db import init_db
from .documents import router as documents_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="OMS API", lifespan=lifespan)
app.include_router(documents_router)


@app.get("/health")
async def get_health():
    checks = await health.run_checks()
    status = "ok" if all(checks.values()) else "degraded"
    return {"status": status, **checks}
