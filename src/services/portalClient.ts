import { env } from '../config/env.js';

/**
 * Pushes the final consolidated hiring evaluation to the Portal's existing,
 * already-tested POST /api/webhooks/ai-evaluation endpoint — the exact
 * same contract n8n's "Push Evaluation to Portal" node used, just from a
 * new caller. Nothing on the Portal side changes: `ingestAiEvaluation()`
 * doesn't know or care who called it.
 *
 * Never throws: a Portal outage must not crash the evaluation job. The
 * caller (candidateEvaluation.service.ts) logs the outcome; there is no
 * retry queue here yet — see README's known-gaps section.
 */
export async function pushAiEvaluation(payload: Record<string, unknown>): Promise<{ ok: boolean; status?: number; error?: string }> {
  try {
    const res = await fetch(`${env.portal.baseUrl}/api/webhooks/ai-evaluation`, {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'x-webhook-secret': env.portal.webhookSecret,
      },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(15_000),
    });
    return { ok: res.ok, status: res.status };
  } catch (err) {
    return { ok: false, error: (err as Error).message };
  }
}
