/**
 * What the pipeline made of one call, beside the transcript that produced it.
 *
 * **Four panels, four layers.** The workbook's Call Tag Schema names L1, L2,
 * L3 and L4 in its "Emitted by" column and nothing beyond L4 exists in it.
 * The server groups the fields — see `call_analysis.py` — so the two ends
 * cannot disagree about which layer produced what.
 *
 * Schema fields 17-18 are computed in code and never sent to a model, and
 * the L4 panel says so where it shows them. They are written with L4 and
 * have no run of their own, so they are labelled rather than given a panel
 * of their own.
 *
 * ## Colour is never the only signal
 *
 * Each panel carries an accent colour, and the accent is never what
 * distinguishes it. The title names the layer and the subtitle says how it
 * works — L1's reads "No model, and the same transcript always gives the
 * same answer" — so a reader who cannot separate blue from orange loses
 * nothing. `StatusPill` makes the same argument in the design system. The
 * four layers take the four categorical accents; the derived panel is
 * deliberately neutral and dashed, so the one panel that is not a layer does
 * not look like one.
 *
 * The "Code"/"Model" badge each panel used to wear was removed on request.
 * The subtitles carried the same distinction in longer words, which is why
 * it could go.
 *
 * ## Every panel opens
 *
 * L3 and L4 used to arrive collapsed, because in a dialog four open panels
 * and a transcript were an unreadable scroll. On a page with a column of its
 * own there is room, and a reader who has navigated to one call wants to see
 * it rather than to click four times first. They stay collapsible.
 *
 * ## An unrun layer is not a clean call
 *
 * Every panel renders its own `notRunBecause` rather than its empty state
 * when the layer has not run. "No signals raised" for a layer that never ran
 * reports a call as clean on the strength of never having looked at it.
 *
 * ## D7
 *
 * The L3 panel shows `knowledge_failure` — schema field 8, the rule that was
 * stated wrongly. It is **organisational and never attributed to the agent**,
 * and the panel says so where a reader would otherwise assume. The separate
 * `knowledge_error` signal in L4 is the agent-conduct event. Neither panel
 * reconciles the two or counts them together: D7 is open with Karim and
 * nothing in code may settle it.
 */

import type { ReactNode } from 'react'

import type { components } from '@/shared/api/schema'
import { Named, Note } from '@/shared/design/primitives'
import { DrawerPanel } from '@/shared/design/drawer/DrawerPanel'

type Analysis = components['schemas']['CallAnalysisResponse']
type L1 = components['schemas']['L1PanelResponse']
type L2 = components['schemas']['L2PanelResponse']
type L3 = components['schemas']['L3PanelResponse']
type L4 = components['schemas']['L4PanelResponse']
type Coded = components['schemas']['CodedValue']
type Evidenced = components['schemas']['EvidencedItem']

export function CallAnalysis({
  analysis,
  callerName,
}: {
  analysis: Analysis
  /**
   * The caller's name, from the same response's header fields.
   *
   * Passed in rather than added to the L1 panel: L1's own output is the
   * reference it resolved, and a name is reference data the layer never
   * saw. The panel would otherwise print the member id bare, which is the
   * one identifier here that points outside the business.
   */
  callerName?: string | null | undefined
}) {
  return (
    <section className="nv-layers">
      <h4>What we made of this call</h4>
      <DrawerPanel
        accent="l1"
        title="L1 — Deterministic extraction"
        subtitle="A pattern match over the opening turns. No model, and the same transcript always gives the same answer."
        present={analysis.l1.ran}
        absentBecause={analysis.l1.notRunBecause}
        openByDefault
      >
        <L1Body panel={analysis.l1} callerName={callerName} />
      </DrawerPanel>

      <DrawerPanel
        accent="l2"
        title="L2 — Classification"
        subtitle="What the call was about and how it ended."
        present={analysis.l2.ran}
        absentBecause={analysis.l2.notRunBecause}
        openByDefault
      >
        <L2Body panel={analysis.l2} />
      </DrawerPanel>

      <DrawerPanel
        accent="l3"
        title="L3 — Quality & knowledge"
        subtitle="The score, the markers behind it, and any rule stated incorrectly."
        present={analysis.l3.ran}
        absentBecause={analysis.l3.notRunBecause}
        openByDefault
      >
        <L3Body panel={analysis.l3} />
      </DrawerPanel>

      <DrawerPanel
        accent="l4"
        title="L4 — Signals & gaps"
        subtitle="What this call is evidence of, and any process gap raised on it."
        present={analysis.l4.ran}
        absentBecause={analysis.l4.notRunBecause}
        openByDefault
      >
        <L4Body panel={analysis.l4} />
      </DrawerPanel>

    </section>
  )
}

function L1Body({
  panel,
  callerName,
}: {
  panel: L1
  callerName?: string | null | undefined
}) {
  return (
    <dl className="nv-facts">
      <Fact label="Caller">
        <Named name={callerName} reference={panel.callerRef} mask />
      </Fact>
      <Fact label="Control exceptions">
        {(panel.controlExceptions ?? []).length === 0 ? (
          // Safe to state as a finding: L1 ran, and unlike the model layers
          // it either proves an exception or proves there was none.
          <span className="nv-none">None found</span>
        ) : (
          <ul className="nv-chips">
            {(panel.controlExceptions ?? []).map((item) => (
              <li key={item.code} className="nv-chip nv-chip-warn">
                {item.label}
              </li>
            ))}
          </ul>
        )}
      </Fact>
    </dl>
  )
}

function L2Body({ panel }: { panel: L2 }) {
  return (
    <>
      {/* The summary sentence leads the page, in `CallVerdict`. Printing
          it here too would put one finding on screen twice. */}
      <dl className="nv-facts">
        <Fact label="Outcome">
          <Chip value={panel.outcome} />
        </Fact>
        <Fact label="Topic">{panel.category ?? <Unknown />}</Fact>
        <Fact label="Product lines">
          {(panel.productLines ?? []).length === 0 ? (
            <Unknown>None named</Unknown>
          ) : (
            <ul className="nv-chips">
              {(panel.productLines ?? []).map((line) => (
                <li key={line.code} className="nv-chip">
                  {line.label}
                </li>
              ))}
            </ul>
          )}
        </Fact>
        <Fact label="Touchpoint">{panel.touchpoint ?? <Unknown />}</Fact>
        <Fact label="Complaint">
          <YesNo value={panel.complaintPresent} />
          {panel.complaintAttributedTo ? <> — against {panel.complaintAttributedTo.label}</> : null}
        </Fact>
        <Fact label="Escalation warranted">
          <YesNo value={panel.escalationTriggered} />
          {panel.escalationRequestedByCaller === true ? <> — the caller asked</> : null}
        </Fact>
        <Fact label="Broker named aloud">
          <YesNo value={panel.brokerNamedAloud} />
          {panel.brokerRef === null || panel.brokerRef === undefined ? null : (
            <> — <code>{panel.brokerRef}</code></>
          )}
          {panel.brokerSentiment ? <>, {panel.brokerSentiment.label.toLowerCase()}</> : null}
          {panel.brokerMatchesEmployerOfRecord === false ? (
            <>
              {' '}
              <em>Not this employer&rsquo;s broker of record.</em>
            </>
          ) : null}
        </Fact>
        <Fact label="Affects">
          {panel.impactScope === null || panel.impactScope === undefined ? (
            <Unknown />
          ) : (
            <>
              {panel.impactScope.label}
              {panel.impactScopeCount === null || panel.impactScopeCount === undefined
                ? ''
                : ` (${String(panel.impactScopeCount)})`}
              {/* The caller's own claim, and a reader who takes it for our
                  count will over-read one sentence into a population. */}
              <small>As the caller stated it, not a count of our own.</small>
            </>
          )}
        </Fact>
        {panel.primaryIssue === null || panel.primaryIssue === undefined ? null : (
          <Fact label="Mainly about">{panel.primaryIssue}</Fact>
        )}
        {(panel.secondaryIssues ?? []).length === 0 ? null : (
          <Fact label="Also raised">
            <ul className="nv-plain">
              {(panel.secondaryIssues ?? []).map((issue) => (
                <li key={issue}>{issue}</li>
              ))}
            </ul>
          </Fact>
        )}
      </dl>
      {(panel.intent ?? []).length === 0 ? null : (
        <>
          <h5>Commercial intent</h5>
          <Evidence items={panel.intent ?? []} />
        </>
      )}
    </>
  )
}

function L3Body({ panel }: { panel: L3 }) {
  return (
    <>
      <dl className="nv-facts">
        <Fact label="Quality score">
          {panel.qualityScore === null || panel.qualityScore === undefined ? (
            <Unknown />
          ) : (
            <>
              <b>{panel.qualityScore}</b> / 100
              {panel.qualityTier ? <> — {panel.qualityTier.label}</> : null}
              {/* Provisional means "not final", which is a different thing
                  from a low score and is read as one if left unsaid. */}
              {panel.qualityStatus?.code === 'provisional' ? (
                <small>{panel.qualityStatus.label}. Something later in the pipeline may move it.</small>
              ) : null}
            </>
          )}
        </Fact>
        <Fact label="Rule stated incorrectly">
          <YesNo value={panel.knowledgeFailurePresent} />
          {panel.knowledgeFailureRuleId === null || panel.knowledgeFailureRuleId === undefined ? null : (
            <> — <code>{panel.knowledgeFailureRuleId}</code></>
          )}
          {panel.knowledgeFailurePresent === true ? (
            <small>
              An organisational record of a rule stated wrongly (schema field 8). It is not
              attributed to the agent who took this call.
            </small>
          ) : null}
        </Fact>
        {panel.knowledgeFailureCorrectStatement === null ||
        panel.knowledgeFailureCorrectStatement === undefined ? null : (
          <Fact label="What the rule says">{panel.knowledgeFailureCorrectStatement}</Fact>
        )}
      </dl>
      {(panel.markers ?? []).length === 0 ? null : (
        <>
          <h5>Markers behind the score</h5>
          <ul className="nv-markers">
            {(panel.markers ?? []).map((marker, index) => (
              <li
                key={`${marker.dimension}-${String(marker.turnSeq)}-${String(index)}`}
                className={
                  marker.polarity.code === 'POSITIVE' ? 'nv-marker-up' : 'nv-marker-down'
                }
              >
                <b>
                  {marker.dimension} — {marker.polarity.label}
                </b>
                <p>{marker.description}</p>
                <blockquote>
                  &ldquo;{marker.quote}&rdquo; <span>turn {marker.turnSeq}</span>
                </blockquote>
              </li>
            ))}
          </ul>
        </>
      )}
    </>
  )
}

function L4Body({ panel }: { panel: L4 }) {
  return (
    <>
      <h5>Signals</h5>
      {(panel.signals ?? []).length === 0 ? (
        <Note>L4 ran and raised no signal on this call.</Note>
      ) : (
        <Evidence items={panel.signals ?? []} />
      )}
      <dl className="nv-facts">
        <Fact label="Escalation handled">
          <YesNo value={panel.escalationHandled} />
          {panel.escalationTriggerType ? <> — {panel.escalationTriggerType.label}</> : null}
        </Fact>
        <Fact label="Process gap">
          <YesNo value={panel.processGapPresent} />
          {panel.processGapType === null || panel.processGapType === undefined ? null : (
            <> — {panel.processGapType}</>
          )}
        </Fact>
        {panel.processGapProposedChange === null ||
        panel.processGapProposedChange === undefined ? null : (
          <Fact label="Proposed change">
            {panel.processGapProposedChange}
            <small>
              {[panel.processGapRaisedBy?.label, panel.processGapStatus?.label]
                .filter((part): part is string => part !== undefined)
                .join(' · ')}
            </small>
          </Fact>
        )}
        {panel.processGapTouchpoint === null || panel.processGapTouchpoint === undefined ? null : (
          <Fact label="Where">{panel.processGapTouchpoint}</Fact>
        )}
        <Fact label="Root cause sits with">
          <Chip value={panel.rootCauseOwner} />
          {/* Said on the field, because it arrives with L4 and would
              otherwise read as something the model concluded. */}
          <small>Computed from the complaint and the signals. No model saw this.</small>
        </Fact>
        <Fact label="Preventable">{panel.preventable ?? <Unknown />}</Fact>
      </dl>
    </>
  )
}

function Evidence({ items }: { items: Evidenced[] }) {
  return (
    <ul className="nv-ev">
      {items.map((item, index) => (
        <li key={`${item.type.code}-${String(item.turnSeq)}-${String(index)}`}>
          <span className="nv-ev-head">
            <b>{item.type.label}</b>
            {item.severity ? (
              <span className={`nv-sev nv-sev-${item.severity.code.toLowerCase()}`}>
                {item.severity.label}
              </span>
            ) : null}
          </span>
          <blockquote>
            &ldquo;{item.quote}&rdquo; <span>turn {item.turnSeq}</span>
          </blockquote>
        </li>
      ))}
    </ul>
  )
}

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  )
}

function Chip({ value }: { value: Coded | null | undefined }) {
  if (value === null || value === undefined) return <Unknown />
  return <span className="nv-chip">{value.label}</span>
}

/**
 * A field the layer ran but left unset.
 *
 * "Not stated" rather than a dash or a blank: the layer looked, and what it
 * found was that the call did not carry this. A blank cell reads as a
 * rendering fault, and a dash reads as nil.
 */
function Unknown({ children }: { children?: ReactNode }) {
  return <span className="nv-none">{children ?? 'Not stated'}</span>
}

function YesNo({ value }: { value: boolean | null | undefined }) {
  if (value === null || value === undefined) return <Unknown />
  return <span className={value ? 'nv-yes' : 'nv-no'}>{value ? 'Yes' : 'No'}</span>
}
