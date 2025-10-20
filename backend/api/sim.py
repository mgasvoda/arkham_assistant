"""Simulation API endpoints."""

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class SimulationConfig(BaseModel):
    """Simulation configuration."""

    mulligan_strategy: str = "aggressive"
    target_cards: Optional[list[str]] = None
    turns_to_simulate: int = 5


class SimulationRequest(BaseModel):
    """Request model for simulation."""

    deck_id: str
    n_trials: int = 1000
    config: Optional[SimulationConfig] = None


@router.post("/run")
async def run_simulation(request: SimulationRequest):
    """Run deck simulation."""
    # TODO: Implement simulation execution
    return {
        "deck_id": request.deck_id,
        "n_trials": request.n_trials,
        "metrics": {
            "avg_setup_time": 0.0,
            "avg_draws_to_key_card": 0.0,
            "success_rate": 0.0,
            "mulligan_rate": 0.0,
        },
        "message": "Simulation not yet implemented",
    }

