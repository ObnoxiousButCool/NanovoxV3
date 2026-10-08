/**
 * The email-OTP sign-in endpoints.
 *
 * Called directly through `postJson` rather than a `useQuery` hook: a
 * sign-in attempt is a one-shot action with no result worth caching, unlike
 * every screen's own data.
 */

import { postJson } from '@/shared/api/client'
import type { components } from '@/shared/api/schema'

export type RequestOtpResponse = components['schemas']['RequestOtpResponse']
export type VerifyOtpResponse = components['schemas']['VerifyOtpResponse']

export async function requestOtp(email: string): Promise<RequestOtpResponse> {
  return postJson<RequestOtpResponse>('/auth/otp/request', { email })
}

export async function verifyOtp(email: string, code: string): Promise<VerifyOtpResponse> {
  return postJson<VerifyOtpResponse>('/auth/otp/verify', { email, code })
}
