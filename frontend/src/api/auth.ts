// Accounts: django-allauth's headless browser API (/_allauth/browser/v1/) for signing in and
// out, sign-up, email verification and passwords, plus /api/v2/session/ and /api/v2/me/.
// allauth answers 401 when a step succeeded but left you signed out (sign-out itself, a
// password reset, verifying while signed out); those 401s are successes here.
import { ApiError, request } from './client'

export interface SessionUser {
  id: string
  email: string
  display_name: string
  email_verified: boolean
}

const AUTH = '/_allauth/browser/v1'

const signedOutIsFine = (error: unknown) => {
  if (error instanceof ApiError && error.status === 401 && !error.detail) return
  throw error
}

/** Who is signed in. Also sets the CSRF cookie that later writes send back. */
export const getSession = (signal?: AbortSignal) =>
  request<{ user: SessionUser | null }>('/api/v2/session/', { signal }).then((data) => data.user)

export const signIn = (email: string, password: string) =>
  request<unknown>(`${AUTH}/auth/login`, { method: 'POST', body: { email, password } })

export const signUp = (email: string, password: string) =>
  request<unknown>(`${AUTH}/auth/signup`, { method: 'POST', body: { email, password } })

export const signOut = () =>
  request<unknown>(`${AUTH}/auth/session`, { method: 'DELETE' }).then(() => {}, signedOutIsFine)

/** Emails a reset link if the address has an account. The answer never tells either way. */
export const requestPasswordReset = (email: string) =>
  request<unknown>(`${AUTH}/auth/password/request`, { method: 'POST', body: { email } })

/** Resolves if the reset key is valid; ApiError(400) if it's expired or already used. */
export const checkPasswordResetKey = (key: string) =>
  request<unknown>(`${AUTH}/auth/password/reset`, { headers: { 'X-Password-Reset-Key': key } })

export const resetPassword = (key: string, password: string) =>
  request<unknown>(`${AUTH}/auth/password/reset`, {
    method: 'POST',
    body: { key, password },
  }).then(() => {}, signedOutIsFine)

export const verifyEmail = (key: string) =>
  request<unknown>(`${AUTH}/auth/email/verify`, { method: 'POST', body: { key } }).then(
    () => {},
    signedOutIsFine,
  )

/** Sends a new verification email. Resolves false when none was sent (one went out recently). */
export const resendVerification = (email: string) =>
  request<unknown>(`${AUTH}/account/email`, { method: 'PUT', body: { email } }).then(
    () => true,
    (error: unknown) => {
      if (error instanceof ApiError && error.status === 403) return false
      throw error
    },
  )

export const changePassword = (currentPassword: string, newPassword: string) =>
  request<unknown>(`${AUTH}/account/password/change`, {
    method: 'POST',
    body: { current_password: currentPassword, new_password: newPassword },
  })

export const updateMe = (changes: { display_name: string }) =>
  request<SessionUser>('/api/v2/me/', { method: 'PATCH', body: changes })

/** Deletes the account and every list it owns, and ends the session. `confirm` is the email. */
export const deleteAccount = (confirm: string) =>
  request<null>('/api/v2/me/', { method: 'DELETE', body: { confirm } })
