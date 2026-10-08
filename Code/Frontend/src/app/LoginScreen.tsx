/**
 * Email-OTP sign-in (feature/email-otp-login, not on main).
 *
 * Two steps, one screen: ask for an email, then ask for the code it was
 * sent. Deliberately no "that email is not recognised" state — the API
 * answers a request the same way whether or not the address is approved
 * (`application.use_cases.auth.RequestOtp`), so there is nothing distinct
 * for this screen to show even if it wanted to.
 */

import { useState } from 'react'
import type { FormEvent } from 'react'

import { ApiError } from '@/shared/api/client'
import { useAuth } from '@/shared/auth/authContext'
import '@/app/login.css'

type Step = 'email' | 'code'

function messageFor(cause: unknown): string {
  if (cause instanceof ApiError) {
    return cause.detail ?? cause.message
  }
  return 'The server could not be reached. Check your connection and try again.'
}

export function LoginScreen() {
  const { requestOtp, verifyOtp } = useAuth()
  const [step, setStep] = useState<Step>('email')
  const [email, setEmail] = useState('')
  const [code, setCode] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submitEmail(event: FormEvent): Promise<void> {
    event.preventDefault()
    setPending(true)
    setError(null)
    try {
      await requestOtp(email)
      setStep('code')
    } catch (cause) {
      setError(messageFor(cause))
    } finally {
      setPending(false)
    }
  }

  async function submitCode(event: FormEvent): Promise<void> {
    event.preventDefault()
    setPending(true)
    setError(null)
    try {
      await verifyOtp(email, code)
    } catch (cause) {
      setError(messageFor(cause))
      setCode('')
    } finally {
      setPending(false)
    }
  }

  async function resend(): Promise<void> {
    setPending(true)
    setError(null)
    try {
      await requestOtp(email)
    } catch (cause) {
      setError(messageFor(cause))
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="nv-login">
      <div className="nv-login-card">
        <div className="nv-login-brand">
          <span className="nv-login-mark" aria-hidden="true">
            NV
          </span>
          <b>NanoVox Insights</b>
        </div>

        {step === 'email' ? (
          <form
            className="nv-login-form"
            onSubmit={(event) => {
              void submitEmail(event)
            }}
          >
            <h1>Sign in</h1>
            <p className="nv-login-lede">Enter your email and we will send you a one-time code.</p>
            <label htmlFor="login-email">Email</label>
            <input
              id="login-email"
              type="email"
              required
              value={email}
              placeholder="you@company.com"
              onChange={(event) => {
                setEmail(event.target.value)
              }}
            />
            {error ? (
              <p className="nv-login-error" role="alert">
                {error}
              </p>
            ) : null}
            <button
              type="submit"
              className="nv-login-submit"
              disabled={pending || email.trim() === ''}
            >
              {pending ? 'Sending…' : 'Send code'}
            </button>
          </form>
        ) : (
          <form
            className="nv-login-form"
            onSubmit={(event) => {
              void submitCode(event)
            }}
          >
            <h1>Enter your code</h1>
            <p className="nv-login-lede">
              We sent a 6-digit code to <b>{email}</b>.
            </p>
            <label htmlFor="login-code">Code</label>
            <input
              id="login-code"
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              required
              maxLength={6}
              value={code}
              placeholder="000000"
              onChange={(event) => {
                setCode(event.target.value.replace(/\D/g, '').slice(0, 6))
              }}
            />
            {error ? (
              <p className="nv-login-error" role="alert">
                {error}
              </p>
            ) : null}
            <button type="submit" className="nv-login-submit" disabled={pending || code.length !== 6}>
              {pending ? 'Verifying…' : 'Verify'}
            </button>
            <button
              type="button"
              className="nv-login-link"
              disabled={pending}
              onClick={() => {
                void resend()
              }}
            >
              Resend code
            </button>
            <button
              type="button"
              className="nv-login-link"
              onClick={() => {
                setStep('email')
                setCode('')
                setError(null)
              }}
            >
              Use a different email
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
