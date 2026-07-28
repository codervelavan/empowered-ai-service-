import OpenAI from 'openai';
import { env } from '../config/env.js';

let client: OpenAI | null = null;

function getClient(): OpenAI {
  if (!client) {
    if (!env.openai.apiKey) {
      throw new Error('OPENAI_API_KEY is not set');
    }
    client = new OpenAI({
      apiKey: env.openai.apiKey,
      // Only pass baseURL when configured, so the SDK keeps its own default
      // for OpenAI proper. Set it to route through an OpenAI-compatible
      // gateway such as OpenRouter.
      ...(env.openai.baseUrl ? { baseURL: env.openai.baseUrl } : {}),
    });
  }
  return client;
}

/**
 * One structured-JSON call. Uses OpenAI's Structured Outputs
 * (response_format: json_schema) so the model is constrained to the exact
 * shape the caller needs — far more reliable than asking for JSON in the
 * prompt and hoping, which is what broke silently in the old n8n pipeline
 * (a model that returned prose instead of JSON produced an empty,
 * indistinguishable-from-valid evaluation).
 */
export async function structuredCompletion<T>(input: {
  model: string;
  systemPrompt: string;
  userPrompt: string;
  schemaName: string;
  schema: Record<string, unknown>;
}): Promise<T> {
  const res = await getClient().chat.completions.create({
    model: input.model,
    messages: [
      { role: 'system', content: input.systemPrompt },
      { role: 'user', content: input.userPrompt },
    ],
    response_format: {
      type: 'json_schema',
      json_schema: {
        name: input.schemaName,
        strict: true,
        schema: input.schema,
      },
    },
  });

  const raw = res.choices[0]?.message?.content;
  if (!raw) throw new Error(`OpenAI returned no content for schema ${input.schemaName}`);
  return JSON.parse(raw) as T;
}

export function isConfigured(): boolean {
  return Boolean(env.openai.apiKey);
}
