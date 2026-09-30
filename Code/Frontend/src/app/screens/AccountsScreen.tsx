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
import { AccountBody, AccountHeader } from '@/app/screens/AccountScreen'
import { AccountActions, AccountCalls, AccountTiles } from '@/app/screens/AccountPanels'
import { Empty, Note } from '@/shared/design/primitives'
import { InsightStrip } from '@/shared/insights/Insights'
import '@/app/screens/accounts.css'

/** What the risk screen knows about one account, if anything. */
interface RiskState {
  flagged: boolean
  indicators: number
  calls: number
  /** Months until renewal, or null when the month could not be read. */
  monthsToRenewal: number | null
  /**
   * Whether the ten families could be tested against this account at all.
   *
   * False below the indicator floor, where `indicators` is nought for every
   * account whatever its calls carry — so the number is not a finding and is
   * not shown as one. Junipero is the case that found this: flagged, renewing
   * this month, two of its three calls carrying a complaint, and a bare 0
   * beside the word Flagged.
   */
  assessed: boolean
}

/**
 * The indicator count beside the flag, or a dash where there is no count.
 *
 * Two different noughts reach this component and they are opposite
 * statements: an account tested against the ten families that cleared them
 * all, and an account with too few calls for any family to be tested. The
 * first is a finding; the second is a gap. A bare 0 renders them the same,
 * and next to the word "Flagged" it reads as a flag with nothing behind it.
 */
function IndicatorCount({ state }: { state: RiskState }) {
  if (!state.assessed) {
    return (
      <i className="nv-acct-unassessed" title="Too few calls to assess the indicator families">
        &mdash;
      </i>
    )
  }
  return <i>{state.indicators}</i>
}

/** An account nobody could assess is not unflagged; it sorts below both. */
function rank(flagged: boolean | undefined): number {
  if (flagged === undefined) return -1
  return flagged ? 1 : 0
}

/**
 * Months to renewal, with the unknown ones last.
 *
 * `null` would otherwise read as "renewing now" and put the accounts we know
 * least about at the top — the same reasoning, and the same 99, as the
 * server's own key.
 */
function renewal(state: RiskState | undefined): number {
  return state?.monthsToRenewal ?? 99
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
            Flagged
            <IndicatorCount state={state} />
          </span>
        ) : (
          <span className="nv-acct-state">
            Not flagged
            <IndicatorCount state={state} />
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
        // The floor is on the employer, so one unassessable family means all
        // ten are. `every` over an empty list is true, which is the right
        // answer: no families is not the same as families nobody could test.
        assessed: row.observations.every((observation) => observation.assessable),
        monthsToRenewal: row.monthsToRenewal ?? null,
      })
    }
    return map
  }, [risk.data])

  const ordered = useMemo(() => {
    const employers = options.data?.employers ?? []
    // D12's order, amended 2026-09-29: the flag first, then the indicator
    // count, then soonest renewal, then name. The same key the server sorts
    // `assessed` by, because an account must not move between two screens
    // that both rank it — and this list cannot simply follow the server's
    // order, since it holds every employer including the ones the risk
    // response never mentions.
    //
    // The renewal tiebreak is new here. The comment claimed it before and
    // the code never applied it, so the two screens already disagreed
    // whenever an indicator count tied.
    return [...employers].sort((a, b) => {
      const left = states.get(a.ref)
      const right = states.get(b.ref)
      return (
        rank(right?.flagged) - rank(left?.flagged) ||
        (right?.indicators ?? -1) - (left?.indicators ?? -1) ||
        renewal(left) - renewal(right) ||
        a.name.localeCompare(b.name)
      )
    })
  }, [options.data, states])

  const needle = query.trim().toLowerCase()
  const shown = needle
    ? ordered.filter((employer) => employer.name.toLowerCase().includes(needle))
    : ordered

  const selected = employerRef ?? ordered[0]?.ref
  const account = useAccount(selected ?? '', filters.apiSearch)
  // Fetched on sight, as `employer.html` has it: the strip is part of the
  // page rather than something the reader asks for.
  //
  // This costs a model call per account opened, and the picker holds
  // ninety-five. It was on-demand for exactly that reason and is back on
  // load by decision, not by oversight. The query is keyed by the
  // reference, so an account read once is served from cache rather than
  // billed again, and switching account can never show the last one's
  // sentences under this one's name.
  const insights = useGeneratedInsights('account', filters.apiSearch, selected)
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
              {/* `employer.html`'s order: the account, then what a model
                  makes of it, then its own counts, then the rest. */}
              <AccountHeader data={account.data} brokerName={brokerName} />
              <div className="nv-c12">
                <InsightStrip data={insights.data} pending={insights.isFetching} />
              </div>
              <div className="nv-c12">
                <AccountTiles profile={account.data.profile} employerRef={selected} />
              </div>
              <AccountBody data={account.data} />
              <div className="nv-c12">
                <AccountCalls employerRef={selected} search={filters.apiSearch} />
              </div>
              <div className="nv-c12">
                <AccountActions employerRef={selected} />
              </div>
            </>
          )}
        </div>
      </div>
    </Screen>
  )
}
