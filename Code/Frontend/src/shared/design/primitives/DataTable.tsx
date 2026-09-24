/**
 * A table, with v2's six-column rule enforced rather than remembered.
 *
 * ## Why the limit is a thrown error and not a lint rule
 *
 * "No table is wider than six columns" is one of v2's stated changes, and
 * the pressure on it is constant — every screen has a seventh column that
 * feels essential. A convention loses that argument quietly, one table at a
 * time. Failing the render loses it loudly, in a test, before review.
 *
 * The seventh column is almost always an explanation, and explanations now
 * live in the (i) tooltip. That is the same change, seen from the other end.
 *
 * Rows carry `href` rather than an onClick so that a row is a real link: it
 * can be opened in a new tab, it is reachable by keyboard without extra
 * work, and screen readers announce it as navigation.
 */

import { useNavigate } from 'react-router-dom'
import type { ReactNode } from 'react'

export const MAX_COLUMNS = 6

export interface Column {
  key: string
  header: ReactNode
  /** Right-aligns and tabular-numbers the cell. */
  numeric?: boolean
}

export interface Row {
  key: string
  cells: ReactNode[]
  /** Makes the whole row navigate. Links inside the row still win. */
  href?: string
}

export function DataTable({
  columns,
  rows,
  empty,
  caption,
}: {
  columns: Column[]
  rows: Row[]
  empty?: ReactNode
  caption?: string
}) {
  const navigate = useNavigate()

  if (columns.length > MAX_COLUMNS) {
    throw new Error(
      `A table may show at most ${String(MAX_COLUMNS)} columns; this one has ${String(columns.length)}. ` +
        'Move the extra column into the panel’s (i) tooltip, or split the table.',
    )
  }

  if (rows.length === 0) return <>{empty}</>

  return (
    <div className="nv-tblwrap">
      <table>
        {caption ? <caption className="nv-visually-hidden">{caption}</caption> : null}
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key} className={column.numeric ? 'nv-num' : undefined} scope="col">
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.key}
              className={row.href ? 'nv-clickable' : undefined}
              tabIndex={row.href ? 0 : undefined}
              onClick={
                row.href
                  ? (event) => {
                      if ((event.target as HTMLElement).closest('a, button')) return
                      navigate(row.href as string)
                    }
                  : undefined
              }
              onKeyDown={
                row.href
                  ? (event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault()
                        navigate(row.href as string)
                      }
                    }
                  : undefined
              }
            >
              {row.cells.map((cell, index) => (
                <td
                  key={columns[index]?.key ?? index}
                  className={columns[index]?.numeric ? 'nv-num' : undefined}
                >
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
