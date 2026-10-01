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
 * Checkpoint **I2**: the column projection is the server's. The buttons
 * hand the browser a URL with the current filters on it, so the file a
 * reader mails out is produced by the same code as the table they are
 * looking at, and a column can never appear in one and not the other.
 *
 * The prototype's export has 26 columns and this one has 24. The five it
 * does not carry are listed under the download button from `omittedColumns`
 * rather than described here, because the person who needs to know is the
 * one about to open the file in Excel and wonder where a column went.
 * Rendered from the response, so a column that gains a source stops being
 * mentioned without this screen being touched.
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { useCalls, useFilterOptions } from '@/shared/api/insights'
import type { CallRow, CallsPage } from '@/shared/api/insights'
import { useDrawer } from '@/shared/design/drawer'
import { CallEvidence } from '@/shared/design/drawer/Evidence'
import { BigRow, Empty, KpiTile, Named, Note } from '@/shared/design/primitives'
import { OUTCOME_COLOR } from '@/shared/design/outcome'
import { getConfig } from '@/shared/config/env'
import { useFilters } from '@/shared/filters/useFilters'
import { Screen } from '@/shared/screens/Screen'
import './calls.css'

const PAGE_SIZES = [25, 50, 100]

/** Sort fields available from the Calls list endpoint. */
const SORTABLE: { key: string; label: string }[] = [
  { key: 'date', label: 'Call' },
  { key: 'employer', label: 'Account' },
  { key: 'agent', label: 'Caller' },
  { key: 'category', label: 'Topic' },
]

export function CallsScreen() {
  const filters = useFilters()
  const { data: filterOptions } = useFilterOptions(filters.apiSearch)
  const signalLabels = useMemo(
    () => new Map((filterOptions?.signals ?? []).map(({ code, label }) => [code, label])),
    [filterOptions?.signals],
  )
  // Severity is fixed per signal type by the Signal Taxonomy sheet, never
  // decided per call — the same source `/insights/calls/:id`'s evidence
  // panel reads for this signal, looked up here rather than carried on
  // every row.
  const signalSeverity = useMemo(
    () => new Map((filterOptions?.signals ?? []).map(({ code, severity }) => [code, severity.code])),
    [filterOptions?.signals],
  )
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

  // `write` below already drops `page` when one of this screen's own
  // controls changes. The shared filter bar (region, broker, employer,
  // period, Advanced) writes through `useFilters` instead, which knows
  // nothing about this screen's `page` — so narrowing the filters while
  // deep in a result could strand a reader on a page past the new, smaller
  // end, rendering as "No call matches" (write's own comment, for the
  // controls it covers). The `useRef` guard skips the very first render, so
  // a shared link to page 3 of an already-filtered view still opens there.
  const lastFilters = useRef(filters.apiSearch)
  useEffect(() => {
    if (lastFilters.current === filters.apiSearch) return
    lastFilters.current = filters.apiSearch
    setParams(
      (previous) => {
        if (!previous.has('page')) return previous
        const next = new URLSearchParams(previous)
        next.delete('page')
        return next
      },
      { replace: true },
    )
  }, [filters.apiSearch, setParams])

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
    <div className="nv-calls">
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
            signalLabels={signalLabels}
            signalSeverity={signalSeverity}
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
    </div>
  )
}

function CallsBody({
  data,
  signalLabels,
  signalSeverity,
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
  signalLabels: Map<string, string>
  signalSeverity: Map<string, string>
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
  // Optional on the wire, because a response that carried every prototype
  // column would send nothing here rather than an empty list.
  const omitted = data.omittedColumns ?? []
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

  const firstRow = data.total === 0 ? 0 : (data.page - 1) * data.perPage + 1
  const lastRow = firstRow + rows.length - 1

  return (
    <div className="nv-grid">
      <div className="nv-c12">
        <CallsTilesPanel data={data} />
      </div>

      <div className="nv-c12">
        <section className="nv-panel nv-calls-panel" aria-label="Calls">
          <div className="nv-calls-toolbar">
            <div className="nv-calls-query">
              <label className="nv-calls-search">
                <span className="nv-sr-only">Search calls</span>
                <input
                  type="search"
                  value={q}
                  placeholder="Search call, account, caller, agent, broker"
                  onChange={(event) => {
                    onWrite('q', event.target.value || null)
                  }}
                />
              </label>
              <span className="nv-calls-count">
                {rows.length === 0
                  ? 'No calls match'
                  : `Showing ${String(firstRow)}–${String(lastRow)} of ${String(data.total)} matching calls`}
              </span>
            </div>
            <div className="nv-fbtns nv-calls-downloads">
              <a className="nv-btn nv-btn-primary" href={downloadUrl([])} download>
                ⤓ Download {data.total} matching calls (CSV)
              </a>
              {selected.size > 0 ? (
                <a className="nv-btn" href={downloadUrl([...selected])} download>
                  ⤓ Download {selected.size} selected
                </a>
              ) : null}
            </div>
          </div>
          <Note>
              The file is built by the server from the same query as this table, so a
              column can never appear in one and not the other. Selecting rows narrows it;
              it never adds a call the filters exclude.
          </Note>
          {omitted.length > 0 ? (
            <>
              <Note suppressed>
                The prototype&rsquo;s export has {omitted.length} columns this one does not.
                They are left out rather than written empty: a blank cell reads as
                &ldquo;no value for this call&rdquo;, which would not be true of any of them.
              </Note>
              <ul className="nv-omitted">
                {omitted.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            </>
          ) : null}

          {rows.length === 0 ? (
            <Empty title="No call matches">
              {data.considered === 0
                ? 'There is no measurable call in the corpus for this period.'
                : `All ${String(data.considered)} calls in scope were excluded by the filters or the search.`}
            </Empty>
          ) : (
            <div className="nv-tblwrap">
              <table className="nv-risktable nv-callstable">
                <thead>
                  <tr>
                    <th scope="col" className="nv-call-check">
                      <input
                        type="checkbox"
                        aria-label="Select every call on this page"
                        checked={allOnPageSelected}
                        onChange={toggleAllOnPage}
                      />
                    </th>
                    {SORTABLE.map((column) => (
                      <th key={column.key} scope="col" aria-sort={ariaSort(column.key, sort, order)}>
                        <button
                          type="button"
                          className="nv-sortbtn"
                          title={column.key === 'agent' ? 'Sorts by agent reference' : undefined}
                          onClick={() => { onSort(column.key) }}
                        >
                          {column.label}
                          <span aria-hidden="true">
                            {sort === column.key ? (order === 'desc' ? ' ▾' : ' ▴') : ''}
                          </span>
                        </button>
                      </th>
                    ))}
                    <th
                      scope="col"
                      aria-sort={sort === 'outcome' || sort === 'quality' ? ariaSort(sort, sort, order) : 'none'}
                    >
                      <div className="nv-call-outcome-heading">
                        <button type="button" className="nv-sortbtn" onClick={() => { onSort('outcome') }}>
                          Outcome{sort === 'outcome' ? (order === 'desc' ? ' ▾' : ' ▴') : ''}
                        </button>
                        <button
                          type="button"
                          className="nv-sortbtn nv-call-quality-sort"
                          aria-label="Sort by quality"
                          onClick={() => { onSort('quality') }}
                        >
                          quality{sort === 'quality' ? (order === 'desc' ? ' ▾' : ' ▴') : ' ↕'}
                        </button>
                      </div>
                    </th>
                    <th scope="col">Signals</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <Row
                      key={row.reference}
                      row={row}
                      signalLabels={signalLabels}
                      signalSeverity={signalSeverity}
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
            </div>
          )}

          <div className="nv-calls-pager">
            <label className="nv-calls-perpage">
              <span>Rows per page</span>
              <select
                value={String(perPage)}
                onChange={(event) => { onWrite('perPage', event.target.value) }}
              >
                {PAGE_SIZES.map((size) => (
                  <option key={size} value={String(size)}>{size}</option>
                ))}
              </select>
            </label>
            <div className="nv-calls-page-nav">
              <button
                type="button"
                className="nv-btn"
                disabled={page <= 1}
                onClick={() => { onWrite('page', String(page - 1)) }}
              >
                ← Previous
              </button>
              <span className="nv-indcount">Page {data.page} of {data.pages}</span>
              <button
                type="button"
                className="nv-btn"
                disabled={page >= data.pages}
                onClick={() => { onWrite('page', String(page + 1)) }}
              >
                Next →
              </button>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}

/**
 * The prototype's bare four-tile strip, above the toolbar. Over every call
 * the filters and search admit — `data.total` and the three aggregates
 * below it — never only the page on screen, so narrowing the page size
 * cannot make "unresolved" look like it dropped.
 */
function CallsTilesPanel({ data }: { data: CallsPage }) {
  return (
      <BigRow>
        <KpiTile label="Calls in view" value={String(data.total)} meta={`of ${String(data.considered)} calls in corpus`} />
        <KpiTile
          label="Unresolved"
          value={String(data.unresolvedCount)}
          meta="across all matches"
          tone={data.unresolvedCount > 0 ? 'warm' : 'plain'}
        />
        <KpiTile
          label="Escalations missed"
          value={String(data.escalationsMissedCount)}
          meta="warranted, not handled"
          tone={data.escalationsMissedCount > 0 ? 'hot' : 'plain'}
        />
        <KpiTile
          label="Average quality"
          value={
            data.averageQuality === null || data.averageQuality === undefined
              ? 'Not recorded'
              : String(Math.round(data.averageQuality))
          }
          meta="recorded scores only"
        />
      </BigRow>
  )
}

function Row({
  row,
  signalLabels,
  signalSeverity,
  checked,
  onToggle,
  onOpen,
}: {
  row: CallRow
  signalLabels: Map<string, string>
  signalSeverity: Map<string, string>
  checked: boolean
  onToggle: () => void
  onOpen: () => void
}) {
  const account = [row.brokerAgency, row.region].filter(
    (part) => part !== null && part !== undefined && part !== '',
  )
  const callerContext = [
    row.callerKind,
    row.agentName ? `agent ${row.agentName}` : null,
    row.agentRef ? `(${row.agentRef})` : null,
  ].filter(
    (part) => part !== null && part !== undefined && part !== '',
  )
  const callerName = row.callerName?.trim()
  const callerDetails = [
    ...callerContext,
  ].filter((part): part is string => part !== null)
  const accountLabel = row.employerName ?? row.employerRef ?? 'Account not recorded'
  const secondaryAccount = account.length > 0 ? account.join(' · ') : 'Broker / region not recorded'
  const topicLabel = row.category ?? 'Topic not recorded'
  const topicDetails = [
    (row.productLines ?? []).filter(Boolean).join(', ') || null,
    row.touchpoint,
  ].filter((part) => part !== null && part !== undefined && part !== '')
  const quality = row.qualityScore == null ? 'Quality not recorded' : `quality ${String(row.qualityScore)}`
  const talkTime = row.ahtSeconds == null
    ? 'Talk-only AHT not recorded'
    : `talk-only AHT ≥${formatDuration(row.ahtSeconds)}`
  const signals = row.signals
  const indicators = [
    row.complaint ? 'Complaint' : null,
    row.escalationTriggered && !row.escalationHandled ? 'Escalation missed' : null,
    row.knowledgeFailure ? 'Knowledge failure' : null,
    ...((row.controlExceptions ?? []).length > 0 ? ['Control exception'] : []),
  ].filter((label): label is string => label !== null)

  return (
    <tr
      className={`nv-clickable${checked ? ' nv-selected' : ''}`}
      tabIndex={0}
      // The prototype's `data-call` row (`nv2.js`'s `wireRows`): the whole
      // row opens the call, and the checkbox — the one interactive thing
      // inside it — still wins over the row's own click.
      onClick={(event) => {
        if ((event.target as HTMLElement).closest('input')) return
        onOpen()
      }}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          onOpen()
        }
      }}
    >
      <td className="nv-call-check">
        <input
          type="checkbox"
          aria-label={`Select call ${row.reference}`}
          checked={checked}
          onChange={onToggle}
        />
      </td>
      <td>
        <span className="nv-call-primary nv-call-mono">{row.reference}</span>
        <small className="nv-call-secondary">{row.occurredOn}</small>
      </td>
      <td>
        <span className="nv-call-primary">{accountLabel}</span>
        <small className="nv-call-secondary">{secondaryAccount}</small>
      </td>
      <td>
        <span className="nv-call-primary">
          <Named name={callerName} reference={row.callerRef} mask fallback="Caller not recorded" />
        </span>
        <small className="nv-call-secondary">
          {callerDetails.length > 0
            ? callerDetails.join(' · ')
            : callerName
              ? 'Caller type / agent not recorded'
              : 'Caller details not recorded'}
        </small>
      </td>
      <td>
        <span className="nv-call-primary">{topicLabel}</span>
        <small className="nv-call-secondary">
          {topicDetails.length > 0 ? topicDetails.join(' · ') : 'Product line / touchpoint not recorded'}
        </small>
      </td>
      <td>
        {row.outcome ? (
          <span className="nv-call-primary" style={{ color: OUTCOME_COLOR[row.outcome.code] }}>{row.outcome.label}</span>
        ) : (
          <span className="nv-call-primary">Outcome not recorded</span>
        )}
        <small className="nv-call-secondary">
          {quality} · {talkTime}
        </small>
      </td>
      <td>
        {signals === undefined ? (
          <span className="nv-call-empty">Signal data unavailable</span>
        ) : signals.length === 0 ? (
          <span className="nv-call-empty">No signals raised</span>
        ) : (
          <div className="nv-call-signals" aria-label="Signals">
            {signals.map((signal, index) => {
              const severity = signalSeverity.get(signal)
              return (
                <span
                  className={`nv-call-signal${severity ? ` nv-call-signal-${severity.toLowerCase()}` : ''}`}
                  key={`${signal}-${String(index)}`}
                >
                  {signalLabels.get(signal) ?? signal}
                </span>
              )
            })}
          </div>
        )}
        {indicators.length > 0 ? (
          <div className="nv-call-indicators">
            {indicators.map((indicator) => <span className="nv-call-indicator" key={indicator}>{indicator}</span>)}
          </div>
        ) : null}
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

function formatDuration(seconds: number): string {
  const totalSeconds = Math.floor(Math.abs(seconds))
  const minutes = Math.floor(totalSeconds / 60)
  const remainder = totalSeconds % 60
  const sign = seconds < 0 ? '−' : ''
  if (minutes === 0) return `${sign}${String(remainder)}s`
  if (remainder === 0) return `${sign}${String(minutes)}m`
  return `${sign}${String(minutes)}m ${String(remainder)}s`
}
