import type { NextFunction, Request, Response } from 'express';
import { env } from '../config/env.js';

/**
 * This service is internal-only — Portal and Frappe are its only callers,
 * over a network path that's already private (localhost / VPC / same
 * cloud), so a static bearer token is proportionate. It is deliberately
 * simpler than the Portal's per-request HMAC scheme, which exists to
 * protect a *publicly reachable* webhook endpoint — this one is never
 * public.
 */
export function requireServiceToken(req: Request, res: Response, next: NextFunction) {
  const header = req.headers.authorization;
  const token = header?.startsWith('Bearer ') ? header.slice(7) : undefined;
  if (!token || token !== env.serviceAuthToken) {
    res.status(401).json({ error: { code: 'unauthorized', message: 'Invalid or missing service token' } });
    return;
  }
  next();
}
