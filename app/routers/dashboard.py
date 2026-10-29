"""Dashboard and analytics endpoints."""
from fastapi import APIRouter, Depends

from dependencies import current_user
from services.analytics import build_analytics, build_dashboard

router = APIRouter()


@router.get("/api/dashboard")
def dashboard(user=Depends(current_user)):
    return build_dashboard(user)


@router.get("/api/analytics")
def analytics(user=Depends(current_user)):
    return build_analytics(user)
