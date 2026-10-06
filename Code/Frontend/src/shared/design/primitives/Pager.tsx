/**
 * A numbered pager: Previous, the page numbers, Next.
 *
 * Long ranges collapse around the current page rather than listing every
 * page — a reader on page 13 of 40 needs page 1, the pages next to where
 * they are, and the last page, not the 36 in between.
 */

export function Pager({
  page,
  pageCount,
  onChange,
}: {
  /** 1-indexed, like every other page number this app shows. */
  page: number
  pageCount: number
  onChange: (page: number) => void
}) {
  if (pageCount <= 1) return null

  return (
    <nav className="nv-pagenav" aria-label="Pagination">
      <button
        type="button"
        className="nv-btn"
        disabled={page <= 1}
        onClick={() => {
          onChange(page - 1)
        }}
      >
        ← Previous
      </button>
      <div className="nv-pagenums">
        {pageNumbers(page, pageCount).map((entry) =>
          typeof entry === 'number' ? (
            <button
              key={entry}
              type="button"
              className="nv-pagebtn"
              aria-current={entry === page ? 'page' : undefined}
              onClick={() => {
                onChange(entry)
              }}
            >
              {entry}
            </button>
          ) : (
            // Keyed by the page before it: at most one gap can follow any
            // given page, so the pairing is already unique.
            <span key={`gap-after-${String(entry.after)}`} className="nv-pagegap" aria-hidden="true">
              …
            </span>
          ),
        )}
      </div>
      <button
        type="button"
        className="nv-btn"
        disabled={page >= pageCount}
        onClick={() => {
          onChange(page + 1)
        }}
      >
        Next →
      </button>
    </nav>
  )
}

/** Page 1, the last page, and one either side of the current page — the
 * rest collapsed into a single gap, never more than one in a row. */
function pageNumbers(page: number, pageCount: number): (number | { after: number })[] {
  const keep = new Set<number>([1, pageCount, page, page - 1, page + 1])
  const sorted = [...keep].filter((value) => value >= 1 && value <= pageCount).sort((a, b) => a - b)

  const result: (number | { after: number })[] = []
  let previous: number | null = null
  for (const value of sorted) {
    if (previous !== null && value - previous > 1) result.push({ after: previous })
    result.push(value)
    previous = value
  }
  return result
}
