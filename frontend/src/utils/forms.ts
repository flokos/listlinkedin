// Turning API errors into form feedback: messages under the fields they belong to, and one
// general message for everything else.
import { ApiError, NetworkError } from '../api'

export interface FormErrors<F extends string> {
  fields: Record<F, string[]>
  /** A message for the whole form, or '' when every problem belongs to a field. */
  form: string
}

export function noErrors<F extends string>(fields: readonly F[]): FormErrors<F> {
  const empty = {} as Record<F, string[]>
  for (const field of fields) empty[field] = []
  return { fields: empty, form: '' }
}

/** Splits an error from an account request into field messages and a general message. */
export function formErrors<F extends string>(error: unknown, fields: readonly F[]): FormErrors<F> {
  const result = noErrors(fields)
  if (error instanceof NetworkError) return { ...result, form: error.message }
  if (!(error instanceof ApiError)) {
    return { ...result, form: 'Something went wrong. Please try again.' }
  }
  const others: string[] = []
  for (const [field, messages] of Object.entries(error.fieldErrors)) {
    if ((fields as readonly string[]).includes(field)) result.fields[field as F] = messages
    else others.push(...messages)
  }
  const anyField = fields.some((f) => result.fields[f].length)
  result.form =
    error.detail ??
    others[0] ??
    (anyField
      ? ''
      : error.status === 429
        ? 'Too many attempts. Please wait a few minutes and try again.'
        : 'Something went wrong. Please try again.')
  return result
}
