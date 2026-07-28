import { describe, expect, it } from 'vitest';
import request from 'supertest';
import { createApp } from '../src/app.js';

const app = createApp();

describe('GET /health', () => {
  it('returns ok without requiring auth', async () => {
    const res = await request(app).get('/health');
    expect(res.status).toBe(200);
    expect(res.body.status).toBe('ok');
    expect(res.body).toHaveProperty('openaiConfigured');
  });
});

describe('auth guard', () => {
  it('rejects /evaluate/candidate without a service token', async () => {
    const res = await request(app).post('/evaluate/candidate').send({});
    expect(res.status).toBe(401);
  });

  it('rejects /evaluate/exam without a service token', async () => {
    const res = await request(app).post('/evaluate/exam').send({});
    expect(res.status).toBe(401);
  });

  it('rejects a wrong service token', async () => {
    const res = await request(app)
      .post('/evaluate/candidate')
      .set('authorization', 'Bearer wrong-token')
      .send({});
    expect(res.status).toBe(401);
  });

  it('accepts the correct service token (test env) and validates the body', async () => {
    const res = await request(app)
      .post('/evaluate/candidate')
      .set('authorization', 'Bearer test-token')
      .send({});
    // Auth passes, but the body is empty -> Zod validation_error, not 401.
    expect(res.status).toBe(400);
    expect(res.body.error.code).toBe('validation_error');
  });
});
