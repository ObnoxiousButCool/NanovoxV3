/**
 * Opening a call, from anywhere.
 *
 * A call used to be the deepest frame of the evidence drawer: a dialog
 * holding four analysis panels and a whole transcript inside a 66vh scroll
 * box, reached by stacking two or three frames deep. It is the longest thing
 * in the product and the one a reader stays in longest, which is the worst
 * possible fit for a modal — no address to share, no browser Back, no
 * scrollback once it is dismissed, and a second scrollbar inside the page's
 * own.
 *
 * So a call is a **page** now, at `/calls/:reference`, and every place that
 * used to push a drawer frame navigates here instead. The drawer keeps the
 * job it is good at: the short list of calls behind a figure.
 *
 * ## Why the origin travels in history state
 *
 * The page offers Back, and Back has to mean "the screen you came from" —
 * the accounts screen you were reading, the calls table on page 3 of a
 * filtered result — not "/calls". `navigate(-1)` restores that exactly,
 * including scroll, but only if there is history to go back to. A reader who
 * opened a shared link has none, and a Back that silently leaves the
 * application is worse than no Back at all. The `from` marker records that
 * the navigation came from inside the app, and names where, so the button
 * can say so and can be left off entirely when it has nothing true to say.
 */

import { useCallback } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

import { useDrawer } from '@/shared/design/drawer'
import { NAV_ITEMS, OFF_RAIL_SCREENS } from '@/shared/design/navigation'

/** Where a call lives. One function, so no call site spells the path. */
export function callPath(reference: string): string {
  return `/calls/${encodeURIComponent(reference)}`
}

/** The screen a call was opened from, carried in history state. */
export interface CallOrigin {
  pathname: string
  search: string
}

/**
 * Reads the origin back off `location.state`.
 *
 * History state is whatever the previous page put there, and a reader can
 * arrive with a hand-edited one, so this validates rather than casts. An
 * unrecognisable state is treated as no origin — the same as a deep link.
 */
export function readCallOrigin(state: unknown): CallOrigin | null {
  if (typeof state !== 'object' || state === null) return null
  const from = (state as { from?: unknown }).from
  if (typeof from !== 'object' || from === null) return null
  const { pathname, search } = from as { pathname?: unknown; search?: unknown }
  if (typeof pathname !== 'string' || !pathname.startsWith('/')) return null
  return { pathname, search: typeof search === 'string' ? search : '' }
}

/**
 * What to call the screen a reader came from.
 *
 * The rail already names every screen as the question it answers, and those
 * are the words the reader clicked. Anything not in the rail — a call opened
 * from another call — gets no name rather than a guessed one.
 */
export function originLabel(origin: CallOrigin): string | null {
  const candidates = [...NAV_ITEMS, ...OFF_RAIL_SCREENS]
  const match = candidates.find(
    (item) => origin.pathname === item.to || origin.pathname.startsWith(`${item.to}/`),
  )
  return match?.label ?? null
}

/**
 * Navigate to a call, recording where from.
 *
 * Closes the drawer on the way. A figure's call list is a drawer frame, and
 * leaving it open behind the page it just navigated to would put a modal
 * over the call the reader asked for.
 */
export function useOpenCall(): (reference: string) => void {
  const navigate = useNavigate()
  const { pathname, search } = useLocation()
  const { close } = useDrawer()

  return useCallback(
    (reference: string) => {
      close()
      navigate(callPath(reference), { state: { from: { pathname, search } } })
    },
    [navigate, close, pathname, search],
  )
}
