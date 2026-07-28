from fastapi import Depends, FastAPI, HTTPException, status
from redis import Redis

from .config import settings
from .evaluation import evaluate_exam
from .schemas import CandidateEvaluationRequest, ExamEvaluationRequest
from .security import require_frappe_token, require_portal_token
from .tasks import evaluate_candidate_task

app = FastAPI(title="EmpowerED AI Service", version="2.0.0")


@app.get("/health")
def health():
    redis_ok = False
    try:
        redis_ok = bool(Redis.from_url(settings().redis_url, socket_connect_timeout=1).ping())
    except Exception:
        redis_ok = False
    return {
        "status": "ok" if redis_ok and settings().openai_configured else "degraded",
        "process": True,
        "redis": redis_ok,
        "queueConfigured": bool(settings().redis_url),
        "openaiConfigured": settings().openai_configured,
        "provider": settings().ai_provider,
    }


@app.post("/evaluate/candidate", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_portal_token)])
def queue_candidate(request: CandidateEvaluationRequest):
    if not settings().openai_configured:
        raise HTTPException(status_code=503, detail={"code": "not_configured", "message": "OpenAI is not configured"})
    run_id = request.runId or request.candidateId
    task = evaluate_candidate_task.apply_async(args=[request.model_dump()], task_id=f"candidate-evaluation-{run_id}")
    return {"accepted": True, "jobId": task.id, "status": "queued"}


@app.post("/evaluate/exam", dependencies=[Depends(require_frappe_token)])
def exam(request: ExamEvaluationRequest):
    if not settings().openai_configured:
        raise HTTPException(status_code=503, detail={"code": "not_configured", "message": "OpenAI is not configured"})
    return evaluate_exam(request)
