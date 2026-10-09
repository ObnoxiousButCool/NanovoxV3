/**
 * What happened on this call, before anything is opened.
 *
 * ## The problem this solves
 *
 * The page below is four collapsible panels of equal weight, which is what
 * the dialog had to be and what a page does not. A reader arriving from a
 * figure is asking two questions — *what was this call about, and is
 * anything wrong with it* — and the answers were spread across three
 * collapsed panels: the sentence in L2, the score in L3, the signals in L4,
 * the control exceptions in L1. Four clicks to learn what one band can say.
 *
 * So the sentence, the three figures and the flags lead the page. Nothing
 * here is new: every value is rendered again, in context, in the panel that
 * owns it. The summary is the one exception — it is **moved** out of L2
 * rather than repeated, because a sentence printed twice on one screen
 * reads as two findings.
 *
 * ## It cannot flag what nobody looked at
 *
 * Every flag is gated on the layer that would know having actually run.
 * "Escalation missed" is `l2.escalationTriggered && !l4.escalationHandled`,
 * and on a call where L4 never ran that expression is *true* while the fact
 * is unknown — the precise shape of the mistake the panels below exist to
 * prevent. When L2 warranted an escalation and L4 did not run, the band says
 * the handling was never checked, which is the only true thing available.
 *
 * For the same reason "Nothing flagged" is only said when all four layers
 * ran. Otherwise it names what did run, because a clean band over a pipeline
 * that never finished is a clean bill of health nobody issued.
 */

import type { components } from '@/shared/api/schema'
import { Note } from '@/shared/design/primitives'
import { OUTCOME_COLOR } from '@/shared/design/outcome'
import './callVerdict.css'

type Analysis = components['schemas']['CallAnalysisResponse']

/** A flag is a concern, and `serious` is the ones that read first. */
interface Flag {
  key: string
  label: string
  serious: boolean
}

function flagsFor(analysis: Analysis): Flag[] {
  const { l1, l2, l3, l4 } = analysis
  const flags: Flag[] = []

  if (l1.ran) {
    for (const exception of l1.controlExceptions ?? []) {
      flags.push({ key: `ctl-${exception.code}`, label: exception.label, serious: true })
    }
  }

  if (l2.ran && l2.complaintPresent === true) {
    flags.push({
      key: 'complaint',
      label: l2.complaintAttributedTo
        ? `Complaint against ${l2.complaintAttributedTo.label}`
        : 'Complaint',
      serious: true,
    })
  }

  // The three escalation states are deliberately distinct. Collapsing the
  // middle one into either neighbour is the bug: unchecked is not handled,
  // and it is not missed either.
  if (l2.ran && l2.escalationTriggered === true) {
    if (!l4.ran) {
      flags.push({
        key: 'esc-unchecked',
        label: 'Escalation warranted — handling not checked',
        serious: false,
      })
    } else if (l4.escalationHandled === false) {
      flags.push({ key: 'esc-missed', label: 'Escalation missed', serious: true })
    }
  }

  if (l3.ran && l3.knowledgeFailurePresent === true) {
    // Named as the organisational record it is. D7: never the agent's.
    flags.push({ key: 'knowledge', label: 'Rule stated incorrectly', serious: false })
  }

  if (l4.ran) {
    if (l4.processGapPresent === true) {
      // `processGapType` is free text the model wrote and often arrives
      // code-shaped ("information_delivery"). Prefixed rather than
      // prettified: inventing a display label for a value we did not
      // define would be this page writing the model's words for it.
      flags.push({
        key: 'gap',
        label:
          l4.processGapType === null || l4.processGapType === undefined
            ? 'Process gap'
            : `Process gap — ${l4.processGapType}`,
        serious: false,
      })
    }
    for (const signal of l4.signals ?? []) {
      const severity = signal.severity?.code
      flags.push({
        key: `sig-${signal.type.code}-${String(signal.turnSeq)}`,
        label: signal.type.label,
        serious: severity === 'CRITICAL' || severity === 'HIGH',
      })
    }
  }

  // Serious first. Within a group the order above is kept, which runs
  // roughly from what we proved to what a model inferred.
  const ranked = [...flags].sort((a, b) => Number(b.serious) - Number(a.serious))

  // Two chips reading "Escalation missed" is what this band looked like
  // before: the structured L2/L4 fields say it and the L4 signal taxonomy
  // raises a signal of the same name, so both arrive. They are one concern
  // and the panels below show each in its own context — the band says it
  // once. Sorted first, so where a derived flag and a signal collide the
  // serious wording survives.
  const seen = new Set<string>()
  return ranked.filter((flag) => {
    const key = flag.label.toLowerCase()
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

export function CallVerdict({ analysis }: { analysis: Analysis }) {
  const { l2, l3 } = analysis
  const flags = flagsFor(analysis)
  const unrun = (['l1', 'l2', 'l3', 'l4'] as const).filter((key) => !analysis[key].ran)

  return (
    <section className="nv-verdict" aria-label="What happened on this call">
      {l2.ran && l2.summary !== null && l2.summary !== undefined ? (
        <p className="nv-verdict-summary">{l2.summary}</p>
      ) : (
        /* Not an empty space where a sentence goes. A blank lede reads as a
           call with nothing to say about it. */
        <Note>
          {l2.ran
            ? 'This call was classified, but no summary sentence was written for it.'
            : 'No summary: the layer that writes one has not run on this call.'}
        </Note>
      )}

      <dl className="nv-verdict-figures">
        <Figure label="Outcome">
          {l2.ran && l2.outcome ? (
            <span style={{ color: OUTCOME_COLOR[l2.outcome.code] }}>{l2.outcome.label}</span>
          ) : (
            <span className="nv-verdict-absent">Not classified</span>
          )}
        </Figure>
        <Figure label="Topic">
          {l2.ran && l2.category !== null && l2.category !== undefined ? (
            l2.category
          ) : (
            <span className="nv-verdict-absent">Not classified</span>
          )}
        </Figure>
        <Figure label="Quality">
          {l3.ran && l3.qualityScore !== null && l3.qualityScore !== undefined ? (
            <>
              {l3.qualityScore}
              <span className="nv-verdict-of">/100</span>
              {l3.qualityTier ? (
                <span className="nv-verdict-tier">{l3.qualityTier.label}</span>
              ) : null}
              {/* Provisional is "not final", which is a different thing from
                  a low score and is read as one if left unsaid. */}
              {l3.qualityStatus?.code === 'provisional' ? (
                <span className="nv-verdict-tier">Provisional</span>
              ) : null}
            </>
          ) : (
            <span className="nv-verdict-absent">Not scored</span>
          )}
        </Figure>
      </dl>

      {flags.length > 0 ? (
        <ul className="nv-verdict-flags" aria-label="Flagged on this call">
          {flags.map((flag) => (
            <li
              key={flag.key}
              className={`nv-verdict-flag${flag.serious ? ' nv-verdict-flag-serious' : ''}`}
            >
              {flag.label}
            </li>
          ))}
        </ul>
      ) : (
        <p className="nv-verdict-clear">
          {unrun.length === 0
            ? 'Nothing flagged on this call.'
            : `Nothing flagged by the layers that ran. ${unrun.length === 1 ? 'One layer has' : `${String(unrun.length)} layers have`} not run, so this is not a clean call — it is an unfinished one.`}
        </p>
      )}
    </section>
  )
}

function Figure({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  )
}
