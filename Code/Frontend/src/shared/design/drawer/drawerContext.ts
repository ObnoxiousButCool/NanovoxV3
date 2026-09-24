/**
 * The drawer's context and hook, separate from the provider component so
 * that module exports only a component and fast refresh keeps working.
 */

import { createContext, useContext } from 'react'
import type { ReactNode } from 'react'

import type { EpistemicKind } from '@/shared/design/primitives/epistemic'

export interface DrawerFrame {
  title: ReactNode
  body: ReactNode
  /** What kind of claim this frame's contents are. */
  chip?: EpistemicKind
}

export interface DrawerContextValue {
  frames: DrawerFrame[]
  /** Push a frame. Opening from inside a frame stacks rather than replaces. */
  open: (frame: DrawerFrame) => void
  /** Pop one frame, returning to the one it was opened from. */
  back: () => void
  /** Dismiss entirely, clearing the stack. */
  close: () => void
  depth: number
}

export const DrawerContext = createContext<DrawerContextValue | null>(null)

export function useDrawer(): DrawerContextValue {
  const value = useContext(DrawerContext)
  if (!value) {
    throw new Error('useDrawer must be used inside a DrawerProvider.')
  }
  return value
}
