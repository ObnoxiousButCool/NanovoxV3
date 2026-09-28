/**
 * The single-frame dialog behind the card modal and the composer.
 *
 * `Drawer` is a stack, because evidence opens evidence. Neither of these
 * needs that: only one of {card, composer, closed} is ever open at a time,
 * so this is `Drawer`'s accessibility handling — a real `<dialog>`,
 * `showModal()` called only when closed, Escape and a backdrop click both
 * routed through `onClose` — without the frame stack that would be dead
 * weight here.
 */

import { useEffect, useRef } from 'react'
import type { ReactNode } from 'react'

export function ActionDialog({
  open,
  onClose,
  children,
}: {
  open: boolean
  onClose: () => void
  children: ReactNode
}) {
  const ref = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    // showModal() throws if the dialog is already open, so call it only on
    // the closed -> open edge, the same note Drawer carries.
    if (open && !dialog.open) dialog.showModal()
    if (!open && dialog.open) dialog.close()
  }, [open])

  return (
    <dialog
      className="nv-actdialog"
      ref={ref}
      onClose={onClose}
      onClick={(event) => {
        // A click on the dialog element itself is the backdrop; a click on
        // its contents bubbles from a child.
        if (event.target === ref.current) onClose()
      }}
    >
      {open ? children : null}
    </dialog>
  )
}
