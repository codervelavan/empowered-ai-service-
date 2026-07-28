import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import rateLimit from 'express-rate-limit';
import { env } from './config/env.js';
import { errorHandler, notFoundHandler } from './middleware/error.js';
import { evaluateRouter } from './routes/evaluate.routes.js';
import { isConfigured } from './services/openai.client.js';

export function createApp() {
  const app = express();

  app.use(helmet());
  app.use(cors({ origin: env.corsOrigins }));
  app.use(express.json({ limit: '2mb' }));

  // This service is internal-only (Portal + Frappe are its only callers),
  // but a generous rate limit still guards against a misbehaving caller
  // hammering the OpenAI/GitHub/LeetCode APIs on our behalf.
  app.use(rateLimit({ windowMs: 60_000, max: 60, standardHeaders: true }));

  app.get('/health', (_req, res) => {
    res.json({ status: 'ok', openaiConfigured: isConfigured(), time: new Date().toISOString() });
  });

  app.use('/evaluate', evaluateRouter);

  app.use(notFoundHandler);
  app.use(errorHandler);

  return app;
}
