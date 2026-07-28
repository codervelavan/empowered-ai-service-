import { env } from '../config/env.js';
import { structuredCompletion } from './openai.client.js';

export interface ExamEvaluation {
  verdict: string;
  recommendation: string;
  strengths: string[];
  concerns: string[];
}

const SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['verdict', 'recommendation', 'strengths', 'concerns'],
  properties: {
    verdict: { type: 'string' },
    recommendation: { type: 'string' },
    strengths: { type: 'array', items: { type: 'string' } },
    concerns: { type: 'array', items: { type: 'string' } },
  },
} as const;

const SYSTEM_PROMPT =
  'You are an exam-performance evaluator for a candidate onboarding pipeline. ' +
  'Be concise and factual, grounded only in the score given.';

/**
 * Ported from the same prompt used in n8n's `Exam AI Evaluation` node and
 * Frappe's `_evaluate_exam_with_ai` (both now retired in favor of this one
 * centralized call) — output shape is unchanged so nothing downstream
 * (Frappe's Qualification doc, the Portal's exam_evaluations ingestion)
 * needs to change.
 *
 * Synchronous by design: this is one model call (not a multi-source
 * dossier), so the caller (Frappe) can wait for the response directly,
 * same as its previous direct-Gemini call.
 */
export async function evaluateExam(input: { candidateName: string; score: number }): Promise<ExamEvaluation> {
  return structuredCompletion<ExamEvaluation>({
    model: env.openai.model,
    schemaName: 'exam_evaluation',
    systemPrompt: SYSTEM_PROMPT,
    userPrompt: `Candidate: ${input.candidateName}\nQualifying exam score: ${input.score}/100\n\nEvaluate this candidate's qualifying exam performance.`,
    schema: SCHEMA,
  });
}
