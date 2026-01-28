"""Simulation API endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.models.simulation_models import MulliganStrategy

router = APIRouter()


class SimulationConfig(BaseModel):
    """Simulation configuration."""

    mulligan_strategy: MulliganStrategy = Field(
        default=MulliganStrategy.AGGRESSIVE,
        description="Strategy for evaluating mulligan decisions",
    )
    key_cards: list[str] | None = Field(
        default=None,
        description="User-specified key cards to track (card IDs)",
    )
    auto_detect_key_cards: bool = Field(
        default=True,
        description="Whether to auto-detect key cards based on card properties",
    )
    seed: int | None = Field(
        default=None,
        description="Random seed for reproducibility",
    )


class SimulationRequest(BaseModel):
    """Request model for simulation."""

    deck_id: str | None = Field(
        default=None,
        description="ID of deck to simulate (fetches from ChromaDB)",
    )
    card_list: list[str] | None = Field(
        default=None,
        description="Direct card list (alternative to deck_id)",
    )
    n_trials: int = Field(
        default=1000,
        ge=1,
        le=10000,
        description="Number of simulation trials to run",
    )
    config: SimulationConfig | None = Field(
        default=None,
        description="Simulation configuration",
    )


@router.post("/run")
async def run_simulation_endpoint(request: SimulationRequest):
    """Run Monte Carlo deck simulation.

    Executes multiple random trials to analyze opening hand consistency,
    mulligan effectiveness, and key card reliability.

    Returns simulation metrics including average setup time, success rate,
    mulligan rate, and per-card statistics for key cards.
    """
    from backend.services.simulator import run_simulation

    if not request.deck_id and not request.card_list:
        raise HTTPException(
            status_code=400,
            detail="Either deck_id or card_list must be provided",
        )

    try:
        config_dict = request.config.model_dump() if request.config else None
        return run_simulation(
            deck_id=request.deck_id,
            card_list=request.card_list,
            n_trials=request.n_trials,
            config=config_dict,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Simulation error: {str(e)}")
