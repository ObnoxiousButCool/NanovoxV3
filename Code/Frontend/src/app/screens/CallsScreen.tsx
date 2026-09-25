/**
 * `/calls` — the workbench. Search, sort, page, select, download, open.
 *
 * ## Everything that is not a filter lives in the URL too
 *
 * Search, sort, order, page and page size go in the address beside the
 * filters, for the reason `useFilters` already gives: a link to "the
 * unresolved calls for this employer, sorted worst-quality first, page 3"
 * has to be a link. They are kept out of `useFilters` because they narrow
 * nothing on any other screen.
 *
 * **Selection deliberately does not.** A hundred call references in a query
 * string is a URL nobody can share, and a selection is a working state
 * rather than a view of the corpus. It lives in component state and is
 * announced as lost when the filters move — see `selected` below.
 *
 * ## Download is a link to the server, not a file built here
 *
 * Checkpoint **I2**: the 26-column projection is the server's. The buttons
 * hand the browser a URL with the current filters on it, so the file a
 * reader mails out is produced by the same code as the table they are
 * looking at, and a column can never appear in one and not the other.
 */

import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { useCalls } from '@/shared/api/insights'
import type { CallRow, CallsPage } from '@/shared/api/insights'
import { useDrawer } from '@/shared/design/drawer'
import { CallEvidence } from '@/shared/design/drawer/Evidence'
import { Empty, Note, Panel } from '@/shared/design/primitives'
import { getConfig } from '@/shared/config/env'
import { useFilters } from '@/shared/filters/useFilters'
import { Screen } from '@/shared/screens/Screen'

const PAGE_SIZES = [25, 50, 100]

/** The six sortable columns the API accepts, and their headings. */
const SORTABLE: { key: string; label: string }[] = [
  { key: 'date', label: 'Date' },
  { key: 'employer', label: 'Employer' },
  { key: 'agent', label: 'Agent' },
  { key: 'category', label: 'Topic' },
  { key: 'outcome', label: 'Outcome' },
  { key: 'quality', label: 'Quality' },
]

export function CallsScreen() {
  const filters = useFilters()
  const [params, setParams] = useSearchParams()
  const { open } = useDrawer()

  const q = params.get('q') ?? ''
  const sort = params.get('sort') ?? 'date'
  const order = params.get('order') ?? 'desc'
  const page = Number(params.get('page') ?? '1')
  const perPage = Number(params.get('perPage') ?? '25')

  const search = useMemo(() => {
    const next = new URLSearchParams(filters.apiSearch)
    if (q) next.set('q', q)
    next.set('sort', sort)
    next.set('order', order)
    next.set('page', String(page))
    next.set('perPage', String(perPage))
    return next
  }, [filters.apiSearch, q, sort, order, page, perPage])

  const { data, isPending, error } = useCalls(search.toString())

  const [selected, setSelected] = useState<Set<string>>(new Set())
  // A selection is a set of references, and the filters decide which
  // references exist. Keeping a selection across a filter change would let
  // "download selected" produce rows the reader can no longer see — so it
  // is dropped, and the panel says so rather than letting it vanish
  // silently.
  useEffect(() => {
    setSelected(new Set())
  }, [filters.apiSearch, q])

  const write = (key: string, value: string | null) => {
    setParams(
      (previous) => {
        const next = new URLSearchParams(previous)
        if (value === null || value === '') next.delete(key)
        else next.set(key, value)
        // Any change to the question resets to page 1. Staying on page 7
        // of a result that now has two pages shows an empty table, which
        // reads as "no matches" rather than "you are past the end".
        if (key !== 'page') next.delete('page')
        return next
      },
      { replace: false },
    )
  }

  const toggleSort = (key: string) => {
    // Same column flips the direction; a different column starts on the
    // direction that puts the interesting end first — most recent, worst
    // quality — rather than always ascending.
    const next = sort === key && order === 'desc' ? 'asc' : 'desc'
    setParams(
      (previous) => {
        const updated = new URLSearchParams(previous)
        updated.set('sort', key)
        updated.set('order', next)
        updated.delete('page')
        return updated
      },
      { replace: false },
    )
  }

  const downloadUrl = (refs: string[]) => {
    const next = new URLSearchParams(search)
    next.delete('page')
    next.delete('perPage')
    for (const ref of refs) next.append('ref', ref)
    // The same base the fetch client uses, so the download cannot end up
    // pointed at a different API than the table it belongs to.
    return `${getConfig().apiBaseUrl}/insights/calls.csv?${next.toString()}`
  }

  return (
    <Screen
      title="All calls"
      lede="Every call the filters admit, with the transcript behind each one."
      scope={data?.scope}
      isPending={isPending}
      error={error}
    >
      {data === undefined ? null : (
        <CallsBody
          data={data}
          q={q}
          sort={sort}
          order={order}
          page={page}
          perPage={perPage}
          selected={selected}
          onWrite={write}
          onSort={toggleSort}
          onSelect={setSelected}
          onOpen={(reference) => {
            open({
              title: `Call ${reference}`,
              chip: 'observed',
              body: <CallEvidence callId={reference} />,
            })
          }}
          downloadUrl={downloadUrl}
        />
      )}
    </Screen>
  )
}

function CallsBody({
  data,
  q,
  sort,
  order,
  page,
  perPage,
  selected,
  onWrite,
  onSort,
  onSelect,
  onOpen,
  downloadUrl,
}: {
  data: CallsPage
  q: string
  sort: string
  order: string
  page: number
  perPage: number
  selected: Set<string>
  onWrite: (key: string, value: string | null) => void
  onSort: (key: string) => void
  onSelect: (next: Set<string>) => void
  onOpen: (reference: string) => void
  downloadUrl: (refs: string[]) => string
}) {
  const rows = data.rows
  const onPage = rows.map((row) => row.reference)
  const allOnPageSelected = onPage.length > 0 && onPage.every((ref) => selected.has(ref))

  const toggleAllOnPage = () => {
    const next = new Set(selected)
    // Select-all applies to **this page**, not the whole result. A
    // checkbox that quietly selected 400 unseen rows would make "download
    // selected" mean something the reader never looked at.
    if (allOnPageSelected) for (const ref of onPage) next.delete(ref)
    else for (const ref of onPage) next.add(ref)
    onSelect(next)
  }

  return (
    <div className="nv-grid">
      <div className="nv-c12">
        <Panel
          title="Calls"
          sub={
            <>
              {data.total} of {data.considered} calls match. Page {data.page} of{' '}
              {data.pages}.
            </>
          }
          actions={
            <div className="nv-rowfilters">
              <label>
                <span>Search</span>
                <input
                  type="search"
                  value={q}
                  placeholder="Reference, employer, topic…"
                  onChange={(event) => {
                    onWrite('q', event.target.value || null)
                  }}
                />
              </label>
              <label>
                <span>Per page</span>
                <select
                  value={String(perPage)}
                  onChange={(event) => {
                    onWrite('perPage', event.target.value)
                  }}
                >
                  {PAGE_SIZES.map((size) => (
                    <option key={size} value={String(size)}>
                      {size}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          }
        >
          <div className="nv-fbtns nv-dlrow">
            <a className="nv-btn" href={downloadUrl([])} download>
              ⤓ Download {data.total} matching calls (CSV)
            </a>
            {selected.size > 0 ? (
              <a className="nv-btn" href={downloadUrl([...selected])} download>
                ⤓ Download {selected.size} selected
              </a>
            ) : null}
            <Note>
              The file is built by the server from the same query as this table, so a
              column can never appear in one and not the other. Selecting rows narrows it;
              it never adds a call the filters exclude.
            </Note>
          </div>

          {rows.length === 0 ? (
            <Empty title="No call matches">
              {data.considered === 0
                ? 'There is no measurable call in the corpus for this period.'
                : `All ${String(data.considered)} calls in scope were excluded by the filters or the search.`}
            </Empty>
          ) : (
            <table className="nv-risktable nv-callstable">
              <thead>
                <tr>
                  <th scope="col">
                    <input
                      type="checkbox"
                      aria-label="Select every call on this page"
                      checked={allOnPageSelected}
                      onChange={toggleAllOnPage}
                    />
                  </th>
                  <th scope="col">Call</th>
                  {SORTABLE.map((column) => (
                    <th key={column.key} scope="col" aria-sort={ariaSort(column.key, sort, order)}>
                      <button type="button" className="nv-sortbtn" onClick={() => { onSort(column.key) }}>
                        {column.label}
                        <span aria-hidden="true">
                          {sort === column.key ? (order === 'desc' ? ' ▾' : ' ▴') : ''}
                        </span>
                      </button>
                    </th>
                  ))}
                  <th scope="col">Flags</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <Row
                    key={row.reference}
                    row={row}
                    checked={selected.has(row.reference)}
                    onToggle={() => {
                      const next = new Set(selected)
                      if (next.has(row.reference)) next.delete(row.reference)
                      else next.add(row.reference)
                      onSelect(next)
                    }}
                    onOpen={() => { onOpen(row.reference) }}
                  />
                ))}
              </tbody>
            </table>
          )}

          <div className="nv-fbtns nv-pager">
            <button
              type="button"
              className="nv-btn"
              disabled={page <= 1}
              onClick={() => { onWrite('page', String(page - 1)) }}
            >
              ← Previous
            </button>
            <span className="nv-indcount">
              Page {data.page} of {data.pages}
            </span>
            <button
              type="button"
              className="nv-btn"
              disabled={page >= data.pages}
              onClick={() => { onWrite('page', String(page + 1)) }}
            >
              Next →
            </button>
          </div>
        </Panel>
      </div>

      {(data.omittedColumns ?? []).length > 0 ? (
        <div className="nv-c12">
          <Panel title="What the export does not carry">
            {/* Said where the export is offered, not only in a docstring.
                A column absent from a file is a question somebody will
                otherwise ask by email. */}
            <ul className="nv-emerging">
              {(data.omittedColumns ?? []).map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          </Panel>
        </div>
      ) : null}
    </div>
  )
}

function Row({
  row,
  checked,
  onToggle,
  onOpen,
}: {
  row: CallRow
  checked: boolean
  onToggle: () => void
  onOpen: () => void
}) {
  return (
    <tr>
      <td>
        <input
          type="checkbox"
          aria-label={`Select call ${row.reference}`}
          checked={checked}
          onChange={onToggle}
        />
      </td>
      <th scope="row">
        <button type="button" className="nv-linkbtn" onClick={onOpen}>
          {row.reference}
        </button>
      </th>
      <td className="nv-indcount">{row.occurredOn}</td>
      <td>{row.employerName ?? row.employerRef ?? '—'}</td>
      <td className="nv-indcount">{row.agentRef ?? '—'}</td>
      <td>{row.category ?? '—'}</td>
      <td>{row.outcome ?? '—'}</td>
      <td className="nv-indcount">
        {/* Null is not zero. A call with no score recorded is not a call
            that scored nothing. */}
        {row.qualityScore ?? 'Not recorded'}
      </td>
      <td>
        <div className="nv-fires">
          {row.complaint ? <span className="nv-fire">Complaint</span> : null}
          {row.escalationTriggered && !row.escalationHandled ? (
            <span className="nv-fire">Escalation missed</span>
          ) : null}
          {row.knowledgeFailure ? <span className="nv-fire">Knowledge failure</span> : null}
          {(row.controlExceptions ?? []).length > 0 ? (
            <span className="nv-fire">Control exception</span>
          ) : null}
        </div>
      </td>
    </tr>
  )
}

function ariaSort(
  key: string,
  sort: string,
  order: string,
): 'ascending' | 'descending' | 'none' {
  if (sort !== key) return 'none'
  return order === 'desc' ? 'descending' : 'ascending'
}
