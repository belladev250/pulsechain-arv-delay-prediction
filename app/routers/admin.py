"""Administrator-only demo tools."""
from fastapi import APIRouter, Depends

from dependencies import admin_only
from services.demo_data import seed_demo_data, simulate_tick

router = APIRouter()


@router.post("/api/seed")
def seed(user=Depends(admin_only)):
    return seed_demo_data()


@router.post("/api/simulate/tick")
def simulate(user=Depends(admin_only)):
    return simulate_tick()
