/**
 * The (i) tooltip that carries a panel's explanation.
 *
 * One of v2's deliberate changes: explanations moved out of the page body
 * and into tooltips, so no table is wider than six columns and no panel
 * carries a paragraph nobody reads.
 *
 * ## Positioned against the viewport, not the parent
 *
 * The prototype learned this the hard way. An absolutely-positioned tooltip
 * is clipped by any ancestor that scrolls — the insight feed, a wide table —
 * so it is placed with `position: fixed` against measured coordinates, and
 * flipped when there is no room on that side.
 *
 * It is a `<button>` because it must be reachable by keyboard: the content
 * is an explanation, and an explanation only a mouse can reach is an
 * explanation half the readers never get.
 */

import { useCallback, useId, useLayoutEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'

const GAP = 8

export function Tooltip({ children, align = 'left' }: { children: ReactNode; align?: 'left' | 'right' }) {
  const id = useId()
  const [open, setOpen] = useState(false)
  const hostRef = useRef<HTMLSpanElement>(null)
  const tipRef = useRef<HTMLSpanElement>(null)

  const place = useCallback(() => {
    const host = hostRef.current
    const tip = tipRef.current
    if (!host || !tip) return

    const rect = host.getBoundingClientRect()
    const width = tip.offsetWidth
    const height = tip.offsetHeight

    let x = align === 'right' ? rect.right - width + GAP : rect.left - GAP
    // Flip rather than overflow. A tooltip half off-screen is unreadable in
    // exactly the case it was needed: a narrow window.
    if (x + width > window.innerWidth - GAP) x = rect.right - width + GAP
    x = Math.max(GAP, Math.min(x, window.innerWidth - width - GAP))

    let y = rect.bottom + GAP
    if (y + height > window.innerHeight - GAP) y = Math.max(GAP, rect.top - height - GAP)

    tip.style.left = `${String(x)}px`
    tip.style.top = `${String(y)}px`
  }, [align])

  useLayoutEffect(() => {
    if (!open) return
    place()
    // Keep it attached to its trigger while the page moves under it.
    window.addEventListener('scroll', place, true)
    window.addEventListener('resize', place)
    return () => {
      window.removeEventListener('scroll', place, true)
      window.removeEventListener('resize', place)
    }
  }, [open, place])

  return (
    <span
      className={`nv-info${align === 'right' ? ' nv-right' : ''}`}
      ref={hostRef}
      onMouseEnter={() => {
        setOpen(true)
      }}
      onMouseLeave={() => {
        setOpen(false)
      }}
    >
      <button
        type="button"
        aria-label="What this means"
        aria-describedby={id}
        aria-expanded={open}
        onFocus={() => {
          setOpen(true)
        }}
        onBlur={() => {
          setOpen(false)
        }}
        onClick={() => {
          setOpen((was) => !was)
        }}
      >
        i
      </button>
      <span role="tooltip" id={id} ref={tipRef} hidden={!open} className="nv-tip">
        {children}
      </span>
    </span>
  )
}
