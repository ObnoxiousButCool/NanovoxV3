/**
 * Region × category, so a reader can tell book-wide from local.
 *
 * The prototype states the reading rule and it is the point of the chart: a
 * column dark across every row is a book-wide topic, which points at a
 * process; one dark cell is local, which points at an account or a broker.
 *
 * ## Zero is a dot, not a pale cell
 *
 * A cell with no calls gets the surface colour and a `·`, not the lightest
 * step of the scale. On a sequential scale the lightest step and "nothing
 * here" look identical, and the difference is the whole question.
 *
 * ## Contrast is CSS, not a computed colour
 *
 * The prototype computes a readable ink colour per cell in JavaScript and
 * caches it by token name, which then has to be invalidated on every theme
 * switch or the cells keep the other theme's text colour and fail contrast
 * outright. Here each step is a class with its background and its text
 * colour declared together, for both themes, so there is no cache and
 * nothing to invalidate.
 */

const COLUMN_WIDTH = 84
const ROW_HEIGHT = 32
const LABEL_WIDTH = 130

export interface HeatmapCell {
  row: string
  column: string
  value: number
}

/** Which of the three steps a value falls in, or `null` for none at all. */
function step(value: number, max: number): 1 | 2 | 3 | null {
  if (value === 0) return null
  const share = max > 0 ? value / max : 0
  if (share > 0.66) return 3
  if (share > 0.33) return 2
  return 1
}

export function Heatmap({
  rows,
  columns,
  cells,
  ariaLabel,
}: {
  rows: string[]
  columns: string[]
  cells: HeatmapCell[]
  ariaLabel: string
}) {
  const lookup = new Map(cells.map((cell) => [`${cell.row}|${cell.column}`, cell.value]))
  const max = Math.max(...cells.map((cell) => cell.value), 0)

  const width = LABEL_WIDTH + columns.length * COLUMN_WIDTH + 8
  const height = rows.length * ROW_HEIGHT + 44

  return (
    <div className="nv-heatmap">
      <svg viewBox={`0 0 ${String(width)} ${String(height)}`} role="img" aria-label={ariaLabel}>
        {columns.map((column, i) => {
          const [first, ...rest] = column.split(' ')
          const x = LABEL_WIDTH + i * COLUMN_WIDTH + COLUMN_WIDTH / 2
          return (
            <g key={column}>
              <text x={x} y={13} textAnchor="middle" fontSize={12} fill="var(--ink-2)">
                {first}
              </text>
              <text x={x} y={27} textAnchor="middle" fontSize={12} fill="var(--ink-2)">
                {rest.join(' ')}
              </text>
            </g>
          )
        })}

        {rows.map((row, ri) => (
          <g key={row}>
            <text x={0} y={36 + ri * ROW_HEIGHT + ROW_HEIGHT / 2 + 4} fontSize={13} fill="var(--ink-2)">
              {row}
            </text>
            {columns.map((column, ci) => {
              const value = lookup.get(`${row}|${column}`) ?? 0
              const level = step(value, max)
              return (
                <g key={column}>
                  <rect
                    x={LABEL_WIDTH + ci * COLUMN_WIDTH + 1}
                    y={36 + ri * ROW_HEIGHT + 1}
                    width={COLUMN_WIDTH - 3}
                    height={ROW_HEIGHT - 3}
                    rx={3}
                    className={level ? `nv-heat-${String(level)}` : 'nv-heat-none'}
                  />
                  <text
                    x={LABEL_WIDTH + ci * COLUMN_WIDTH + COLUMN_WIDTH / 2}
                    y={36 + ri * ROW_HEIGHT + ROW_HEIGHT / 2 + 4}
                    textAnchor="middle"
                    fontSize={13}
                    className={level ? `nv-heat-ink-${String(level)}` : 'nv-heat-ink-none'}
                  >
                    {value === 0 ? '·' : value}
                  </text>
                </g>
              )
            })}
          </g>
        ))}
      </svg>
      <div className="nv-legend">
        <span>
          <i className="nv-heat-swatch nv-heat-1" />
          fewer
        </span>
        <span>
          <i className="nv-heat-swatch nv-heat-3" />
          more calls
        </span>
        <span>
          <i className="nv-heat-swatch nv-heat-none" />
          none
        </span>
      </div>
    </div>
  )
}
