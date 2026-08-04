import hashlib
import hmac
import json
import time

import httpx
from celery import Celery, Task

from .config import settings

celery_app = Celery("empowered_ai", broker=settings().redis_url, backend=settings().redis_url)
celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    # A single evaluation makes several sequential external HTTP + LLM calls
    # (GitHub, LeetCode, multiple OpenAI completions). Without a hard limit,
    # one hung call blocks the worker process indefinitely -- a real risk on
    # a small cloud instance with few worker processes.
    task_time_limit=180,
    task_soft_time_limit=150,
    # Default prefetch (4) lets a worker grab more tasks than it can run
    # concurrently, delaying other candidates' evaluations behind a slow one.
    worker_prefetch_multiplier=1,
)


def _post_to_portal(result: dict) -> None:
    callback_url = settings().portal_callback_url
    if not callback_url:
        return
    body = json.dumps({**result, "source": "ai-service"}, separators=(",", ":"))
    timestamp = str(int(time.time()))
    signature = hmac.new(settings().portal_callback_secret.encode(), f"{timestamp}.{body}".encode(), hashlib.sha256).hexdigest()
    httpx.post(
        callback_url,
        content=body,
        headers={
            "content-type": "application/json",
            "x-webhook-timestamp": timestamp,
            "x-webhook-signature": signature,
            "x-webhook-secret": settings().portal_callback_secret,
        },
        timeout=settings().request_timeout_seconds,
    ).raise_for_status()


class NotifyPortalOnFailureTask(Task):
    """Without this, a task that exhausts all 5 retries just dies —
    fire-and-forget in both directions means the Portal never learns the
    evaluation failed at all, and the candidate's deep-dive silently shows
    nothing forever with no visible signal to an admin. Sends a minimal,
    honest 'unavailable' dossier instead, so at minimum the candidate
    reads as "evaluation failed" rather than "evaluation never ran"."""

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        payload = args[0] if args else {}
        candidate_id = payload.get("candidateId")
        if not candidate_id:
            return
        result = {
            "run_id": payload.get("runId") or task_id,
            "candidate_id": candidate_id,
            "overall_score": 0,
            "confidence_score": 0,
            "hiring_recommendation": "Needs Review",
            "final_summary": f"AI evaluation failed after all retries and could not complete: {exc}",
            "source_reports": {},
        }
        try:
            _post_to_portal(result)
        except Exception:
            # Best-effort — if even the failure notification can't reach
            # the Portal, there's nothing further to do from here; this
            # must never raise out of Celery's own failure handling.
            pass


@celery_app.task(
    bind=True,
    base=NotifyPortalOnFailureTask,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    max_retries=5,
)
def evaluate_candidate_task(self, payload: dict):
    import asyncio

    from .evaluation import evaluate_candidate
    from .schemas import CandidateEvaluationRequest

    result = asyncio.run(evaluate_candidate(CandidateEvaluationRequest.model_validate(payload)))
    _post_to_portal(result)
    return result
