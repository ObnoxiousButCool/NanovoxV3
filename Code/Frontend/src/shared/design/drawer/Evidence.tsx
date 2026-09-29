/**
 * The evidence a figure opens.
 *
 * Every response carries `callIds` behind every figure, which is what makes
 * "every figure opens its evidence" possible rather than aspirational. This
 * renders that list and offers each call as the next frame.
 *
 * A call frame reads `GET /insights/calls/{reference}` for the turns and for
 * what the pipeline made of them. That endpoint is the only one in the
 * application that serves transcript text, and the leak check runs against
 * its response — see `read_call_evidence.py`.
 *
 * The analysis sits **above** the conversation, and the conversation is a
 * panel of the same kind rather than a heading and a list. A reader who
 * opened this frame from a figure arrived asking why this call was counted,
 * and the answer is in the layer panels; the transcript is the evidence for
 * them, which is the order the two want to be read in.
 *
 * It is the only panel whose producer is **Source**: it is neither computed
 * nor inferred, and every other panel is derived from it. Open on arrival,
 * because a reader who wanted the layers can shut it and a reader who wanted
 * the call should not have to find it. L1 and L2 are the only other two
 * open by default — the frame is a long scroll otherwise, and those are the
 * two that every analysed call has.
 *
 * Nothing here renders an empty shell. An empty evidence panel reads as
 * "there is nothing behind this figure", which is the opposite of true and
 * the worst thing this drawer could imply — so a call with no turns says
 * why, and a failure says what failed.
 */

import { useCallEvidence } from '@/shared/api/insights'
import { Empty, Note } from '@/shared/design/primitives'
import { CallAnalysis } from '@/shared/design/drawer/CallAnalysis'
import { DrawerPanel } from '@/shared/design/drawer/DrawerPanel'
import { useDrawer } from '@/shared/design/drawer/drawerContext'

/** A button that opens the calls behind one figure. */
export function EvidenceLink({
  callIds,
  title = 'Evidence',
  children,
}: {
  callIds: string[]
  title?: string
  children?: React.ReactNode
}) {
  const { open } = useDrawer()

  if (callIds.length === 0) return null

  return (
    <button
      type="button"
      className="nv-evidence-link"
      onClick={() => {
        open({ title, chip: 'observed', body: <CallList callIds={callIds} /> })
      }}
    >
      {children ?? `${String(callIds.length)} ${callIds.length === 1 ? 'call' : 'calls'}`}
    </button>
  )
}

/** The calls behind a figure, each opening its own frame. */
export function CallList({ callIds }: { callIds: string[] }) {
  const { open } = useDrawer()

  if (callIds.length === 0) {
    return <Empty title="No calls behind this figure">Nothing was counted here.</Empty>
  }

  return (
    <>
      <Note>
        {callIds.length === 1
          ? 'One call is behind this figure.'
          : `${String(callIds.length)} calls are behind this figure.`}
      </Note>
      <ul className="nv-callids">
        {callIds.map((id) => (
          <li key={id}>
            <button
              type="button"
              onClick={() => {
                open({ title: `Call ${id}`, chip: 'observed', body: <CallEvidence callId={id} /> })
              }}
            >
              {id}
            </button>
          </li>
        ))}
      </ul>
    </>
  )
}

/** One call: who it was, how it ended, and what was said. */
export function CallEvidence({ callId }: { callId: string }) {
  const { data, isPending, error } = useCallEvidence(callId)

  if (error !== null) {
    return (
      <Empty title={`Call ${callId} could not be loaded`}>
        {/* Said, not swallowed. A drawer that fails silently is
            indistinguishable from a call with nothing behind it. */}
        {error instanceof Error ? error.message : 'The request failed.'}
      </Empty>
    )
  }
  if (isPending) {
    return <Note>Loading the call…</Note>
  }

  return (
    <>
      <dl className="nv-callfacts">
        <div>
          <dt>Caller</dt>
          {/* The reference, never a member's name. The workbench export
              makes the same choice for the same reason. */}
          <dd>
            {data.callerRef} ({data.callerType.toLowerCase()})
          </dd>
        </div>
        <div>
          <dt>Agent</dt>
          <dd>{data.agentRef}</dd>
        </div>
        <div>
          <dt>Employer</dt>
          <dd>{data.employerRef ?? 'Not resolved'}</dd>
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

      <CallAnalysis analysis={data.analysis} />

      <DrawerPanel
        accent="conversation"
        producer="Source"
        title="The conversation"
        subtitle="What was said, as it was stored. Every panel above is derived from these turns."
        present={!data.transcriptMissing}
        /* Not "Not run": nothing ran or failed to run here. The call is in
           the corpus and counted in the figures that led to this drawer; what
           is missing is the recording of it. */
        absentLabel="No transcript"
        absentBecause={
          'The call is in the corpus and counted in the figures above it. Its conversation ' +
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
    </>
  )
}
