/**
 * The frame every insights screen renders into.
 *
 * Four screens showing the same four states four slightly different ways is
 * four chances for one of them to render an empty result as a clean bill of
 * health. The states live here once.
 *
 * ## The four states, and why "empty" is not one of them
 *
 * **Loading**, **error** and **loaded** are here. *Empty* deliberately is
 * not: what "nothing to show" means is different on every screen — no
 * assessable accounts is not no flagged accounts is not no calls in the
 * period — and a shared empty state would have to say something vague
 * enough to be true of all three. Each screen says its own, inside its own
 * panels, where it can be specific.
 *
 * ## The scope line sits above the content, always
 *
 * `Documents/notes/plan.md` §9: filters slice, never hide. The count of what survived the
 * filters is part of the frame rather than a panel a screen might forget,
 * and the server's own `caveats` are rendered verbatim beneath it — they
 * are computed from the numbers, and a screen that dropped them would be
 * publishing a figure without the sentence that qualifies it.
 */

import { useEffect, useState, type ReactNode } from 'react'

import { FilterBar } from '@/shared/filters/FilterBar'
import { Note } from '@/shared/design/primitives'
import type { Scope } from '@/shared/design/primitives'
import '@/shared/screens/screen.css'

export function Screen({
  title,
  scope,
  isPending,
  error,
  compactFilters = false,
  stickyHead = false,
  skeleton,
  children,
}: {
  title: string
  /** `filterBar({ compact: true })` in the prototype. See `FilterBar`. */
  compactFilters?: boolean
  /** Prototype-style sticky, collapsing page head, enabled only by Exec. */
  stickyHead?: boolean
  /** Undefined until the first response lands. */
  scope?: Scope | undefined
  isPending: boolean
  error: unknown
  /**
   * What to draw while `isPending`, instead of the word "Loading…".
   *
   * Opt-in per screen rather than a shared default, because a useful skeleton
   * is the shape of *that* page: a generic one is a grey rectangle that
   * rearranges itself when the data lands, which is the reflow this exists to
   * prevent. Screens that have not got one keep the text, which is honest
   * about saying nothing rather than guessing at a layout.
   */
  skeleton?: ReactNode
  children: ReactNode
}) {
  const [headStuck, setHeadStuck] = useState(false)

  useEffect(() => {
    if (!stickyHead) return
    let stuck = false
    const update = () => {
      const next = stuck
        ? window.scrollY > 40
        : window.scrollY > 180 &&
          document.documentElement.scrollHeight - window.innerHeight > 420
      if (next !== stuck) {
        stuck = next
        setHeadStuck(next)
      }
    }
    update()
    window.addEventListener('scroll', update, { passive: true })
    window.addEventListener('resize', update)
    return () => {
      window.removeEventListener('scroll', update)
      window.removeEventListener('resize', update)
    }
  }, [stickyHead])

  const pageHead = (
    <>
      {/* Title only. The prototype's `.q` paragraph under each heading --
          "This page shows every risk indicator across accounts…" and its
          equivalents -- was carried across and has been dropped on request.
          The headings are already written as the question the page answers,
          and the panels say what they are, so the paragraph repeated both
          and pushed the figures down the screen. */}
      <header className="nv-pagehead">
        <h1>{title}</h1>
      </header>

      {scope === undefined ? (
        <FilterBar compact={compactFilters} />
      ) : (
        <FilterBar callsInScope={scope.matched} compact={compactFilters} />
      )}
    </>
  )

  return (
    <div className={`nv-screen${stickyHead ? ' nv-screen-has-stickyhead' : ''}`}>
      {stickyHead ? (
        <div className={`nv-stickyhead${headStuck ? ' nv-stuck' : ''}`}>{pageHead}</div>
      ) : pageHead}

      {(scope?.caveats ?? []).map((caveat) => (
        // Verbatim, and every one of them. These are generated from the
        // numbers (§9), so paraphrasing or truncating to the first would
        // drop a qualification a reader is entitled to.
        <Note key={caveat}>{caveat}</Note>
      ))}

      {error !== null && error !== undefined ? (
        <div className="nv-screenstate" role="alert">
          <b>This screen could not be loaded.</b>
          <p>
            {/* The message, not a friendly substitute. A reader who can see
                "404" or "no such column" can act on it or forward it; "something
                went wrong" is unactionable by everyone.

                A non-Error rejection is reported as its type rather than
                stringified: `String(someObject)` is "[object Object]", which
                tells a reader strictly less than saying an object was thrown. */}
            {error instanceof Error ? error.message : `Unexpected ${typeof error} thrown.`}
          </p>
        </div>
      ) : isPending ? (
        // The skeleton speaks for itself — it carries its own `aria-busy` and
        // a single polite label — so it is not wrapped in the text state's
        // live region, which would announce the wait twice.
        (skeleton ?? (
          <div className="nv-screenstate" aria-live="polite">
            Loading…
          </div>
        ))
      ) : (
        children
      )}
    </div>
  )
}
