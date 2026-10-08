/**
 * The shape of a screen before its figures arrive.
 *
 * ## Why a skeleton rather than "Loading…"
 *
 * `/insights/risk` takes about three and a half seconds cold, and `/exec` is
 * three queries wide. For that whole period the body was the word "Loading…"
 * on an otherwise empty page, so a reader had no idea whether they were
 * waiting for one number or a screenful, and the layout jumped under them when
 * it arrived. Drawing the layout first removes both: the page stops reflowing,
 * and the wait reads as a page arriving rather than as nothing happening.
 *
 * ## It draws boxes, never numbers
 *
 * Nothing here renders a plausible-looking figure, not even a greyed one. A
 * skeleton that shows "0" or "—" where a figure will be is a screen making a
 * claim it has not read yet, which is the same failure the withheld panels
 * exist to prevent — and the one place a reader is least able to check it.
 *
 * ## Announced once, not per box
 *
 * The container carries `aria-busy` and a single visually-hidden "Loading"
 * label. The boxes themselves are `aria-hidden`: a screen reader announcing
 * fourteen empty regions is worse than silence, and the one message is what a
 * reader needs.
 */

export function SkeletonBlock({
  lines = 3,
  className,
}: {
  /** Rows of grey inside the block. Roughly the content it stands in for. */
  lines?: number
  className?: string
}) {
  return (
    <div className={`nv-skel-block${className ? ` ${className}` : ''}`} aria-hidden="true">
      <div className="nv-skel-title" />
      {Array.from({ length: lines }, (_, i) => (
        // `nv-skel-line-last` is narrower, so a block reads as a paragraph
        // rather than as a solid rectangle.
        <div key={i} className={`nv-skel-line${i === lines - 1 ? ' nv-skel-line-last' : ''}`} />
      ))}
    </div>
  )
}

export function SkeletonTiles({ count = 4 }: { count?: number }) {
  return (
    <div className="nv-skel-tiles" aria-hidden="true">
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="nv-skel-tile">
          <div className="nv-skel-tile-label" />
          <div className="nv-skel-tile-figure" />
        </div>
      ))}
    </div>
  )
}

/** Wraps a screen's skeleton, and is the only thing that speaks. */
export function Skeleton({ children }: { children: React.ReactNode }) {
  return (
    <div className="nv-skel" aria-busy="true" aria-live="polite">
      <span className="nv-visually-hidden">Loading this screen</span>
      {children}
    </div>
  )
}
