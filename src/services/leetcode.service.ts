import { env } from '../config/env.js';
import { structuredCompletion } from './openai.client.js';

export interface LeetcodeReport {
  source_status: 'verified' | 'partial' | 'unavailable';
  leetcode_score: number | null;
  problem_solving_score: number | null;
  contest_score: number | null;
  consistency_score: number | null;
  dsa_depth_score: number | null;
  summary: string;
  strengths: string[];
  risks: string[];
  recommendations: string[];
}

const UNAVAILABLE: LeetcodeReport = {
  source_status: 'unavailable',
  leetcode_score: null,
  problem_solving_score: null,
  contest_score: null,
  consistency_score: null,
  dsa_depth_score: null,
  summary: 'No LeetCode username was provided in the candidate data.',
  strengths: [],
  risks: ['Missing LeetCode profile'],
  recommendations: ['Add a LeetCode username to the application'],
};

const QUERY = `
query userStats($username: String!) {
  matchedUser(username: $username) {
    username
    profile { ranking reputation }
    submitStats {
      acSubmissionNum { difficulty count }
    }
  }
  userContestRanking(username: $username) {
    rating
    globalRanking
    attendedContestsCount
  }
}`;

const SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: [
    'leetcode_score', 'problem_solving_score', 'contest_score', 'consistency_score',
    'dsa_depth_score', 'summary', 'strengths', 'risks', 'recommendations',
  ],
  properties: {
    leetcode_score: { type: 'number' },
    problem_solving_score: { type: 'number' },
    contest_score: { type: 'number' },
    consistency_score: { type: 'number' },
    dsa_depth_score: { type: 'number' },
    summary: { type: 'string' },
    strengths: { type: 'array', items: { type: 'string' } },
    risks: { type: 'array', items: { type: 'string' } },
    recommendations: { type: 'array', items: { type: 'string' } },
  },
} as const;

export async function analyzeLeetcode(username: string | null | undefined): Promise<LeetcodeReport> {
  if (!username) return UNAVAILABLE;

  let data: {
    matchedUser?: {
      profile?: { ranking?: number; reputation?: number };
      submitStats?: { acSubmissionNum?: Array<{ difficulty: string; count: number }> };
    } | null;
    userContestRanking?: { rating?: number; globalRanking?: number; attendedContestsCount?: number } | null;
  };

  try {
    const res = await fetch('https://leetcode.com/graphql', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ query: QUERY, variables: { username } }),
      signal: AbortSignal.timeout(10_000),
    });
    if (!res.ok) throw new Error(`LeetCode GraphQL ${res.status}`);
    const body = (await res.json()) as { data: typeof data };
    data = body.data;
  } catch (err) {
    return { ...UNAVAILABLE, summary: `LeetCode profile could not be fetched: ${(err as Error).message}` };
  }

  if (!data.matchedUser) {
    return { ...UNAVAILABLE, summary: `LeetCode user "${username}" was not found.` };
  }

  const solved = data.matchedUser.submitStats?.acSubmissionNum ?? [];

  try {
    const scored = await structuredCompletion<Omit<LeetcodeReport, 'source_status'>>({
      model: env.openai.model,
      schemaName: 'leetcode_analysis',
      systemPrompt:
        'You are a technical recruiter analyzing a LeetCode profile for a candidate onboarding pipeline. ' +
        'Score 0-100 for each dimension. Be concise and factual, grounded only in the data given.',
      userPrompt: JSON.stringify({
        ranking: data.matchedUser.profile?.ranking,
        reputation: data.matchedUser.profile?.reputation,
        problems_solved_by_difficulty: solved,
        contest: data.userContestRanking ?? null,
      }),
      schema: SCHEMA,
    });
    return { source_status: 'verified', ...scored };
  } catch (err) {
    return {
      ...UNAVAILABLE,
      source_status: 'partial',
      summary: `LeetCode profile fetched but AI scoring failed: ${(err as Error).message}`,
    };
  }
}
