// @vitest-environment node
// Without a document, as in Chrome's service worker: an offscreen document copies.
import { describe, expect, it } from 'vitest'

import { browser } from '../test/fakeBrowser'
import { copyText } from './clipboard'

const LINK = 'https://lists.example.test/l/A'

describe('copyText in a service worker', () => {
  it('opens an offscreen document, asks it to copy, and closes it', async () => {
    browser().runtime.sendMessage.mockResolvedValue({ ok: true })

    await copyText(LINK)

    expect(browser().offscreen.createDocument).toHaveBeenCalledWith(
      expect.objectContaining({ url: 'offscreen.html', reasons: ['CLIPBOARD'] }),
    )
    expect(browser().runtime.sendMessage).toHaveBeenCalledWith({
      type: 'offscreen:copy',
      text: LINK,
    })
    expect(browser().offscreen.closeDocument).toHaveBeenCalledOnce()
  })

  it('uses the document that is already open', async () => {
    browser().offscreen.hasDocument.mockResolvedValue(true)
    browser().runtime.sendMessage.mockResolvedValue({ ok: true })
    await copyText(LINK)
    expect(browser().offscreen.createDocument).not.toHaveBeenCalled()
  })

  it('rejects when the document could not copy, and still closes it', async () => {
    browser().runtime.sendMessage.mockResolvedValue({ ok: false })
    await expect(copyText(LINK)).rejects.toThrow('refused')
    expect(browser().offscreen.closeDocument).toHaveBeenCalledOnce()
  })
})
