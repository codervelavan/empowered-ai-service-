import { Router } from 'express';
import { z } from 'zod';
import { requireServiceToken } from '../middleware/auth.js';
import { asyncHandler } from '../utils/asyncHandler.js';
import { runCandidateEvaluation } from '../services/candidateEvaluation.service.js';
import { evaluateExam } from '../services/examEvaluation.service.js';
import { isConfigured } from '../services/openai.client.js';

export const evaluateRouter = Router();
evaluateRouter.use(requireServiceToken);

const candidateSchema = z.object({
  candidateId: z.string().min(1),
  candidateName: z.string().min(1),
  email: z.string().email(),
  domain: z.string().nullable().optional(),
  college: z.string().nullable().optional(),
  cgpa: z.number().nullable().optional(),
  github: z.string().nullable().optional(),
  linkedin: z.string().nullable().optional(),
  leetcode: z.string().nullable().optional(),
  resumeText: z.string().nullable().optional(),
});

/**
 * Async by design (see candidateEvaluation.service.ts) — the multi-source
 * evaluation takes real time; the Portal's registration flow must not
 * block on it. Responds 202 immediately and pushes the result to the
 * Portal's existing webhook once done.
 */
evaluateRouter.post('/candidate', (req, res) => {
  const body = candidateSchema.parse(req.body);
  if (!isConfigured()) {
    res.status(503).json({ error: { code: 'not_configured', message: 'OPENAI_API_KEY is not set' } });
    return;
  }
  void runCandidateEvaluation({
    candidateId: body.candidateId,
    candidateName: body.candidateName,
    email: body.email,
    domain: body.domain ?? null,
    college: body.college ?? null,
    cgpa: body.cgpa ?? null,
    github: body.github ?? null,
    linkedin: body.linkedin ?? null,
    leetcode: body.leetcode ?? null,
    resumeText: body.resumeText ?? null,
  });
  res.status(202).json({ accepted: true });
});

const examSchema = z.object({
  candidateName: z.string().min(1),
  score: z.number().min(0).max(100),
});

/**
 * Synchronous by design — one model call, Frappe waits for the response
 * directly (same shape as its previous direct-Gemini call).
 */
evaluateRouter.post(
  '/exam',
  asyncHandler(async (req, res) => {
    const body = examSchema.parse(req.body);
    if (!isConfigured()) {
      res.status(503).json({ error: { code: 'not_configured', message: 'OPENAI_API_KEY is not set' } });
      return;
    }
    const result = await evaluateExam(body);
    res.json(result);
  }),
);
