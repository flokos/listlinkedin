import { describe, expect, it, vi } from 'vitest'

import { browser } from '../test/fakeBrowser'
import { copyBySelection, copyRequest, copyText } from './clipboard'

const LINK = 'https://lists.example.test/l/A'

/** jsdom has no execCommand: this one records the text that was there to copy. */
function fakeExecCommand(works: boolean) {
  const copied: string[] = []
  document.execCommand = vi.fn(() => {
    copied.push(document.querySelector('textarea')?.value ?? '')
    return works
  })
  return copied
}

describe('copyText in a page', () => {
  it('writes to the clipboard, without an offscreen document', async () => {
    const writeText = vi.fn(async () => {})
    vi.stubGlobal('navigator', { clipboard: { writeText } })

    await copyText(LINK)

    expect(writeText).toHaveBeenCalledWith(LINK)
    expect(browser().offscreen.createDocument).not.toHaveBeenCalled()
  })

  it('selects and copies when the clipboard refuses (a window without the focus)', async () => {
    vi.stubGlobal('navigator', {
      clipboard: { writeText: vi.fn(async () => Promise.reject(new Error('not focused'))) },
    })
    const copied = fakeExecCommand(true)

    await copyText(LINK)

    expect(copied).toEqual([LINK])
    expect(document.querySelector('textarea')).toBeNull() // nothing left behind
  })

  it('rejects when the browser allows neither', async () => {
    vi.stubGlobal('navigator', {
      clipboard: { writeText: vi.fn(async () => Promise.reject(new Error('not allowed'))) },
    })
    fakeExecCommand(false)
    await expect(copyText(LINK)).rejects.toThrow('not allowed')
  })
})

describe('copyBySelection', () => {
  it('reports a browser without the command as a failure, not an error', () => {
    // @ts-expect-error jsdom's document, as it comes
    delete document.execCommand
    expect(copyBySelection(LINK)).toBe(false)
  })
})

describe('copyRequest', () => {
  it('accepts only a request to copy a text', () => {
    expect(copyRequest({ type: 'offscreen:copy', text: LINK })).toEqual({
      type: 'offscreen:copy',
      text: LINK,
    })
    for (const other of [
      null,
      'offscreen:copy',
      { type: 'offscreen:copy' },
      { type: 'offscreen:copy', text: 7 },
      { type: 'connect:code', text: LINK },
    ])
      expect(copyRequest(other), JSON.stringify(other)).toBeNull()
  })
})
