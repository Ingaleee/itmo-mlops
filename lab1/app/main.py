import os
from contextlib import asynccontextmanager
from pathlib import Path

import joblib
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from typing import Annotated

MODEL_PATH = Path(os.getenv("MODEL_PATH", "model.joblib"))
MODEL_VERSION = os.getenv("MODEL_VERSION", "iris-v1")
model = None
FLOAT32_MAX = float(np.finfo(np.float32).max)


class PredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    features: list[Annotated[float, Field(strict=True, allow_inf_nan=False, ge=-FLOAT32_MAX, le=FLOAT32_MAX)]] = Field(min_length=4, max_length=4)


@asynccontextmanager
async def lifespan(_: FastAPI):
    global model
    model = joblib.load(MODEL_PATH)
    try:
        yield
    finally:
        model = None


app = FastAPI(title="Iris classifier", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def invalid_request(_, error: RequestValidationError):
    # Never echo input: non-standard JSON NaN/Infinity cannot be serialized in a response.
    details = [{key: issue[key] for key in ("type", "loc", "msg")} for issue in error.errors()]
    return JSONResponse(status_code=422, content={"detail": details})


@app.get("/live")
def live() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/health")
def health() -> dict[str, str]:
    if model is None:
        raise HTTPException(status_code=503, detail="model is not loaded")
    return {"status": "ready", "model_version": MODEL_VERSION}


@app.post("/predict")
def predict(request: PredictionRequest) -> dict[str, str | int]:
    if model is None:
        raise HTTPException(status_code=503, detail="model is not loaded")
    prediction = int(model.predict([request.features])[0])
    return {"class_id": prediction, "model_version": MODEL_VERSION}
