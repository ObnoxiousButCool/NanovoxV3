/**
 * The one clearly-marked AI surface per screen.
 *
 * Two shapes over one payload. `InsightStrip` is the compact row the exec
 * page carries above its figures; `InsightFeed` is the expandable list,
 * with the figures each sentence read and a "what to do" link. Neither
 * calculates anything: every number in a sentence was checked against the
 * screen's own published figures before it left the server, and a sentence
 * that failed that check took the whole surface down with it.
 *
 * ## Unavailable is rendered, not hidden
 *
 * **U2 (D14):** when the provider is unavailable the surface shows an
 * explicit unavailable state, like the withheld panels — not templated copy
 * standing in for generated text, and not a silently hidden panel. So there
 * is no fallback prose in this file. A reader who cannot have insights is
 * told so, in the same visual language a withheld figure uses, because the
 * two facts are the same fact: nobody could say.
 *
 * ## The badge and the standing tooltip are not decoration
 *
 * Every surface carries both, always, on generated and unavailable alike.
 * The tooltip states the two promises the prototype's README asks for in
 * its own words — that this never calculates, forecasts or adds a number of
 * its own, and that where an insight and a figure disagree the figure is
 * right. They are the reason a reader is allowed to trust the panel at all,
 * so they are part of the component rather than something a screen
 * remembers to add.
 */

import { useState } from 'react'

import { IssueCue } from '@/shared/actions/IssueLink'
import { isIssueKey } from '@/shared/actions/issueHref'
import type { GeneratedInsights, Insight } from '@/shared/api/insights'
import { Panel, Tooltip } from '@/shared/design/primitives'
import '@/shared/insights/insights.css'

/** The promises the surface makes, shown wherever it appears. */
export const AI_PROMISE =
  'Written from the figures on this page. It never calculates, forecasts or adds a ' +
  'number of its own. If an insight and a figure disagree, the figure is right.'

function AiBadge() {
  return (
    <span className="nv-ai">
      <span className="nv-ai-mark">AI</span>
      <Tooltip align="right">{AI_PROMISE}</Tooltip>
    </span>
  )
}

/**
 * Why there is nothing to read, in the reader's terms.
 *
 * The API's own label, not wording invented here — for the same reason
 * `Withheld` uses the API's: "no model is configured" and "the model stated
 * a figure we did not measure" are different facts with different owners,
 * and flattening them into "unavailable" loses the one that matters.
 */
function Unavailable({ reason }: { reason: GeneratedInsights['reason'] }) {
  return (
    <p className="nv-ai-out">
      <span className="nv-ai-out-mark" aria-hidden="true">
        –
      </span>
      <span>
        No insights for this screen. {reason?.label ?? 'The reason was not given.'}
      </span>
    </p>
  )
}

/** One sentence, with what it read and what to do about it. */
function InsightBody({ insight, expanded }: { insight: Insight; expanded: boolean }) {
  const issue = insight.issueKey
  return (
    <>
      <p className="nv-ai-sentence">{insight.sentence}</p>
      {expanded ? (
        <div className="nv-ai-detail">
          <p className="nv-ai-read">
            <span>Read from</span> {insight.factKeys.join(', ')}
          </p>
          {/* The link is dropped rather than guessed when the key is not one
              the registry knows: a dead "what to do" is worse than none. */}
          {issue !== null && issue !== undefined && isIssueKey(issue) ? (
            <IssueCue issue={issue} />
          ) : null}
        </div>
      ) : null}
    </>
  )
}

function KindChip({ insight }: { insight: Insight }) {
  return (
    <span className={`nv-ai-kind nv-ai-kind-${insight.kind.code.toLowerCase()}`}>
      {insight.kind.label}
    </span>
  )
}

/**
 * The compact row: two to four sentences, no expansion.
 *
 * Deliberately not clickable. A strip that opened something would compete
 * with the figures beneath it, and the figures are the page.
 */
export function InsightStrip({
  data,
  onRequest,
  pending = false,
}: {
  data: GeneratedInsights | undefined
  /**
   * Given where the surface is asked for rather than fetched on sight.
   *
   * On `/exec` and `/risk` there is one surface per page, so loading it is
   * one call. On an account there are ninety-five of them, one per account
   * a reader clicks, and each is billed. So that screen hands this a
   * request handler and the reader decides.
   *
   * A held-back query still serves anything already in the cache, so an
   * account read once shows its sentences again without asking twice.
   */
  onRequest?: (() => void) | undefined
  pending?: boolean
}) {
  if (!data) {
    if (onRequest === undefined) return null
    return (
      <section className="nv-ai-strip" aria-label="Generated insights">
        <header>
          <h2>What this looks like</h2>
          <AiBadge />
        </header>
        <p className="nv-ai-ask">
          Reading this account&rsquo;s figures asks a model, which costs a call. The
          figures below do not wait for it.
        </p>
        <button
          type="button"
          className="nv-ai-go"
          onClick={onRequest}
          disabled={pending}
        >
          {pending ? 'Reading…' : 'Read this account'}
        </button>
      </section>
    )
  }
  const items = data.insights

  return (
    <section className="nv-ai-strip" aria-label="Generated insights">
      <header>
        <h2>What this looks like</h2>
        <AiBadge />
      </header>
      {items.length === 0 ? (
        <Unavailable reason={data.reason} />
      ) : (
        <ul>
          {items.map((insight) => (
            <li key={insight.key}>
              <KindChip insight={insight} />
              <InsightBody insight={insight} expanded={false} />
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

/** The full feed: every sentence, each expandable to what it read. */
export function InsightFeed({ data }: { data: GeneratedInsights | undefined }) {
  const [open, setOpen] = useState<string | null>(null)

  if (!data) return null
  const items = data.insights

  return (
    <Panel title="What this looks like" chip={<AiBadge />}>
      {items.length === 0 ? (
        <Unavailable reason={data.reason} />
      ) : (
        <ul className="nv-ai-feed">
          {items.map((insight) => {
            const expanded = open === insight.key
            return (
              <li key={insight.key}>
                <button
                  type="button"
                  aria-expanded={expanded}
                  // Named for what opening it reveals. Without this the
                  // button's name is the two chips inside it, which says
                  // nothing to a screen reader about what it does.
                  aria-label={`What this insight read: ${insight.sentence}`}
                  onClick={() => {
                    setOpen(expanded ? null : insight.key)
                  }}
                >
                  <KindChip insight={insight} />
                  <span className="nv-ai-order">{insight.severity.label}</span>
                </button>
                <InsightBody insight={insight} expanded={expanded} />
              </li>
            )
          })}
        </ul>
      )}
      {data.provider ? (
        <p className="nv-ai-by">
          Written by {data.provider}
          {data.model ? ` (${data.model})` : ''}.
        </p>
      ) : null}
    </Panel>
  )
}


/**
 * The four-lens grid `exec.html` carries under "What this period means".
 *
 * **The lenses are a client requirement (U1)**, so all four are always
 * rendered, in this order, whether or not the model had anything to put
 * under them. A lens with nothing under it is a true statement about the
 * period's figures — the alternative is a grid that silently changes shape,
 * where a reader cannot tell "nothing to say about churn" from "churn was
 * not considered".
 *
 * The order and the labels come from the API's own coded values, so the
 * frontend is not a second place the client's taxonomy is written down.
 */
const LENS_SUB: Record<string, string> = {
  EMPLOYERS: 'Which kinds of account are struggling',
  CHURN_AND_RETENTION: 'Who might leave, and when',
  PRODUCT_AND_SERVICE: 'Which documents, lines and rules cause calls',
  PAYER_AND_CARRIER: 'Billing, premium and carrier-owned issues',
}

export function InsightLenses({ data }: { data: GeneratedInsights | undefined }) {
  if (!data) return null
  const items = data.insights

  return (
    <Panel
      title="What this period means"
      sub="The same calls read through four lenses. Each insight names what the numbers mean and what to do next."
      chip={<AiBadge />}
    >
      {items.length === 0 ? <Unavailable reason={data.reason} /> : null}
      <div className="nv-lenses">
        {/* From the response, not a list held here: the taxonomy is the
            client's, and a second copy in the client is a second copy to
            disagree. The one-line descriptions below are panel copy, which
            D13 does keep on this side. */}
        {data.lenses.map((lens) => {
          const mine = items.filter((insight) => insight.lens.code === lens.code)
          return (
            <article key={lens.code} className="nv-lens">
              <header>
                <h3>{lens.label}</h3>
                <p>{LENS_SUB[lens.code]}</p>
              </header>
              {mine.length === 0 ? (
                <p className="nv-lens-none">
                  Nothing in this period&rsquo;s figures speaks to this.
                </p>
              ) : (
                <ol>
                  {mine.map((insight) => (
                    <li key={insight.key}>
                      <KindChip insight={insight} />
                      <InsightBody insight={insight} expanded />
                    </li>
                  ))}
                </ol>
              )}
            </article>
          )
        })}
      </div>
    </Panel>
  )
}
