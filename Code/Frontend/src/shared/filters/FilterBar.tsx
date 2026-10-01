/**
 * The filter bar, on every screen.
 *
 * Follows the v2 prototype: a lean primary row, an **Advanced** disclosure
 * beside **Reset all** carrying a count of what is hidden behind it, and a
 * chip row showing only what someone actually set, each chip removable.
 *
 * ## The scope line, and the one thing v2 dropped that this keeps
 *
 * v2 removed the scope line. `plan.md` §9 lists "filters slice, never hide"
 * as a standing practice and requires the applied row to "always show scope
 * and count" — conflict **C2** in the revised plan. The resolution recorded
 * there is to take v2's chip row *and* keep the count, which is what this
 * does: the chips say what was set, and the count says how much of the
 * corpus survived it. A reader who has filtered to nothing needs to be told,
 * not left looking at an empty screen.
 *
 * ## Options come from the server
 *
 * Regions, brokers, employers, agents and touchpoints arrive from
 * `/insights/filters`, which ignores the current selection on purpose. If
 * this component derived them from the data on screen, narrowing once would
 * remove the way back.
 */

import { useState } from 'react'

import { useFilterOptions } from '@/shared/api/insights'
import { ADVANCED_KEYS, FLAG_KEYS, useFilters } from '@/shared/filters/useFilters'
import type { FlagKey, MultiKey } from '@/shared/filters/useFilters'
import { PeriodControl } from '@/shared/filters/PeriodControl'
import type { PeriodMode } from '@/shared/filters/PeriodControl'
import '@/shared/filters/filters.css'

/** Wording for each filter key. Codes never reach a reader. */
const LABELS: Record<string, string> = {
  region: 'Region',
  broker: 'Broker',
  employer: 'Employer',
  agent: 'Agent',
  category: 'Topic',
  productLine: 'Product line',
  touchpoint: 'Touchpoint',
  outcome: 'Outcome',
  signal: 'Signal',
  intent: 'Intent',
  complaintTarget: 'Complaint against',
  qualityBand: 'Call quality',
  escalated: 'Escalated',
  complaint: 'Complaint',
  complianceException: 'Compliance exception',
}

interface Option {
  value: string
  label: string
}

/** The prototype's own wording: "All 6 regions", not "All 6". */
const PLURALS: Partial<Record<MultiKey, string>> = {
  region: 'regions',
  broker: 'brokers',
  employer: 'employers',
  agent: 'agents',
  touchpoint: 'touchpoints',
  signal: 'signals',
  category: 'topics',
  productLine: 'lines',
  outcome: 'outcomes',
  intent: 'intents',
  qualityBand: 'quality bands',
}

export function FilterBar({
  callsInScope,
  compact = false,
}: {
  callsInScope?: number
  /**
   * `filterBar({ compact: true })` in `nv2.js` — period, region and Reset,
   * with no broker, employer or Advanced.
   *
   * Two screens ask for it and both have the same reason: they are not
   * about an account. Narrowing an agent page by employer would leave a
   * conduct figure resting on whichever two calls that employer happened
   * to make, and the executive overview is a book-wide summary that a
   * single broker turns into something else. The advanced filters do not
   * disappear from the URL — a link carrying one still applies, and the
   * chip row below still shows it — they are simply not offered here.
   */
  compact?: boolean
}) {
  const filters = useFilters()
  const { data, isPending, isError } = useFilterOptions(filters.apiSearch)
  const [advancedOpen, setAdvancedOpen] = useState(false)
  // In the URL rather than in state: a shared link should restore the picker
  // a colleague sees, not only the dates behind it.
  const mode = (filters.single.period as PeriodMode | undefined) ?? 'week'

  // Undefined means "not loaded yet", which the select renders as
  // Loading rather than as an empty list. They are different states.
  const options: Partial<Record<MultiKey, Option[] | undefined>> = {
    region: data?.regions.map((region) => ({ value: region, label: region })),
    broker: data?.brokers.map((broker) => ({ value: broker.ref, label: broker.agency })),
    employer: data?.employers.map((employer) => ({
      value: employer.ref,
      label: employer.name,
    })),
    // The roster's name, falling back to the reference for an agent who
    // took a call and is not on it. A dropdown of AGT-01 … AGT-20 is a
    // list nobody can pick from.
    agent: data?.agents.map((agent) => ({ value: agent.ref, label: agent.name })),
    touchpoint: data?.touchpoints.map((point) => ({ value: point, label: point })),
    // The workbook's own wording, like `touchpoint` — not a `{code, label}`
    // pair because a label identical to its own code is not a label.
    category: data?.categories.map((category) => ({ value: category, label: category })),
    productLine: data?.productLines.map((line) => ({ value: line.code, label: line.label })),
    outcome: data?.outcomes.map((outcome) => ({ value: outcome.code, label: outcome.label })),
    signal: data?.signals.map((signal) => ({ value: signal.code, label: signal.label })),
    intent: data?.intents.map((intent) => ({ value: intent.code, label: intent.label })),
    complaintTarget: data?.complaintTargets.map((target) => ({
      value: target.code,
      label: target.label,
    })),
    qualityBand: data?.qualityBands.map((band) => ({ value: band.code, label: band.label })),
  }

  // Membership is tested against the key list, not against `filters.flags`.
  // An unset flag is simply absent from that object, so `key in flags` is
  // false for it and the check would fall through to `filters.multi`, which
  // has no entry for a flag key at all.
  const isFlag = (key: string): key is FlagKey => (FLAG_KEYS as readonly string[]).includes(key)

  const advancedCount = ADVANCED_KEYS.filter((key) =>
    isFlag(key) ? filters.flags[key] !== undefined : filters.multi[key].length > 0,
  ).length

  const select = (key: MultiKey) => {
    const available = options[key]
    const chosen = filters.multi[key]
    return (
      <label key={key} className="nv-fg">
        <span>{LABELS[key]}</span>
        <select
          value=""
          disabled={!available || available.length === 0}
          onChange={(event) => {
            if (event.target.value) filters.toggleMulti(key, event.target.value)
          }}
        >
          <option value="">
            {available === undefined
              ? 'Loading…'
              : available.length === 0
                ? 'None recorded'
                : chosen.length > 0
                  ? `${String(chosen.length)} selected`
                  : `All ${String(available.length)} ${PLURALS[key] ?? ''}`.trim()}
          </option>
          {available?.map((option) => (
            <option key={option.value} value={option.value}>
              {chosen.includes(option.value) ? '✓ ' : ''}
              {option.label}
            </option>
          ))}
        </select>
      </label>
    )
  }

  const flag = (key: FlagKey) => (
    <label key={key} className="nv-fg">
      <span>{LABELS[key]}</span>
      <select
        value={filters.flags[key] === undefined ? '' : String(filters.flags[key])}
        onChange={(event) => {
          filters.setFlag(key, event.target.value === '' ? null : event.target.value === 'true')
        }}
      >
        {/* "Any" is not the same as "no". Absent narrows nothing; false is
            a real selection, and the API distinguishes them. */}
        <option value="">Any</option>
        <option value="true">Yes</option>
        <option value="false">No</option>
      </select>
    </label>
  )

  return (
    <section className="nv-filterbar" aria-label="Filters">
      <div className="nv-filters">
        <PeriodControl
          mode={mode}
          from={filters.single.from ?? null}
          to={filters.single.to ?? null}
          corpusFrom={data?.corpusPeriod?.from ?? null}
          corpusTo={data?.corpusPeriod?.to ?? null}
          onChange={(next) => {
            filters.setMany({
              period: next.mode === 'week' ? null : next.mode,
              from: next.from,
              to: next.to,
            })
          }}
        />
        {select('region')}
        {compact ? null : select('broker')}
        {compact ? null : select('employer')}

        <div className="nv-fbtns">
          <button
            type="button"
            className="nv-btn"
            onClick={filters.reset}
            disabled={filters.activeCount === 0}
          >
            Reset all
          </button>
          {compact ? null : (
            <button
              type="button"
              className="nv-btn"
              aria-expanded={advancedOpen}
              onClick={() => {
                setAdvancedOpen((open) => !open)
              }}
            >
              Advanced filters
              {advancedCount > 0 ? <span className="nv-advn">{advancedCount}</span> : null}
              <span aria-hidden="true"> {advancedOpen ? '▴' : '▾'}</span>
            </button>
          )}
        </div>
      </div>

      {advancedOpen && !compact ? (
        <div className="nv-filters nv-advpanel">
          {select('category')}
          {select('productLine')}
          {select('touchpoint')}
          {select('outcome')}
          {select('signal')}
          {select('intent')}
          {select('complaintTarget')}
          {select('qualityBand')}
          {select('agent')}
          {flag('escalated')}
          {flag('complaint')}
          {flag('complianceException')}
        </div>
      ) : null}

      {/* Filters slice, never hide. The chips say what was set; the count
          says how much survived it. Both, or a reader cannot tell an empty
          screen from a narrow one. */}
      <div className="nv-appliedbar">
        {filters.applied.map(({ key, value }) => (
          <span className="nv-chipf" key={`${key}:${value}`}>
            {LABELS[key] ?? key}: {labelFor(key, value, options)}
            <button
              type="button"
              aria-label={`Remove ${LABELS[key] ?? key} filter ${labelFor(key, value, options)}`}
              onClick={() => {
                if (isFlag(key)) filters.setFlag(key, null)
                else filters.clear(key, value)
              }}
            >
              ×
            </button>
          </span>
        ))}
        <span className="nv-scope">
          {callsInScope === undefined
            ? filters.activeCount === 0
              ? 'No filters applied'
              : `${String(filters.activeCount)} filters applied`
            : `${String(callsInScope)} calls in scope`}
        </span>
        {isError ? (
          <span className="nv-scope nv-warn">
            Filter options unavailable — the lists above may be incomplete.
          </span>
        ) : null}
        {isPending ? <span className="nv-scope">Loading options…</span> : null}
      </div>
    </section>
  )
}

/** A chip shows the reader's wording, never the code it sends. */
function labelFor(
  key: string,
  value: string,
  options: Partial<Record<MultiKey, Option[] | undefined>>,
): string {
  const found = options[key as MultiKey]?.find((option) => option.value === value)
  return found?.label ?? value
}
