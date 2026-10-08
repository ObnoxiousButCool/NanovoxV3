/**
 * Sign-in: one shared username and password (leadership, 2026-10-08 —
 * replaces the email-OTP flow this branch started with).
 *
 * Called directly through `postJson` rather than a `useQuery` hook: a
 * sign-in attempt is a one-shot action with no result worth caching, unlike
 * every screen's own data.
 */

import { postJson } from '@/shared/api/client'
import type { components } from '@/shared/api/schema'

export type LoginResponse = components['schemas']['LoginResponse']

export async function login(username: string, password: string): Promise<LoginResponse> {
  return postJson<LoginResponse>('/auth/login', { username, password })
}
