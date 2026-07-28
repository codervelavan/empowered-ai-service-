import { env } from '../config/env.js';
import { structuredCompletion } from './openai.client.js';

export interface ResumeReport {
  source_status: 'verified' | 'partial' | 'unavailable';
  resume_score: number | null;
  ats_score: number | null;
  domain_fit_score: number | null;
  communication_score: number | null;
  impact_score: number | null;
  structure_score: number | null;
  summary: string;
  technical_skills: string[];
  frameworks_tools: string[];
  databases_cloud: string[];
  inferred_skills: string[];
  experience_analysis: string;
  education_analysis: string;
  project_analysis: string;
  strengths: string[];
  risks: string[];
  recommendations: string[];
}

const UNAVAILABLE: ResumeReport = {
  source_status: 'unavailable',
  resume_score: null,
  ats_score: null,
  domain_fit_score: null,
  communication_score: null,
  impact_score: null,
  structure_score: null,
  summary:
    'No résumé text is available for this candidate. The Portal currently stores résumé metadata ' +
    '(filename/size) only — it does not extract or store the file\'s text — so this analysis runs in ' +
    'fallback mode until résumé text extraction is implemented.',
  technical_skills: [],
  frameworks_tools: [],
  databases_cloud: [],
  inferred_skills: [],
  experience_analysis: '',
  education_analysis: '',
  project_analysis: '',
  strengths: [],
  risks: ['No résumé text available for analysis'],
  recommendations: ['Implement résumé text extraction so this analysis can run for real'],
};

const SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: [
    'resume_score', 'ats_score', 'domain_fit_score', 'communication_score', 'impact_score',
    'structure_score', 'summary', 'technical_skills', 'frameworks_tools', 'databases_cloud',
    'inferred_skills', 'experience_analysis', 'education_analysis', 'project_analysis',
    'strengths', 'risks', 'recommendations',
  ],
  properties: {
    resume_score: { type: 'number' },
    ats_score: { type: 'number' },
    domain_fit_score: { type: 'number' },
    communication_score: { type: 'number' },
    impact_score: { type: 'number' },
    structure_score: { type: 'number' },
    summary: { type: 'string' },
    technical_skills: { type: 'array', items: { type: 'string' } },
    frameworks_tools: { type: 'array', items: { type: 'string' } },
    databases_cloud: { type: 'array', items: { type: 'string' } },
    inferred_skills: { type: 'array', items: { type: 'string' } },
    experience_analysis: { type: 'string' },
    education_analysis: { type: 'string' },
    project_analysis: { type: 'string' },
    strengths: { type: 'array', items: { type: 'string' } },
    risks: { type: 'array', items: { type: 'string' } },
    recommendations: { type: 'array', items: { type: 'string' } },
  },
} as const;

/**
 * `resumeText` is only populated once the Portal actually extracts and
 * forwards résumé text (not yet built — see the fallback below and
 * PROJECT-OVERVIEW's known-gaps list). Callers should pass whatever text
 * they have; an empty/missing value is the honest common case today.
 */
export async function analyzeResume(
  resumeText: string | null | undefined,
  preferredDomain: string | null | undefined,
): Promise<ResumeReport> {
  const text = (resumeText ?? '').trim();
  if (text.length < 30) return UNAVAILABLE;

  try {
    const scored = await structuredCompletion<Omit<ResumeReport, 'source_status'>>({
      model: env.openai.model,
      schemaName: 'resume_analysis',
      systemPrompt:
        'You are a technical recruiter analyzing a resume for a candidate onboarding pipeline. ' +
        'Score 0-100 for each dimension. Be concise and factual, grounded only in the resume text given.',
      userPrompt: JSON.stringify({ resume_text: text, preferred_domain: preferredDomain ?? null }),
      schema: SCHEMA,
    });
    return { source_status: 'verified', ...scored };
  } catch (err) {
    return { ...UNAVAILABLE, source_status: 'partial', summary: `Résumé AI scoring failed: ${(err as Error).message}` };
  }
}
