from fastapi import APIRouter, Depends, HTTPException

from app.core.security import require_api_key
from app.eval.metrics import EvalDependencyError, resolve_eval_dataset, run_eval, summarize_eval_dataset
from app.schemas.eval import EvalDatasetSummary, EvalResponse, EvalRunRequest

router = APIRouter()


@router.get("/dataset", response_model=EvalDatasetSummary)
async def dataset_summary(name: str = "default", sample_size: int = 12) -> EvalDatasetSummary:
    try:
        return summarize_eval_dataset(name=name, sample_size=max(1, min(sample_size, 50)))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/run", response_model=EvalResponse, dependencies=[Depends(require_api_key)])
async def evaluate(request: EvalRunRequest | None = None) -> EvalResponse:
    request = request or EvalRunRequest()
    try:
        return await run_eval(
            dataset_path=resolve_eval_dataset(request.dataset_name),
            configs=request.configs if request.configs else None,
            include_agent_eval=request.include_agent_eval,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except EvalDependencyError as exc:
        raise HTTPException(status_code=503, detail=f"eval dependency unavailable: {exc}") from exc
