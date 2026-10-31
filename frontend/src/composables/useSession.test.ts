import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  getSession: vi.fn(),
  signIn: vi.fn(),
  signUp: vi.fn(),
  signOut: vi.fn(),
  updateMe: vi.fn(),
}))
vi.mock('../api', () => api)

const ada = { id: '1', email: 'ada@example.com', display_name: '', email_verified: false }

/** The session store keeps module-level state; each test gets a fresh copy. */
async function fresh() {
  vi.resetModules()
  return import('./useSession')
}

beforeEach(() => vi.clearAllMocks())

describe('useSession', () => {
  it('loads the session once and shares it', async () => {
    api.getSession.mockResolvedValue(ada)
    const { currentUser, loadSession, useSession } = await fresh()

    await Promise.all([loadSession(), loadSession()])
    await loadSession()

    expect(api.getSession).toHaveBeenCalledTimes(1)
    expect(currentUser()).toEqual(ada)
    expect(useSession().isSignedIn.value).toBe(true)
  })

  it('behaves as signed out when the server cannot be reached', async () => {
    api.getSession.mockRejectedValue(new Error('offline'))
    const { currentUser, loadSession, useSession } = await fresh()

    await expect(loadSession()).resolves.toBeUndefined()

    expect(currentUser()).toBeNull()
    expect(useSession().ready.value).toBe(true)
  })

  it('reloads the session after signing in', async () => {
    api.getSession.mockResolvedValueOnce(null).mockResolvedValueOnce(ada)
    const { currentUser, loadSession, useSession } = await fresh()
    await loadSession()

    await useSession().signIn('ada@example.com', 'secret-password')

    expect(api.signIn).toHaveBeenCalledWith('ada@example.com', 'secret-password')
    expect(currentUser()).toEqual(ada)
  })

  it('tells listeners when the user signs out or changes, not on a reload', async () => {
    const bob = { ...ada, id: '2', email: 'bob@example.com' }
    api.getSession.mockResolvedValueOnce(ada).mockResolvedValueOnce(ada).mockResolvedValue(bob)
    const { loadSession, onUserChange, useSession } = await fresh()
    const changed = vi.fn()
    onUserChange(changed)

    await loadSession()
    expect(changed).toHaveBeenCalledTimes(1) // nobody → Ada
    await loadSession(true)
    expect(changed).toHaveBeenCalledTimes(1) // still Ada
    await useSession().signOut()
    expect(changed).toHaveBeenCalledTimes(2)
    await loadSession(true)
    expect(changed).toHaveBeenCalledTimes(3) // Bob signed in elsewhere
  })

  it('forgets the user on sign-out', async () => {
    api.getSession.mockResolvedValue(ada)
    const { currentUser, loadSession, useSession } = await fresh()
    await loadSession()

    await useSession().signOut()

    expect(currentUser()).toBeNull()
    expect(useSession().isSignedIn.value).toBe(false)
  })

  it('keeps the user when the server rejects a sign-out', async () => {
    api.getSession.mockResolvedValue(ada)
    api.signOut.mockRejectedValue(new Error('offline'))
    const { currentUser, loadSession, useSession } = await fresh()
    await loadSession()

    await expect(useSession().signOut()).rejects.toThrow('offline')

    expect(currentUser()).toEqual(ada)
  })

  it('takes the updated profile from the server', async () => {
    api.getSession.mockResolvedValue(ada)
    api.updateMe.mockResolvedValue({ ...ada, display_name: 'Ada' })
    const { currentUser, loadSession, useSession } = await fresh()
    await loadSession()

    await useSession().updateDisplayName('Ada')

    expect(api.updateMe).toHaveBeenCalledWith({ display_name: 'Ada' })
    expect(currentUser()?.display_name).toBe('Ada')
  })
})
