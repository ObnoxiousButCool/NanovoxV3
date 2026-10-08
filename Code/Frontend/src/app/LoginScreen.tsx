/**
 * Sign-in: one shared username and password (leadership, 2026-10-08 —
 * replaces the email-OTP flow this branch started with; see
 * Documents/notes/Decisions-and-Questions.md).
 *
 * One step, one message for any wrong input: the API does not say which of
 * username or password was wrong, so this screen has nothing distinct to
 * show either (`application.use_cases.auth.Login`).
 */

import { useState } from 'react'
import type { FormEvent } from 'react'

import { ApiError } from '@/shared/api/client'
import { useAuth } from '@/shared/auth/authContext'
import '@/app/login.css'

function messageFor(cause: unknown): string {
  if (cause instanceof ApiError) {
    return cause.detail ?? cause.message
  }
  return 'The server could not be reached. Check your connection and try again.'
}

export function LoginScreen() {
  const { login } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(event: FormEvent): Promise<void> {
    event.preventDefault()
    setPending(true)
    setError(null)
    try {
      await login(username, password)
    } catch (cause) {
      setError(messageFor(cause))
      setPassword('')
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

        <form
          className="nv-login-form"
          onSubmit={(event) => {
            void submit(event)
          }}
        >
          <h1>Sign in</h1>
          <label htmlFor="login-username">Username</label>
          <input
            id="login-username"
            type="text"
            autoComplete="username"
            required
            value={username}
            onChange={(event) => {
              setUsername(event.target.value)
            }}
          />
          <label htmlFor="login-password">Password</label>
          <input
            id="login-password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => {
              setPassword(event.target.value)
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
            disabled={pending || username.trim() === '' || password === ''}
          >
            {pending ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  )
}
