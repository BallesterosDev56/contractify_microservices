import logging

from fastapi import FastAPI

from .routers.contracts import router as contracts_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("contracts-service")

app = FastAPI(title="Contractify Contracts Service", version="1.0.0")
app.include_router(contracts_router)
