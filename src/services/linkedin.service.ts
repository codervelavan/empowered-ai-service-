export interface LinkedinReport {
  source_status: 'unavailable';
  linkedin_score: null;
  profile_completeness_score: null;
  experience_quality_score: null;
  achievements_score: null;
  certifications_score: null;
  leadership_signal_score: null;
  summary: string;
  strengths: string[];
  risks: string[];
  recommendations: string[];
}

/**
 * Always unavailable, deliberately. There is no compliant public API for
 * reading an arbitrary candidate's LinkedIn profile — the n8n version this
 * replaces had the same honest limitation (its "Create a post in LinkedIn"
 * node was unused by the actual evaluation logic; the LinkedIn Agent ran in
 * "no profile data" fallback for the large majority of candidates). This
 * is a data-access gap, not something a different LLM provider fixes —
 * don't fabricate a score to make the report look more complete than it is.
 */
export async function analyzeLinkedin(profileUrl: string | null | undefined): Promise<LinkedinReport> {
  const hadUrl = Boolean(profileUrl);
  return {
    source_status: 'unavailable',
    linkedin_score: null,
    profile_completeness_score: null,
    experience_quality_score: null,
    achievements_score: null,
    certifications_score: null,
    leadership_signal_score: null,
    summary: hadUrl
      ? 'A LinkedIn URL was provided but no compliant API exists to read profile data from it. Professional verification and social signaling analysis could not be conducted.'
      : 'No LinkedIn profile URL was provided in the candidate data.',
    strengths: [],
    risks: ['Missing LinkedIn profile', 'No verifiable professional history'],
    recommendations: ['Add a LinkedIn profile URL to the application'],
  };
}
