/**
 * Every primitive and chart on one page.
 *
 * A component library nobody can look at is a library nobody reviews. The
 * tests prove the behaviour that would fail silently; this proves the things
 * only an eye catches — that the tokens read correctly in both themes, that
 * the shape-coded pills are distinguishable, that a gap in a chart is
 * visible as a gap.
 *
 * It renders **fixture data, clearly labelled as such**. Nothing here comes
 * from the API and nothing here is a claim about the corpus; the figures are
 * chosen to exercise the awkward states — withheld, empty, gapped — rather
 * than to look plausible.
 */

import {
  BarCell,
  Gauge,
  Heatmap,
  MiniBars,
  Sparkline,
  VBars,
  VLine,
} from '@/shared/design/charts'
import { EvidenceLink } from '@/shared/design/drawer/Evidence'
import {
  BigRow,
  Claim,
  DataTable,
  Delta,
  Empty,
  EpistemicChip,
  FigureSample,
  FigureValue,
  KpiTile,
  Note,
  Panel,
  Quote,
  RiskPill,
  SeverityLabel,
  StatusPill,
  Tooltip,
  Withheld,
} from '@/shared/design/primitives'
import type { EpistemicKind, Figure } from '@/shared/design/primitives'

const WEEKS = ['Wk 1', 'Wk 2', 'Wk 3', 'Wk 4', 'Wk 5', 'Wk 6']

function fixture(over: Partial<Figure>): Figure {
  return {
    value: 0.42,
    published: true,
    n: 64,
    basis: { code: 'OBSERVED', label: 'Observed' },
    withheldReason: null,
    caveats: [],
    callIds: ['C-0001', 'C-0002', 'C-0003'],
    ...over,
  }
}

const OBSERVED = fixture({})

// The two withheld fixtures differ in more than their reason, and that is
// the point of having both on the page (D13). A figure suppressed below min
// n **keeps its basis** — it is still our count, there are just too few
// calls to publish it. A figure the v9 schema has no field for has no
// origin to name at all, so its basis is null and no chip is drawn.
const BELOW_MIN_N = fixture({
  published: false,
  value: null,
  n: 4,
  basis: { code: 'DERIVED', label: 'Derived' },
  withheldReason: { code: 'BELOW_MIN_N', label: 'Too few calls to publish' },
  caveats: ['4 calls, and this metric needs 30.'],
})
const NO_FIELD = fixture({
  published: false,
  value: null,
  n: 0,
  basis: null,
  withheldReason: { code: 'NO_FIELD', label: 'Not a field in the v9 schema' },
  callIds: [],
})

const KINDS: EpistemicKind[] = [
  'observed',
  'reference',
  'derived',
  'pattern',
  'inference',
  'recommendation',
]

const percent = (value: number): string => `${String(Math.round(value * 100))}%`

export function DesignGallery() {
  return (
    <div className="nv-gallery">
      <header>
        <h1>Design system</h1>
        <p className="nv-lede">
          Every primitive and chart, on fixture data. Nothing here comes from the API, and no
          figure below is a claim about the corpus — the values are chosen to exercise the awkward
          states rather than to look plausible.
        </p>
      </header>

      <Panel
        title={
          <>
            Figures
            <Tooltip>
              <p>
                Every published number goes through one component, so a withheld figure cannot
                reach a formatter and be rendered as a zero.
              </p>
            </Tooltip>
          </>
        }
        sub="A withheld figure is never a zero, and the reason it was withheld is part of it."
        chip={<EpistemicChip kind="observed" />}
      >
        <BigRow>
          <KpiTile
            label="Published"
            value={<FigureValue figure={OBSERVED} format={percent} />}
            meta={<FigureSample figure={OBSERVED} />}
          />
          <KpiTile
            label="Withheld — too few calls"
            value={<FigureValue figure={BELOW_MIN_N} format={percent} />}
            meta="More calls would fix this one"
            tone="withheld"
          />
          <KpiTile
            label="Withheld — no such field"
            value={<FigureValue figure={NO_FIELD} format={percent} />}
            meta="Only a schema change fixes this one"
            tone="withheld"
          />
          <KpiTile label="Needs attention" value="12" meta="accounts flagged" tone="hot" />
        </BigRow>

        <p className="nv-row">
          <EvidenceLink callIds={OBSERVED.callIds ?? []} title="Calls behind this figure" />
          <span className="nv-spacer" />
          <Delta now={12} prior={10} />
          <Delta now={8} prior={10} />
          <Delta now={5} prior={0} />
        </p>
      </Panel>

      <Panel
        title="Claims and status"
        sub="Every panel says what kind of claim it is. Status is shape-coded, never colour alone — these pages get printed."
        chip={<EpistemicChip kind="reference" />}
      >
        <p className="nv-row">
          {KINDS.map((kind) => (
            <EpistemicChip key={kind} kind={kind} />
          ))}
        </p>
        <p className="nv-row">
          <RiskPill eligible flagged />
          <RiskPill eligible flagged={false} />
          <RiskPill eligible={false} flagged={false} />
          <StatusPill tone="flagged">Renewing soon</StatusPill>
        </p>
        <p className="nv-row">
          <SeverityLabel severity="CRITICAL" />
          <SeverityLabel severity="HIGH" />
          <SeverityLabel severity="MEDIUM" />
          <SeverityLabel severity="LOW" />
        </p>
        <Claim>
          A claim sits against a rule, so it reads as an assertion rather than as prose.
        </Claim>
        <Quote source="C-0042 · member">
          I might look elsewhere when this comes up for renewal.
        </Quote>
        <Note suppressed>
          A suppressed note carries a warning edge, for a figure that exists but is not being
          shown.
        </Note>
      </Panel>

      <Panel
        title="Tables"
        sub="At most six columns. A seventh throws rather than shipping — the explanation belongs in the (i) tooltip."
        chip={<EpistemicChip kind="observed" />}
      >
        <DataTable
          columns={[
            { key: 'account', header: 'Account' },
            { key: 'risk', header: 'Risk' },
            { key: 'calls', header: 'Calls', numeric: true },
            { key: 'trend', header: 'Trend' },
            { key: 'share', header: 'Unresolved', numeric: true },
          ]}
          rows={[
            {
              key: 'a',
              cells: [
                'Northwind Traders',
                <RiskPill key="p" eligible flagged />,
                14,
                <Sparkline key="s" values={[2, 3, null, 5, 6]} label="Calls each week" />,
                <BarCell key="b" value={6} max={14} bad />,
              ],
            },
            {
              key: 'b',
              cells: [
                'Contoso Ltd',
                <RiskPill key="p" eligible flagged={false} />,
                9,
                <Sparkline key="s" values={[4, 3, 3, 2, 1]} label="Calls each week" />,
                <BarCell key="b" value={1} max={14} />,
              ],
            },
            {
              key: 'c',
              cells: [
                'Fabrikam',
                <RiskPill key="p" eligible={false} flagged={false} />,
                2,
                <span key="s" className="nv-basis">
                  too few
                </span>,
                <Withheld key="w" reason={{ code: 'BELOW_MIN_N', label: 'Too few calls' }} />,
              ],
            },
          ]}
          empty={<Empty />}
          caption="Accounts, risk and call volume"
        />
      </Panel>

      <Panel
        title="Charts"
        sub="Each measures its container, so a 12px label stays 12px. A null is a gap — never a zero at the baseline."
        chip={<EpistemicChip kind="pattern" />}
      >
        <div className="nv-gallery-grid">
          <div>
            <h3>Bars — week 4 has no calls</h3>
            <VBars
              labels={WEEKS}
              series={[
                { name: 'Calls', values: [11, 9, 12, null, 8, 10], color: 'var(--seq-2)' },
                { name: 'Unresolved', values: [2, 1, 3, null, 1, 2], color: 'var(--critical)' },
              ]}
              ariaLabel="Calls each week"
            />
          </div>
          <div>
            <h3>Line — the gap breaks it</h3>
            <VLine
              labels={WEEKS}
              series={[
                { name: 'Quality', values: [72, 74, 69, null, 78, 81], color: 'var(--seq-3)' },
              ]}
              yMax={100}
              ariaLabel="Average quality each week"
            />
          </div>
        </div>

        <div className="nv-gallery-grid">
          <div>
            <h3>Gauge — measured and withheld</h3>
            <div className="nv-row">
              <Gauge value={64} label="64%" ariaLabel="Escalation integrity" />
              <Gauge value={null} label="–" ariaLabel="Escalation integrity, withheld" />
            </div>
          </div>
          <div>
            <h3>Mini bars</h3>
            <p className="nv-row">
              <MiniBars values={[2, 4, 9]} label="Rising across the quarter" />
              <MiniBars values={[9, 5, 2]} label="Easing across the quarter" />
            </p>
          </div>
        </div>

        <h3>Heatmap — a dot is none, not the palest step</h3>
        <Heatmap
          rows={['West', 'Midwest', 'Northeast']}
          columns={['Claims & EOB', 'Billing & Premium', 'Enrolment']}
          cells={[
            { row: 'West', column: 'Claims & EOB', value: 12 },
            { row: 'West', column: 'Billing & Premium', value: 4 },
            { row: 'West', column: 'Enrolment', value: 0 },
            { row: 'Midwest', column: 'Claims & EOB', value: 7 },
            { row: 'Midwest', column: 'Billing & Premium', value: 0 },
            { row: 'Midwest', column: 'Enrolment', value: 2 },
            { row: 'Northeast', column: 'Claims & EOB', value: 3 },
            { row: 'Northeast', column: 'Billing & Premium', value: 9 },
            { row: 'Northeast', column: 'Enrolment', value: 1 },
          ]}
          ariaLabel="Calls by region and topic"
        />
      </Panel>

      <Panel
        title="Empty states"
        sub="An empty panel says what to do about it. At batch-1 volume it is usually a filter that is too narrow, not a real absence."
        chip={<EpistemicChip kind="observed" />}
      >
        <Empty />
      </Panel>
    </div>
  )
}
