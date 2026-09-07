"""FactMesh FastAPI application entrypoint."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import documents, facts, relationships, issues

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown lifecycle."""
    logger.info("FactMesh API starting up...")
    yield
    logger.info("FactMesh API shutting down...")


app = FastAPI(
    title="FactMesh",
    description=(
        "A Fact Knowledge Layer that extracts atomic facts from PDFs, "
        "grounds them in source evidence, and identifies cross-document "
        "relationships (corroboration, contradiction, contextual differences)."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow the Next.js frontend (default dev port 3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(documents.router)
app.include_router(facts.router)
app.include_router(relationships.router)
app.include_router(issues.router)


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "factmesh"}
