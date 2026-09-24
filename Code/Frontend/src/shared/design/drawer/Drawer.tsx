/**
 * Renders the top frame of the drawer stack.
 *
 * A real `<dialog>`, so the browser handles the modal backdrop, focus
 * trapping and Escape rather than this file reimplementing three things it
 * would get subtly wrong.
 */

import { useEffect, useRef } from 'react'

import { EpistemicChip } from '@/shared/design/primitives'
import { useDrawer } from '@/shared/design/drawer/drawerContext'

export function Drawer() {
  const { frames, back, close, depth } = useDrawer()
  const ref = useRef<HTMLDialogElement>(null)
  const frame = frames.at(-1)

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return

    // showModal() throws if the dialog is already open, so it is called only
    // when closed — the prototype's own hard-won note.
    if (depth > 0 && !dialog.open) dialog.showModal()
    if (depth === 0 && dialog.open) dialog.close()
  }, [depth])

  return (
    <dialog
      className="nv-drawer"
      ref={ref}
      aria-label="Evidence"
      onClose={() => {
        // Escape and the backdrop both fire this. Clearing the stack matters:
        // otherwise the next open resumes halfway down a stack the reader
        // already dismissed.
        if (depth > 0) close()
      }}
      onClick={(event) => {
        // A click on the dialog element itself is the backdrop; a click on
        // its contents bubbles from a child.
        if (event.target === ref.current) close()
      }}
    >
      {frame ? (
        <>
          <div className="nv-dh">
            <h3>{frame.title}</h3>
            <div className="nv-dh-actions">
              {frame.chip ? <EpistemicChip kind={frame.chip} /> : null}
              {depth > 1 ? (
                <button type="button" className="nv-btn" onClick={back}>
                  ← Back
                </button>
              ) : null}
              <button type="button" className="nv-btn" onClick={close}>
                Close
              </button>
            </div>
          </div>
          <div className="nv-db">{frame.body}</div>
        </>
      ) : null}
    </dialog>
  )
}
