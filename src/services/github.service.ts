import { env } from '../config/env.js';
import { structuredCompletion } from './openai.client.js';

export interface GithubReport {
  source_status: 'verified' | 'partial' | 'unavailable';
  github_score: number | null;
  repo_quality_score: number | null;
  consistency_score: number | null;
  contribution_score: number | null;
  collaboration_score: number | null;
  open_source_score: number | null;
  summary: string;
  strengths: string[];
  risks: string[];
  recommendations: string[];
  top_languages: string[];
  public_repos: number;
  public_gists: number;
  followers: number;
  following: number;
  account_created_at: string | null;
  last_activity_at: string | null;
  recent_pushes_count: number;
  total_stars: number;
  total_forks: number;
  avg_repo_size_kb: number;
  languages_count: number;
  top_repositories: Array<{
    name: string;
    url: string | null;
    description: string | null;
    language: string | null;
    size_kb: number | null;
    stargazers_count: number;
    forks_count: number;
    open_issues_count: number;
    repo_created_at: string | null;
    repo_updated_at: string | null;
    repo_pushed_at: string | null;
  }>;
}

const UNAVAILABLE: GithubReport = {
  source_status: 'unavailable',
  github_score: null,
  repo_quality_score: null,
  consistency_score: null,
  contribution_score: null,
  collaboration_score: null,
  open_source_score: null,
  summary: 'No GitHub username was provided in the candidate data.',
  strengths: [],
  risks: ['Missing GitHub profile'],
  recommendations: ['Add a GitHub username to the application'],
  top_languages: [],
  public_repos: 0,
  public_gists: 0,
  followers: 0,
  following: 0,
  account_created_at: null,
  last_activity_at: null,
  recent_pushes_count: 0,
  total_stars: 0,
  total_forks: 0,
  avg_repo_size_kb: 0,
  languages_count: 0,
  top_repositories: [],
};

function ghHeaders(): Record<string, string> {
  const headers: Record<string, string> = { accept: 'application/vnd.github+json' };
  if (env.github.token) headers.authorization = `Bearer ${env.github.token}`;
  return headers;
}

async function fetchJson(url: string): Promise<unknown> {
  const res = await fetch(url, { headers: ghHeaders(), signal: AbortSignal.timeout(10_000) });
  if (!res.ok) throw new Error(`GitHub API ${res.status} for ${url}`);
  return res.json();
}

const SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: [
    'github_score', 'repo_quality_score', 'consistency_score', 'contribution_score',
    'collaboration_score', 'open_source_score', 'summary', 'strengths', 'risks', 'recommendations',
  ],
  properties: {
    github_score: { type: 'number' },
    repo_quality_score: { type: 'number' },
    consistency_score: { type: 'number' },
    contribution_score: { type: 'number' },
    collaboration_score: { type: 'number' },
    open_source_score: { type: 'number' },
    summary: { type: 'string' },
    strengths: { type: 'array', items: { type: 'string' } },
    risks: { type: 'array', items: { type: 'string' } },
    recommendations: { type: 'array', items: { type: 'string' } },
  },
} as const;

interface ScoredFields {
  github_score: number;
  repo_quality_score: number;
  consistency_score: number;
  contribution_score: number;
  collaboration_score: number;
  open_source_score: number;
  summary: string;
  strengths: string[];
  risks: string[];
  recommendations: string[];
}

export async function analyzeGithub(username: string | null | undefined): Promise<GithubReport> {
  if (!username) return UNAVAILABLE;

  let profile: Record<string, unknown>;
  let repos: Record<string, unknown>[];
  try {
    profile = (await fetchJson(`https://api.github.com/users/${encodeURIComponent(username)}`)) as Record<
      string,
      unknown
    >;
    repos = (await fetchJson(
      `https://api.github.com/users/${encodeURIComponent(username)}/repos?sort=pushed&per_page=30`,
    )) as Record<string, unknown>[];
  } catch (err) {
    return {
      ...UNAVAILABLE,
      summary: `GitHub username "${username}" could not be reached: ${(err as Error).message}`,
      risks: ['GitHub profile could not be fetched'],
    };
  }

  // Deterministic aggregates computed here, not by the model — arithmetic
  // on real data is more reliable and cheaper than asking an LLM to sum.
  const nonForkRepos = repos.filter((r) => !r.fork);
  const totalStars = nonForkRepos.reduce((s, r) => s + (Number(r.stargazers_count) || 0), 0);
  const totalForks = nonForkRepos.reduce((s, r) => s + (Number(r.forks_count) || 0), 0);
  const sizes = nonForkRepos.map((r) => Number(r.size) || 0).filter((s) => s > 0);
  const avgRepoSizeKb = sizes.length ? Math.round(sizes.reduce((a, b) => a + b, 0) / sizes.length) : 0;
  const languageCounts = new Map<string, number>();
  for (const r of nonForkRepos) {
    const lang = r.language as string | null;
    if (lang) languageCounts.set(lang, (languageCounts.get(lang) ?? 0) + 1);
  }
  const topLanguages = [...languageCounts.entries()].sort((a, b) => b[1] - a[1]).map(([lang]) => lang).slice(0, 8);
  const topRepositories = [...nonForkRepos]
    .sort((a, b) => (Number(b.stargazers_count) || 0) - (Number(a.stargazers_count) || 0))
    .slice(0, 5)
    .map((r) => ({
      name: String(r.name ?? 'repo'),
      url: (r.html_url as string) ?? null,
      description: (r.description as string) ?? null,
      language: (r.language as string) ?? null,
      size_kb: (r.size as number) ?? null,
      stargazers_count: Number(r.stargazers_count) || 0,
      forks_count: Number(r.forks_count) || 0,
      open_issues_count: Number(r.open_issues_count) || 0,
      repo_created_at: (r.created_at as string) ?? null,
      repo_updated_at: (r.updated_at as string) ?? null,
      repo_pushed_at: (r.pushed_at as string) ?? null,
    }));
  const mostRecentPush = nonForkRepos
    .map((r) => r.pushed_at as string | undefined)
    .filter(Boolean)
    .sort()
    .at(-1) ?? null;
  const recentPushesCount = nonForkRepos.filter((r) => {
    const pushed = r.pushed_at ? Date.parse(r.pushed_at as string) : 0;
    return Date.now() - pushed < 1000 * 60 * 60 * 24 * 90; // last 90 days
  }).length;

  let scored: ScoredFields;
  if (!isReachableProfile(profile)) {
    return { ...UNAVAILABLE, summary: `GitHub user "${username}" was not found.` };
  }

  try {
    scored = await structuredCompletion<ScoredFields>({
      model: env.openai.model,
      schemaName: 'github_analysis',
      systemPrompt:
        'You are a technical recruiter analyzing a GitHub profile for a candidate onboarding pipeline. ' +
        'Score 0-100 for each dimension. Be concise and factual, grounded only in the data given.',
      userPrompt: JSON.stringify({
        profile: {
          login: profile.login,
          name: profile.name,
          bio: profile.bio,
          public_repos: profile.public_repos,
          followers: profile.followers,
          following: profile.following,
          created_at: profile.created_at,
        },
        aggregate_stats: {
          total_stars: totalStars,
          total_forks: totalForks,
          languages_count: languageCounts.size,
          top_languages: topLanguages,
          recent_pushes_count: recentPushesCount,
        },
        top_repositories: topRepositories,
      }),
      schema: SCHEMA,
    });
  } catch (err) {
    return {
      ...UNAVAILABLE,
      source_status: 'partial',
      summary: `GitHub profile fetched but AI scoring failed: ${(err as Error).message}`,
      public_repos: Number(profile.public_repos) || 0,
      followers: Number(profile.followers) || 0,
      following: Number(profile.following) || 0,
      account_created_at: (profile.created_at as string) ?? null,
    };
  }

  return {
    source_status: 'verified',
    ...scored,
    top_languages: topLanguages,
    public_repos: Number(profile.public_repos) || 0,
    public_gists: Number(profile.public_gists) || 0,
    followers: Number(profile.followers) || 0,
    following: Number(profile.following) || 0,
    account_created_at: (profile.created_at as string) ?? null,
    last_activity_at: mostRecentPush,
    recent_pushes_count: recentPushesCount,
    total_stars: totalStars,
    total_forks: totalForks,
    avg_repo_size_kb: avgRepoSizeKb,
    languages_count: languageCounts.size,
    top_repositories: topRepositories,
  };
}

function isReachableProfile(profile: Record<string, unknown>): boolean {
  return typeof profile.login === 'string';
}
