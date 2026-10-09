/**
 * `/calls/:reference` — one call, as a page.
 *
 * ## Why this is not a drawer frame any more
 *
 * Everything here used to render inside the evidence dialog, two or three
 * frames down. A call is the longest thing in the product — four analysis
 * panels and an entire conversation — and a reader opens it to read it, not
 * to glance at it. A dialog gave that reading no address to share, no
 * browser Back, a scroll box inside the page's own scroll, and nothing left
 * on screen once Escape was pressed by accident. `shared/calls/openCall.ts`
 * has the rest of the argument.
 *
 * The drawer keeps the frame it suits: the short list of calls behind a
 * figure. Opening one of them lands here.
 *
 * ## Back and Close are different promises
 *
 * **Back** returns to the screen the call was opened from, in the state it
 * was in — the filtered table on page 3, the account that was on screen.
 * That only exists when the reader arrived from inside the application, so
 * the button is absent on a shared link rather than present and pointing at
 * whatever happened to be in the tab's history before.
 *
 * **Close** leaves the call for the full list at `/calls`. It is fixed, it
 * works from a deep link, and it is the one control that is always there.
 *
 * Escape does what Back does, because every reader who used the dialog has
 * that reflex and a page that ignored it would feel broken rather than
 * different.
 *
 * ## The chrome outlives the content
 *
 * The header renders before the call does and stays through a failure. A
 * reader whose call cannot be loaded is still somewhere, with a way back;
 * the dialog's equivalent was an error message in a box, which is the same
 * information in a worse place.
 */

import { useEffect } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'

import { useCallEvidence } from '@/shared/api/insights'
import { CallVerdict } from '@/app/screens/CallVerdict'
import { CallAnalysis } from '@/shared/design/drawer/CallAnalysis'
import { DrawerPanel } from '@/shared/design/drawer/DrawerPanel'
import { Empty, EpistemicChip, Named, Skeleton, SkeletonBlock } from '@/shared/design/primitives'
import { originLabel, readCallOrigin } from '@/shared/calls/openCall'
import './call.css'

export function CallScreen() {
  const { reference = '' } = useParams<{ reference: string }>()
  // React Router types history state as `any`, which it cannot know. It is
  // `unknown` here, and `readCallOrigin` validates it rather than trusting
  // the shape — a reader can arrive with a hand-written one.
  const state: unknown = useLocation().state
  const navigate = useNavigate()

  const origin = readCallOrigin(state)
  const label = origin === null ? null : originLabel(origin)
  const canGoBack = origin !== null

  useEffect(() => {
    if (!canGoBack) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') navigate(-1)
    }
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('keydown', onKey)
    }
  }, [canGoBack, navigate])

  return (
    /* `nv-screen` carries the 28px page gutter every other screen stands
       clear of the rail by, and the grid's own top margin. Without it this
       page sat flush against the rail -- the exact bug `screen.css` already
       has a comment about. */
    <div className="nv-screen nv-callpage">
      <header className="nv-callpage-head">
        <div className="nv-callpage-id">
          <h1>Call {reference}</h1>
          {/* Everything on this page is what was said and what the pipeline
              made of it. Nothing here is a projection. */}
          <EpistemicChip kind="observed" />
        </div>
        <div className="nv-callpage-actions">
          {canGoBack ? (
            <button
              type="button"
              className="nv-btn"
              onClick={() => {
                navigate(-1)
              }}
            >
              ← Back{label === null ? '' : ` to ${label}`}
            </button>
          ) : null}
          <button
            type="button"
            className="nv-btn"
            onClick={() => {
              navigate('/calls')
            }}
          >
            Close
          </button>
        </div>
      </header>

      <CallBody reference={reference} />
    </div>
  )
}

function CallBody({ reference }: { reference: string }) {
  const { data, isPending, error } = useCallEvidence(reference)

  if (error !== null) {
    return (
      <Empty title={`Call ${reference} could not be loaded`}>
        {/* Said, not swallowed. A page that fails silently is
            indistinguishable from a call with nothing behind it. */}
        {error instanceof Error ? error.message : 'The request failed.'}
      </Empty>
    )
  }

  if (isPending) {
    // The shape of the page, not the word "Loading…": the facts across the
    // top, then the two columns. Boxes only — a skeleton that drew a
    // plausible outcome or quality score would be the page making a claim
    // it has not read.
    return (
      <Skeleton>
        <div className="nv-grid">
          <div className="nv-c12">
            <SkeletonBlock lines={1} />
          </div>
          <div className="nv-c6">
            <SkeletonBlock lines={5} />
          </div>
          <div className="nv-c6">
            <SkeletonBlock lines={5} />
          </div>
        </div>
      </Skeleton>
    )
  }

  return (
    <div className="nv-grid">
      {/* What happened, before anything is opened. The reader arrived from
          a figure asking what this call was and whether anything is wrong
          with it, and the answers were spread over three collapsed panels. */}
      <div className="nv-c12">
        <CallVerdict analysis={data.analysis} />
      </div>

      {/* Who the call was between. Below the verdict and set quietly: it is
          what you check after you know what happened, not before. */}
      <div className="nv-c12">
        <dl className="nv-callfacts nv-callpage-facts">
          <div>
            <dt>Caller</dt>
            {/* The caller's name, and `mask` keeps their reference off the
                screen: member and contact references are the one identifier
                here that points at a person outside the business. The agent
                and the employer below keep theirs in brackets. */}
            <dd>
              <Named name={data.callerName} reference={data.callerRef} mask />{' '}
              {data.callerType.toLowerCase()}
            </dd>
          </div>
          <div>
            <dt>Agent</dt>
            <dd>
              <Named name={data.agentName} reference={data.agentRef} />
            </dd>
          </div>
          <div>
            <dt>Employer</dt>
            <dd>
              <Named name={data.employerName} reference={data.employerRef} fallback="Not resolved" />
            </dd>
          </div>
          <div>
            <dt>Record</dt>
            <dd>
              {data.resolutionStatus}
              {data.resolutionReason === null || data.resolutionReason === undefined
                ? ''
                : ` — ${data.resolutionReason}`}
            </dd>
          </div>
        </dl>
      </div>

      {/* The two halves of a call, side by side on a wide screen and
          stacked below 900px. The analysis is what we made of the call and
          the conversation is what it was made from, so the reading order is
          left to right; neither is readable across a 1400px window, which
          is why this is a split rather than one full-width column. */}
      <div className="nv-c6">
        <CallAnalysis analysis={data.analysis} callerName={data.callerName} />
      </div>

      <div className="nv-c6">
        {/* The same wrapper and heading the analysis column has, so the two
            columns start on the same line and read as the pair they are:
            what we made of the call, and what we made it from. */}
        <section className="nv-layers">
          <h4>What it was made from</h4>
          <DrawerPanel
            accent="conversation"
            title="The conversation"
            subtitle="What was said, as it was stored. The analysis is derived from these turns."
            present={!data.transcriptMissing}
            /* Not "Not run": nothing ran or failed to run here. The call is in
               the corpus and counted in the figures that led to this page; what
               is missing is the recording of it. */
            absentLabel="No transcript"
            absentBecause={
              'The call is in the corpus and counted in the figures that led here. Its conversation ' +
              'was not stored, which is not the same as a conversation with nothing in it.'
            }
            openByDefault
          >
            <ol className="nv-turns">
              {data.turns?.map((turn) => (
                <li key={turn.sequence} className={turn.role === 'AGENT' ? 'nv-agent' : 'nv-caller'}>
                  <b>{turn.role === 'AGENT' ? 'Agent' : 'Caller'}</b>
                  <p>{turn.text}</p>
                </li>
              ))}
            </ol>
          </DrawerPanel>
        </section>
      </div>
    </div>
  )
}
