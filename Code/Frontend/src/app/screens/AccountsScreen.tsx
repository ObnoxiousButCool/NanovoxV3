/**
 * `/accounts` — "Insights & patterns around employers".
 *
 * The prototype's `employer.html`: an account picker beside one account's
 * detail, not a list page that navigates away. Picking an account changes
 * the detail in place and the URL with it, so the view is linkable and the
 * back button does what a reader expects.
 *
 * `/accounts/:employerRef` renders this same screen with that account
 * selected. One component for both, because they are one page — the
 * previous split left `/accounts` as a placeholder while the detail lived
 * at a route nothing linked to from the rail.
 *
 * ## The picker lists every account, not only the assessable ones
 *
 * `NV.employersInScope()` in the prototype lists the whole book. Ours does
 * too, and that matters more here than it looks: an account with three
 * calls is not a low-risk account, it is one nobody could assess, and a
 * picker that quietly dropped it would make the book look smaller and
 * cleaner than it is. Each row says which of the three states it is in.
 *
 * ## There is no band pill
 *
 * The prototype shows `bandPill(scoped_band)`. **D12 removed the band.**
 * A row shows the flag (metric 10 and nothing else) with the indicator
 * count beside it, and "not assessed" where there were too few calls. This
 * is a deliberate divergence from the presentation authority, and it is the
 * one the workbook wins.
 */

import { useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import {
  useAccount,
  useFilterOptions,
  useGeneratedInsights,
  useRisk,
} from '@/shared/api/insights'
import { useFilters } from '@/shared/filters/useFilters'
import { Screen } from '@/shared/screens/Screen'
import { AccountBody } from '@/app/screens/AccountScreen'
import { AccountActions, AccountCalls, AccountTiles } from '@/app/screens/AccountPanels'
import { Empty, Note } from '@/shared/design/primitives'
import { InsightStrip } from '@/shared/insights/Insights'
import '@/app/screens/accounts.css'

/** What the risk screen knows about one account, if anything. */
interface RiskState {
  flagged: boolean
  indicators: number
  calls: number
}

function PickerRow({
  name,
  region,
  state,
  current,
  onSelect,
}: {
  name: string
  region: string
  state: RiskState | undefined
  current: boolean
  onSelect: () => void
}) {
  return (
    <li>
      <button type="button" aria-current={current ? 'true' : undefined} onClick={onSelect}>
        <span>
          <b>{name}</b>
          <small>{region}</small>
        </span>
        {/* Three states, never a band. An account nobody could assess is
            the third one, and it is not the same as "not flagged". */}
        {state === undefined ? (
          <span className="nv-acct-state nv-acct-none">Not assessed</span>
        ) : state.flagged ? (
          <span className="nv-acct-state nv-acct-flag">
            Flagged<i>{state.indicators}</i>
          </span>
        ) : (
          <span className="nv-acct-state">
            Not flagged<i>{state.indicators}</i>
          </span>
        )}
      </button>
    </li>
  )
}

export function AccountsScreen() {
  const { employerRef } = useParams()
  const navigate = useNavigate()
  const filters = useFilters()
  const [query, setQuery] = useState('')

  const options = useFilterOptions(filters.apiSearch)
  // The risk screen's own response, from cache when it has been visited.
  // It carries the flag and the indicator count per account; nothing else
  // does, and recomputing either here would be a second definition.
  const risk = useRisk(filters.apiSearch)

  const states = useMemo(() => {
    const map = new Map<string, RiskState>()
    for (const row of risk.data?.assessed ?? []) {
      map.set(row.employerRef, {
        flagged: row.flagged,
        indicators: row.observations.filter((observation) => observation.observed).length,
        calls: row.calls,
      })
    }
    return map
  }, [risk.data])

  const ordered = useMemo(() => {
    const employers = options.data?.employers ?? []
    // Most indicators first, then soonest renewal, then name — the
    // prototype's own order, and the same one the risk table uses, so an
    // account does not move between two screens that both rank it.
    return [...employers].sort((a, b) => {
      const left = states.get(a.ref)?.indicators ?? -1
      const right = states.get(b.ref)?.indicators ?? -1
      return right - left || a.name.localeCompare(b.name)
    })
  }, [options.data, states])

  const needle = query.trim().toLowerCase()
  const shown = needle
    ? ordered.filter((employer) => employer.name.toLowerCase().includes(needle))
    : ordered

  const selected = employerRef ?? ordered[0]?.ref
  const account = useAccount(selected ?? '', filters.apiSearch)
  // Asked for, not fetched on sight: one model call per account, and the
  // picker holds ninety-five. `readFor` is the account the reader asked
  // about, so moving to another one puts the offer back rather than
  // quietly spending again.
  //
  // Keyed by the reference either way, so switching account can never
  // show the last one's sentences under this one's name.
  const [readFor, setReadFor] = useState<string | null>(null)
  const insights = useGeneratedInsights('account', filters.apiSearch, selected, {
    enabled: readFor === selected,
  })
  const brokerName = (ref: string) =>
    options.data?.brokers.find((broker) => broker.ref === ref)?.agency ?? ref

  return (
    <Screen
      title="Insights & patterns around employers"
      lede="Pick an account to see what its members call about, which risk indicators fired, and the exact call behind each one."
      scope={account.data?.scope}
      isPending={options.isPending}
      error={options.error}
    >
      <div className="nv-c12 nv-acctsplit">
        <aside className="nv-picker" aria-label="Accounts">
          <span className="nv-picker-head">Accounts · {ordered.length}</span>
          <input
            type="search"
            value={query}
            placeholder="Search accounts"
            aria-label="Search accounts"
            onChange={(event) => {
              setQuery(event.target.value)
            }}
          />
          <ul>
            {shown.map((employer) => (
              <PickerRow
                key={employer.ref}
                name={employer.name}
                region={employer.region}
                state={states.get(employer.ref)}
                current={employer.ref === selected}
                onSelect={() => {
                  navigate({
                    pathname: `/accounts/${encodeURIComponent(employer.ref)}`,
                    search: filters.search,
                  })
                  window.scrollTo({ top: 0 })
                }}
              />
            ))}
            {shown.length === 0 ? <li className="nv-picker-none">No match</li> : null}
          </ul>
        </aside>

        <div className="nv-grid nv-acctdetail">
          {selected === undefined ? (
            <div className="nv-c12">
              <Empty title="No account matches these filters">
                Clear a filter to bring accounts back.
              </Empty>
            </div>
          ) : account.error ? (
            <div className="nv-c12">
              <Empty title="That account could not be read">
                <Note>{account.error.message}</Note>
              </Empty>
            </div>
          ) : account.data === undefined ? (
            <div className="nv-c12">
              <Note>Loading the account…</Note>
            </div>
          ) : (
            <>
              {/* `employer.html`'s order: the strip, then the account's own
                  counts, then the figures, then what it calls about. */}
              <div className="nv-c12">
                <InsightStrip
                  data={insights.data}
                  pending={insights.isFetching}
                  onRequest={() => {
                    setReadFor(selected)
                  }}
                />
              </div>
              <div className="nv-c12">
                <AccountTiles profile={account.data.profile} employerRef={selected} />
              </div>
              <AccountBody data={account.data} brokerName={brokerName} />
              <div className="nv-c12">
                <AccountCalls employerRef={selected} search={filters.apiSearch} />
              </div>
              <div className="nv-c12">
                <AccountActions
                  employerRef={selected}
                  // Optional on the wire; an account with no evidence
                  // cited is a real state, not a missing field.
                  callRefs={account.data.risk.evidence ?? []}
                />
              </div>
            </>
          )}
        </div>
      </div>
    </Screen>
  )
}
