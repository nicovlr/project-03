"""GovSense — FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.storage.database import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database tables ...")
    init_db()
    logger.info("GovSense API is ready.")
    yield
    logger.info("Shutting down GovSense API.")


app = FastAPI(
    title="GovSense",
    description=(
        "Intelligence operationnelle sur les donnees publiques gouvernementales. "
        "Transforme les open data de data.gouv.fr en dashboards decisionnels."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/", tags=["Root"])
def root():
    return {
        "name": "GovSense",
        "version": "1.0.0",
        "docs": "/docs",
        "description": "Open data intelligence for public decision-making",
    }
