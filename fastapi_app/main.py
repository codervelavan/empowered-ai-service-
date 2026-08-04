from fastapi import Depends, FastAPI, HTTPException, Response, status
from redis import Redis

from .config import settings
from .evaluation import evaluate_exam
from .resume_parse import ResumeParseRequest
from .resume_parse_service import parse_resume_text
from .schemas import CandidateEvaluationRequest, ExamEvaluationRequest
from .security import require_frappe_token, require_portal_token
from .tasks import evaluate_candidate_task

app = FastAPI(title="EmpowerED AI Service", version="2.0.0")


@app.get("/health")
def health(response: Response):
    redis_ok = False
    try:
        redis_ok = bool(Redis.from_url(settings().redis_url, socket_connect_timeout=1).ping())
    except Exception:
        redis_ok = False
    ok = redis_ok and settings().openai_configured
    # A cloud load balancer's health check keys off the HTTP status code, not
    # the JSON body -- without this, a broken Redis/OpenAI dependency still
    # reports "healthy" to the LB and traffic keeps routing here.
    response.status_code = status.HTTP_200_OK if ok else status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ok" if ok else "degraded",
        "process": True,
        "redis": redis_ok,
        "queueConfigured": bool(settings().redis_url),
        "openaiConfigured": settings().openai_configured,
        "provider": settings().ai_provider,
    }


@app.post("/parse/resume", dependencies=[Depends(require_portal_token)])
def parse_resume(request: ResumeParseRequest):
    if not settings().openai_configured:
        raise HTTPException(status_code=503, detail={"code": "not_configured", "message": "OpenAI is not configured"})
    return parse_resume_text(request.resumeText)


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
