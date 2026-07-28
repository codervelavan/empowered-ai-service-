import type { NextFunction, Request, RequestHandler, Response } from 'express';

/** Forwards a rejected promise from an async route handler to Express's error middleware. */
export function asyncHandler(fn: (req: Request, res: Response, next: NextFunction) => Promise<void>): RequestHandler {
  return (req, res, next) => {
    fn(req, res, next).catch(next);
  };
}
