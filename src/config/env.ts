import 'dotenv/config';

const isTest = process.env.NODE_ENV === 'test';

export const env = {
  nodeEnv: process.env.NODE_ENV ?? 'development',
  port: Number(process.env.PORT ?? 4200),
  corsOrigins: (process.env.CORS_ORIGIN ?? 'http://localhost:4000')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean),

  // Shared-secret bearer token callers (Portal, Frappe) present. This
  // service is internal-only — never exposed publicly — so a single static
  // token is proportionate; no need for the HMAC-per-request scheme the
  // Portal uses for its public webhook endpoints.
  serviceAuthToken: isTest ? 'test-token' : (process.env.SERVICE_AUTH_TOKEN ?? 'dev-insecure-token'),

  openai: {
    apiKey: process.env.OPENAI_API_KEY ?? '',
    // Any OpenAI-compatible endpoint. Leave unset for OpenAI itself; set to
    // https://openrouter.ai/api/v1 to route through OpenRouter (whose keys
    // start `sk-or-v1-`). Model ids differ per provider — OpenRouter needs
    // the `vendor/model` form, e.g. `google/gemma-4-26b-a4b-it:free`.
    baseUrl: process.env.OPENAI_BASE_URL ?? '',
    model: process.env.OPENAI_MODEL ?? 'gpt-4o-mini',
    // Only the final consolidated report uses this; falls back to `model`.
    consolidationModel: process.env.OPENAI_CONSOLIDATION_MODEL ?? process.env.OPENAI_MODEL ?? 'gpt-4o',
  },

  github: {
    token: process.env.GITHUB_TOKEN ?? '',
  },

  portal: {
    baseUrl: (process.env.PORTAL_BASE_URL ?? 'http://localhost:4000').replace(/\/$/, ''),
    webhookSecret: process.env.PORTAL_WEBHOOK_SECRET ?? 'dev-webhook-secret',
  },
} as const;
