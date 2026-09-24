/**
 * The stacked evidence drawer.
 *
 * "Every figure opens its evidence" is one of the plan's standing practices,
 * and evidence has evidence: a figure opens the calls behind it, a call
 * opens the rule it turned on. So the drawer is a **stack**, and Back
 * returns to the frame it came from rather than closing outright. Closing
 * from depth three and having to navigate back to where you were is how a
 * reader stops opening evidence at all.
 *
 * ## What the prototype had to do and this does not
 *
 * The prototype rebuilds the drawer's `innerHTML` per frame, so each frame
 * carries a `rewire` function to re-bind its own event handlers. React
 * re-renders instead, so frames are plain nodes and there is nothing to
 * rebind. The other half of its note still applies: `showModal()` throws if
 * the dialog is already open, so it is called only when closed.
 *
 * Escape closes the dialog natively. That has to clear the whole stack, or
 * the next open would resume mid-way down a stack the reader had dismissed.
 */

import { useCallback, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

import { DrawerContext } from '@/shared/design/drawer/drawerContext'
import type { DrawerFrame } from '@/shared/design/drawer/drawerContext'

export function DrawerProvider({ children }: { children: ReactNode }) {
  const [frames, setFrames] = useState<DrawerFrame[]>([])

  const open = useCallback((frame: DrawerFrame) => {
    setFrames((stack) => [...stack, frame])
  }, [])

  const back = useCallback(() => {
    setFrames((stack) => stack.slice(0, -1))
  }, [])

  const close = useCallback(() => {
    setFrames([])
  }, [])

  const value = useMemo(
    () => ({ frames, open, back, close, depth: frames.length }),
    [frames, open, back, close],
  )

  return <DrawerContext.Provider value={value}>{children}</DrawerContext.Provider>
}
