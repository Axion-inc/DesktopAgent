from __future__ import annotations
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from .utils import get_logger
from .metrics import compute_metrics
from .models import init_db

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path("./data")
DATA_DIR.mkdir(exist_ok=True, parents=True)

app = FastAPI(title="Desktop Agent API", description="Minimal API for CLI operations")


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    get_logger().info("app.startup")


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/metrics")
def metrics():
    return compute_metrics()
