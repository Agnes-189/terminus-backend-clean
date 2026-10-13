from fastapi import APIRouter
from app.api.v1.endpoints import medical
from app.api.v1.endpoints import death_certificate
api_router = APIRouter()
api_router.include_router(medical.router)
api_router.include_router(death_certificate.router)