/**
 * The evidence a figure opens.
 *
 * Every response carries `callIds` behind every figure, which is what makes
 * "every figure opens its evidence" possible rather than aspirational. This
 * renders that list and offers each call.
 *
 * ## The list is a drawer frame; the call is not
 *
 * A list of references is short, is read at a glance, and is genuinely a
 * detour from the screen underneath — which is what a dialog is for. The
 * call behind one of them is four analysis panels and a whole conversation,
 * which is not, so it is a page at `/calls/:reference` and the drawer closes
 * on the way there. `shared/calls/openCall.ts` has the argument; `CallScreen`
 * is where the call itself now lives.
 *
 * Nothing here renders an empty shell. An empty evidence panel reads as
 * "there is nothing behind this figure", which is the opposite of true and
 * the worst thing this drawer could imply.
 */

import { Empty, Note } from '@/shared/design/primitives'
import { useDrawer } from '@/shared/design/drawer/drawerContext'
import { useOpenCall } from '@/shared/calls/openCall'

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

/** The calls behind a figure, each opening its own page. */
export function CallList({ callIds }: { callIds: string[] }) {
  const openCall = useOpenCall()

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
                openCall(id)
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
