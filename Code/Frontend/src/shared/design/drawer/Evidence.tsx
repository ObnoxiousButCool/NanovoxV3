/**
 * The evidence a figure opens.
 *
 * Every response carries `callIds` behind every figure, which is what makes
 * "every figure opens its evidence" possible rather than aspirational. This
 * renders that list and offers each call as the next frame.
 *
 * The call's own contents — its tags, the rules it turned on, the transcript
 * turns — need `GET /insights/calls/{id}`, which arrives in Phase 3. Until
 * then a call frame says so. It does **not** render an empty shell: an empty
 * evidence panel reads as "there is nothing behind this figure", which is
 * the opposite of true and the worst thing this drawer could imply.
 */

import { Empty, Note } from '@/shared/design/primitives'
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

/**
 * One call's evidence.
 *
 * Deliberately unbuilt rather than mocked. The transcript is the one place
 * label stripping matters most (plan §6.3), and the endpoint that serves it
 * does not exist yet.
 */
export function CallEvidence({ callId }: { callId: string }) {
  return (
    <Empty title={`Call ${callId}`}>
      The call view arrives in Phase 3, with the endpoint that serves its tags, the rules it
      turned on and its transcript turns.
    </Empty>
  )
}
