/**
 * `/rules` — "What do we fail to explain?", as `rules.html` has it.
 *
 * ## Why this screen exists at all
 *
 * The v2 prototype dropped it. That was conflict **C5**, and Minnie closed
 * it on 2026-09-25 (**D14**): it ships, reachable from `/agents` rather
 * than on the main rail. Insights 23 and 24 render nowhere else, and
 * `/agents` has been linking here since it was written — a link to a route
 * that did not exist, which the catch-all quietly turned into the overview.
 *
 * v2 has no design for this page, so it inherits v1's layout translated
 * into the v2 language: the shared primitives, six columns at most, and
 * explanations in the (i) tooltip rather than in a paragraph.
 *
 * ## Counts, and exactly one rate
 *
 * The endpoint's own rule, and this screen's hardest line to hold: a rule
 * row carries a **count** and never a rate. The denominator a rate would
 * need is "calls where this rule was relevant", and nothing in v9 records
 * it. v1 could at least show *times cited* beside the misstatements; this
 * endpoint does not serve citations, so the column is absent rather than
 * approximated, and the panel says which figure is missing.
 *
 * The one rate here is metric 8, and it is about the corpus: calls carrying
 * a knowledge failure over all calls in the window. It is never divided
 * down to a rule.
 *
 * ## Never an agent error
 *
 * **D7 is open with Karim.** Schema field 8 is organisational wherever it
 * fires, so nothing on this page attributes a misstatement to a person, and
 * no agent is named. The `knowledge_error` signal is the agent-conduct
 * event and it lives on `/agents`.
 *
 * ## A rule with no failures is not a rule that is well explained
 *
 * The endpoint returns the whole rulebook, including the rules nobody got
 * wrong, and the last panel lists them. At this volume most of them are
 * simply rules no call in the window went near — which is a different thing
 * from a rule we explain well, and the panel says so rather than letting
 * the empty column imply it.
 */

import { useRules } from '@/shared/api/insights'
import type { Rules } from '@/shared/api/insights'
import { EvidenceLink } from '@/shared/design/drawer/Evidence'
import { useFilters } from '@/shared/filters/useFilters'
import { Screen } from '@/shared/screens/Screen'
import {
  BigRow,
  DataTable,
  Empty,
  EpistemicChip,
  FigureSample,
  FigureValue,
  KpiTile,
  Note,
  Panel,
  Provenance,
  Tooltip,
} from '@/shared/design/primitives'
import type { Row } from '@/shared/design/primitives'

type RuleRow = Rules['rules'][number]
type Count = Rules['byLayer'][number]

const UNVERIFIED = 'UNVERIFIED'

/** The grades, in the order the Rules sheets grade them — best sourced first. */
const GRADES = ['VERIFIED', 'VERIFIED (SECONDARY)', UNVERIFIED]

function misstated(rules: RuleRow[]): RuleRow[] {
  return rules.filter((rule) => rule.failures > 0)
}

export function RulesScreen() {
  const filters = useFilters()
  const { data, isPending, error } = useRules(filters.apiSearch)

  return (
    <Screen
      title="Rules we fail to explain"
      lede="The published rulebook, read against the calls that cite it. A rule stated incorrectly is a knowledge failure — the one place the corpus records us getting our own product wrong."
      compactFilters
      scope={data?.scope}
      isPending={isPending}
      error={error}
    >
      {data === undefined ? null : <RulesBody data={data} />}
    </Screen>
  )
}

function RulesBody({ data }: { data: Rules }) {
  const rules = data.rules
  const wrong = misstated(rules)
  const unverified = rules.filter((rule) => rule.confidence.code === UNVERIFIED)
  const failures = data.byLayer.reduce((total, count) => total + count.failures, 0)

  return (
    <div className="nv-grid">
      <div className="nv-c12">
        <BigRow>
          <KpiTile
            label="Published rules"
            value={rules.length}
            meta="the whole rulebook, across three layers"
          />
          <KpiTile
            label="Stated incorrectly"
            value={wrong.length}
            meta={`on ${String(failures)} ${failures === 1 ? 'call' : 'calls'} in the window`}
            tone={wrong.length > 0 ? 'hot' : 'plain'}
          />
          <KpiTile
            label="Calls carrying a knowledge failure"
            value={<FigureValue figure={data.overallRate} format={percent} />}
            meta={<FigureSample figure={data.overallRate} />}
            info={
              <Tooltip>
                Metric 8, over the {String(data.windowWeeks)}-week window ending {data.asOf}. It
                is a figure about the corpus and never about one rule: dividing it down would
                need a count of the calls each rule was relevant to, which nothing records.
              </Tooltip>
            }
          />
          <KpiTile
            label="Unverified in the workbook"
            value={unverified.length}
            meta={
              unverified.length === 0
                ? 'every rule has a source'
                : unverified.map((rule) => rule.ruleRef).join(', ')
            }
            tone={unverified.length > 0 ? 'warm' : 'plain'}
          />
        </BigRow>
      </div>

      <div className="nv-c12">
        <RewriteList rules={wrong} />
      </div>

      <div className="nv-c6">
        <ByLayer rules={rules} counts={data.byLayer} />
      </div>

      <div className="nv-c6">
        <ByProvenance rules={rules} counts={data.byProvenance} />
      </div>

      <div className="nv-c6">
        <ByCount
          title="Where the failure originated"
          rows={data.byTouchpoint}
          header="Touchpoint"
        />
      </div>

      <div className="nv-c6">
        <ByCount
          title="By subject area"
          rows={data.byArea}
          header="Subject area"
        />
      </div>

      <div className="nv-c12">
        <NothingWrong rules={rules} />
      </div>
    </div>
  )
}

function percent(value: number): string {
  return `${(value * 100).toFixed(1)}%`
}

/** Worst first — the order the endpoint already returns them in. */
function RewriteList({ rules }: { rules: RuleRow[] }) {
  const rows: Row[] = rules.map((rule) => ({
    key: rule.ruleRef,
    cells: [
      <span className="nv-ref">{rule.ruleRef}</span>,
      rule.layer.label,
      rule.area,
      rule.commonlyConfusedWith === '' ? (
        <Note suppressed>Not recorded</Note>
      ) : (
        rule.commonlyConfusedWith
      ),
      <Provenance grade={rule.confidence} />,
      <EvidenceLink callIds={rule.failedCallIds} title={`Rule ${rule.ruleRef}`}>
        {rule.failures}
      </EvidenceLink>,
    ],
  }))

  return (
    <Panel
      title="Rules we stated incorrectly"
      chip={<EpistemicChip kind="observed" />}
      info={
        <Tooltip>
          A rule misstated twice is two calls, not a percentage. The denominator a rate would
          need is the number of calls where that rule was relevant, and the v9 schema does not
          record it, so this column counts and stops. Nothing here is attributed to an agent:
          schema field 8 is organisational wherever it fires (D7).
        </Tooltip>
      }
    >
      <DataTable
        caption="Published rules stated incorrectly, worst first"
        columns={[
          { key: 'rule', header: 'Rule' },
          { key: 'layer', header: 'Layer' },
          { key: 'area', header: 'Area' },
          { key: 'confused', header: 'Commonly confused with' },
          { key: 'provenance', header: 'Provenance' },
          { key: 'failures', header: 'Calls', numeric: true },
        ]}
        rows={rows}
        empty={
          <Empty title="No rule was stated incorrectly in scope">
            Nothing in the window carried a knowledge failure. At this volume that is a quiet
            window rather than a clean rulebook.
          </Empty>
        }
      />
    </Panel>
  )
}

/**
 * Whose rulebook the problem sits in.
 *
 * Rule counts come from the rulebook and failure counts from the endpoint's
 * own roll-up, joined on the layer code rather than recomputed here — the
 * two answer different questions, and a layer can appear in one and not in
 * the other.
 */
function ByLayer({ rules, counts }: { rules: RuleRow[]; counts: Count[] }) {
  const codes = [
    ...new Set([...counts.map((count) => count.value.code), ...rules.map((rule) => rule.layer.code)]),
  ]
  const rows: Row[] = codes.map((code) => {
    const mine = rules.filter((rule) => rule.layer.code === code)
    const count = counts.find((entry) => entry.value.code === code)
    return {
      key: code,
      cells: [
        count?.value.label ?? mine[0]?.layer.label ?? code,
        mine.length,
        misstated(mine).length,
        count?.failures ?? 0,
      ],
    }
  })

  return (
    <Panel
      title="By rule layer"
      chip={<EpistemicChip kind="observed" />}
    >
      <DataTable
        caption="Rules and failures by layer"
        columns={[
          { key: 'layer', header: 'Layer' },
          { key: 'rules', header: 'Rules', numeric: true },
          { key: 'wrong', header: 'Misstated', numeric: true },
          { key: 'calls', header: 'Calls', numeric: true },
        ]}
        rows={rows}
      />
    </Panel>
  )
}

/** Insight 24: by provenance grade, with the unverified rules listed by id. */
function ByProvenance({ rules, counts }: { rules: RuleRow[]; counts: Count[] }) {
  const codes = GRADES.filter((code) => rules.some((rule) => rule.confidence.code === code))
  const rows: Row[] = codes.map((code) => {
    const mine = rules.filter((rule) => rule.confidence.code === code)
    const count = counts.find((entry) => entry.value.code === code)
    const grade = count?.value ?? mine[0]?.confidence
    return {
      key: code,
      cells: [
        grade === undefined ? code : <Provenance grade={grade} />,
        mine.length,
        misstated(mine).length,
        count?.failures ?? 0,
        // The ids are the point of the row when there are few enough to act
        // on. A list of 110 references is not a finding, it is the rulebook.
        mine.length <= 4 ? (
          <span className="nv-ref">{mine.map((rule) => rule.ruleRef).join(', ')}</span>
        ) : (
          <Note suppressed>Too many to list</Note>
        ),
      ],
    }
  })

  return (
    <Panel
      title="How sure are we of our own rules?"
      chip={<EpistemicChip kind="reference" />}
    >
      <DataTable
        caption="Rules and failures by provenance grade"
        columns={[
          { key: 'grade', header: 'Provenance' },
          { key: 'rules', header: 'Rules', numeric: true },
          { key: 'wrong', header: 'Misstated', numeric: true },
          { key: 'calls', header: 'Calls', numeric: true },
          { key: 'which', header: 'Which' },
        ]}
        rows={rows}
      />
    </Panel>
  )
}

/** One cut of the failures — a coded value and a count, nothing derived. */
function ByCount({
  title,
  rows,
  header,
}: {
  title: string
  rows: Count[]
  header: string
}) {
  return (
    <Panel title={title} chip={<EpistemicChip kind="observed" />}>
      <DataTable
        caption={`Failures by ${header.toLowerCase()}`}
        columns={[
          { key: 'value', header },
          { key: 'calls', header: 'Calls', numeric: true },
        ]}
        rows={rows.map((row) => ({
          key: row.value.code,
          cells: [row.value.label, row.failures],
        }))}
        empty={
          <Empty title="Nothing to break down">
            No knowledge failure in scope carried one.
          </Empty>
        }
      />
    </Panel>
  )
}

/**
 * The rules nobody got wrong — listed, and explicitly not praised.
 *
 * v1 listed the rules no call *cited*, which is a stronger statement than
 * this endpoint can support: it serves failures, not citations. So this says
 * the weaker and true thing.
 */
function NothingWrong({ rules }: { rules: RuleRow[] }) {
  const clean = rules.filter((rule) => rule.failures === 0)

  return (
    <Panel
      title="Rules no call got wrong"
      chip={<EpistemicChip kind="observed" />}
    >
      {clean.length === 0 ? (
        <Empty title="Every published rule was misstated at least once">
          At this volume that would be surprising enough to check the join before acting on it.
        </Empty>
      ) : (
        <p className="nv-ref nv-rulelist">{clean.map((rule) => rule.ruleRef).join(' · ')}</p>
      )}
    </Panel>
  )
}
