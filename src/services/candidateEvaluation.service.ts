import { randomUUID } from 'node:crypto';
import { analyzeGithub } from './github.service.js';
import { analyzeLeetcode } from './leetcode.service.js';
import { analyzeLinkedin } from './linkedin.service.js';
import { analyzeResume } from './resume.service.js';
import { consolidate } from './dossier.service.js';
import { pushAiEvaluation } from './portalClient.js';

export interface CandidateEvaluationInput {
  candidateId: string;
  candidateName: string;
  email: string;
  domain: string | null;
  college: string | null;
  cgpa: number | null;
  github: string | null;
  linkedin: string | null;
  leetcode: string | null;
  // Not yet populated by any real caller — the Portal only stores résumé
  // metadata (filename/size), not extracted text. Accepted here so this
  // service is ready the moment that's built, without an API change.
  resumeText?: string | null;
}

/**
 * Runs the full 4-source evaluation and pushes the result to the Portal.
 * Replaces n8n's profiling workflow (LinkedIn/GitHub/LeetCode/Résumé
 * Agents -> merge -> Final Candidate Profile Agent -> Push Evaluation to
 * Portal) as one in-process pipeline.
 *
 * Fire-and-forget from the route handler's perspective: this takes real
 * wall-clock time (multiple LLM + external API calls), so
 * evaluate.routes.ts returns 202 immediately and this runs in the
 * background. Never throws past its own boundary -- every failure is
 * caught and logged; a failed evaluation must not crash the service.
 */
export async function runCandidateEvaluation(input: CandidateEvaluationInput): Promise<void> {
  const runId = randomUUID();
  try {
    const [linkedin, github, leetcode, resume] = await Promise.all([
      analyzeLinkedin(input.linkedin),
      analyzeGithub(input.github),
      analyzeLeetcode(input.leetcode),
      analyzeResume(input.resumeText, input.domain),
    ]);

    const consolidated = await consolidate({
      candidate: { fullName: input.candidateName, domain: input.domain, college: input.college, cgpa: input.cgpa },
      linkedin,
      github,
      leetcode,
      resume,
    });

    const payload = {
      run_id: runId,
      candidate_id: input.candidateId,
      ...consolidated,
      // Deliberately not asked of the model — see dossier.service.ts.
      placement_probability: null,
      processed_at: new Date().toISOString(),
      source_reports: { linkedin, github, leetcode, resume },
    };

    const result = await pushAiEvaluation(payload);
    if (!result.ok) {
      console.error(`[evaluation ${runId}] push to portal failed`, result.status, result.error);
    } else {
      console.log(`[evaluation ${runId}] completed for ${input.candidateId}`);
    }
  } catch (err) {
    console.error(`[evaluation ${runId}] failed for ${input.candidateId}:`, (err as Error).message);
  }
}
