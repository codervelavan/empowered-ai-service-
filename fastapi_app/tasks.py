import hashlib
import hmac
import json
import time

import httpx
from celery import Celery

from .config import settings

celery_app = Celery("empowered_ai", broker=settings().redis_url, backend=settings().redis_url)
celery_app.conf.update(task_acks_late=True, task_reject_on_worker_lost=True, task_track_started=True, broker_connection_retry_on_startup=True)


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_backoff_max=600, max_retries=5)
def evaluate_candidate_task(self, payload: dict):
    import asyncio

    from .evaluation import evaluate_candidate
    from .schemas import CandidateEvaluationRequest

    result = asyncio.run(evaluate_candidate(CandidateEvaluationRequest.model_validate(payload)))
    callback_url = settings().portal_callback_url
    if not callback_url:
        return result
    body = json.dumps({**result, "source": "ai-service"}, separators=(",", ":"))
    timestamp = str(int(time.time()))
    signature = hmac.new(settings().portal_callback_secret.encode(), f"{timestamp}.{body}".encode(), hashlib.sha256).hexdigest()
    response = httpx.post(
        callback_url,
        content=body,
        headers={
            "content-type": "application/json",
            "x-webhook-timestamp": timestamp,
            "x-webhook-signature": signature,
            "x-webhook-secret": settings().portal_callback_secret,
        },
        timeout=settings().request_timeout_seconds,
    )
    response.raise_for_status()
    return result
