import '@testing-library/jest-dom/vitest'

/**
 * jsdom implements `<dialog>` as an element but not its modal behaviour:
 * `showModal` and `close` are simply absent, so anything that opens a drawer
 * throws `is not a function` before a single assertion runs.
 *
 * This supplies the minimum the drawer depends on — the `open` attribute,
 * the `close` event, and Escape — rather than pulling in a full polyfill.
 * What it deliberately does not fake is focus trapping or the backdrop:
 * those come from the real browser, and a stub of them here would let a test
 * pass for behaviour nothing actually implements.
 */
function installDialogStub(): void {
  const proto = HTMLDialogElement.prototype as HTMLDialogElement & {
    showModal?: () => void
    close?: (returnValue?: string) => void
  }

  if (typeof proto.showModal !== 'function') {
    proto.showModal = function showModal(this: HTMLDialogElement) {
      this.setAttribute('open', '')
    }
  }

  if (typeof proto.close !== 'function') {
    proto.close = function close(this: HTMLDialogElement, returnValue?: string) {
      this.removeAttribute('open')
      if (returnValue !== undefined) this.returnValue = returnValue
      this.dispatchEvent(new Event('close'))
    }
  }
}

installDialogStub()

// Escape closes a real modal dialog. Without this a test cannot exercise the
// dismissal path that clears the drawer's frame stack.
document.addEventListener('keydown', (event) => {
  if (event.key !== 'Escape') return
  document.querySelectorAll('dialog[open]').forEach((dialog) => {
    ;(dialog as HTMLDialogElement).close()
  })
})
