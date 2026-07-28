import { env } from '../config/env.js';
import { structuredCompletion } from './openai.client.js';
import type { GithubReport } from './github.service.js';
import type { LeetcodeReport } from './leetcode.service.js';
import type { LinkedinReport } from './linkedin.service.js';
import type { ResumeReport } from './resume.service.js';

// Must match the DB enum exactly (db/migrations/001) — see
// empowered/server/src/routes/webhooks.routes.ts's HIRING_RECOMMENDATIONS.
export const HIRING_RECOMMENDATIONS = [
  'Strong Hire',
  'Hire',
  'Needs Interview',
  'Needs Review',
  'Do Not Proceed',
] as const;

export interface ConsolidatedReport {
  overall_score: number;
  confidence_score: number | null;
  hiring_recommendation: (typeof HIRING_RECOMMENDATIONS)[number];
  academic_score: number | null;
  domain_alignment_score: number | null;
  professional_presence_score: number | null;
  engineering_score: number | null;
  coding_assessment_score: number | null;
  salary_expectation_fit_score: number | null;
  final_summary: string;
  executive_summary: string;
  academics_analysis: string;
  resume_analysis: string;
  github_analysis: string;
  leetcode_analysis: string;
  linkedin_analysis: string;
  compensation_analysis: string;
  overall_verdict: string;
  top_strengths: string[];
  top_concerns: string[];
  interview_focus_areas: string[];
  recommended_roles: string[];
}

export interface CandidateBasics {
  fullName: string;
  domain: string | null;
  college: string | null;
  cgpa: number | null;
  desiredSalary?: string | null;
}

const SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: [
    'overall_score', 'confidence_score', 'hiring_recommendation', 'academic_score',
    'domain_alignment_score', 'professional_presence_score', 'engineering_score',
    'coding_assessment_score', 'salary_expectation_fit_score', 'final_summary',
    'executive_summary', 'academics_analysis', 'resume_analysis', 'github_analysis',
    'leetcode_analysis', 'linkedin_analysis', 'compensation_analysis', 'overall_verdict',
    'top_strengths', 'top_concerns', 'interview_focus_areas', 'recommended_roles',
  ],
  properties: {
    overall_score: { type: 'number' },
    confidence_score: { type: ['number', 'null'] },
    hiring_recommendation: { type: 'string', enum: [...HIRING_RECOMMENDATIONS] },
    academic_score: { type: ['number', 'null'] },
    domain_alignment_score: { type: ['number', 'null'] },
    professional_presence_score: { type: ['number', 'null'] },
    engineering_score: { type: ['number', 'null'] },
    coding_assessment_score: { type: ['number', 'null'] },
    salary_expectation_fit_score: { type: ['number', 'null'] },
    final_summary: { type: 'string' },
    executive_summary: { type: 'string' },
    academics_analysis: { type: 'string' },
    resume_analysis: { type: 'string' },
    github_analysis: { type: 'string' },
    leetcode_analysis: { type: 'string' },
    linkedin_analysis: { type: 'string' },
    compensation_analysis: { type: 'string' },
    overall_verdict: { type: 'string' },
    top_strengths: { type: 'array', items: { type: 'string' } },
    top_concerns: { type: 'array', items: { type: 'string' } },
    interview_focus_areas: { type: 'array', items: { type: 'string' } },
    recommended_roles: { type: 'array', items: { type: 'string' } },
  },
} as const;

/**
 * The one call that produces the report actually stored in
 * ai_evaluation_reports. Deliberately does NOT ask the model for
 * placement_probability — the Portal's own docs are explicit that this is
 * "sent as null rather than fabricated" until a real model for it exists;
 * the orchestrator sets it to null directly, it is never part of this
 * schema.
 */
export async function consolidate(input: {
  candidate: CandidateBasics;
  linkedin: LinkedinReport;
  github: GithubReport;
  leetcode: LeetcodeReport;
  resume: ResumeReport;
}): Promise<ConsolidatedReport> {
  return structuredCompletion<ConsolidatedReport>({
    model: env.openai.consolidationModel,
    schemaName: 'candidate_hiring_evaluation',
    systemPrompt:
      'You are the final-stage evaluator in a candidate hiring pipeline, consolidating four independent ' +
      'source analyses (LinkedIn, GitHub, LeetCode, résumé) into one hiring recommendation. Be concise, ' +
      'factual, and ground every claim only in the data given — do not invent facts the sources do not ' +
      'support. hiring_recommendation MUST be exactly one of: ' +
      HIRING_RECOMMENDATIONS.join(', ') +
      '. If a source is unavailable, treat its absence as a genuine gap, not a red flag — reflect that ' +
      "honestly rather than penalizing the candidate for what wasn't collected.",
    userPrompt: JSON.stringify({
      candidate: input.candidate,
      source_reports: {
        linkedin: input.linkedin,
        github: input.github,
        leetcode: input.leetcode,
        resume: input.resume,
      },
    }),
    schema: SCHEMA,
  });
}
