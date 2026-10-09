/**
 * The card, Trello-style: next move, checklist, what-was-done / what-changed,
 * activity, Move to, owner and due.
 *
 * Every write here is one `PATCH /insights/actions/{id}` — a tick, a move, a
 * logged update, a recorded outcome — through `useUpdateAction`, which
 * invalidates the board on success. There is nothing to save locally: the
 * next render shows the server's own answer, not an optimistic guess.
 */

import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import type { Action, Lane, UpdateActionBody } from '@/shared/api/actionBoard'
import { useUpdateAction } from '@/shared/api/actionBoard'
import { useOpenCall } from '@/shared/calls/openCall'
import { Note } from '@/shared/design/primitives'
import {
  formatDue,
  initials,
  laneColors,
  priorityColor,
  requirementLabel,
  sourceKindColor,
  sourceKindLabel,
} from '@/app/screens/actions/format'
import { findLane, missingRequirements, nextStepIndex } from '@/app/screens/actions/lifecycle'

export function ActionCardModal({
  action,
  lanes,
  employerName,
  onClose,
}: {
  action: Action
  lanes: Lane[]
  employerName: string | null
  onClose: () => void
}) {
  const update = useUpdateAction()
  const goToCall = useOpenCall()

  const [ownerInput, setOwnerInput] = useState(action.owner ?? '')
  const [dueInput, setDueInput] = useState(action.due ?? '')
  const [takenText, setTakenText] = useState('')
  const [outcomeText, setOutcomeText] = useState('')
  const [measureStart, setMeasureStart] = useState('')
  const [measureEnd, setMeasureEnd] = useState('')
  const [logText, setLogText] = useState('')

  const takenRef = useRef<HTMLTextAreaElement>(null)
  const outcomeRef = useRef<HTMLTextAreaElement>(null)

  const lane = findLane(lanes, action.status)
  const closed = lane ? !lane.open : false
  const nextIdx = nextStepIndex(action)
  const done = action.steps.filter((step) => step.done).length
  const colors = laneColors(lanes)

  // `clearOwner` and `clearDue` are required on the wire (they default to
  // `false`, not to "absent") — every patch carries them so a caller only
  // sets one to true when it means to clear the field.
  const patch = (body: Omit<UpdateActionBody, 'clearOwner' | 'clearDue'>) => {
    update.mutate({ id: action.id, body: { clearOwner: false, clearDue: false, ...body } })
  }

  const toggleStep = (index: number, next: boolean) => {
    const step = action.steps[index]
    patch({
      ticks: [{ index, done: next }],
      note: `${next ? 'Completed' : 'Reopened'} step: ${step?.text ?? ''}`,
    })
  }

  const moveTo = (target: Lane) => {
    if (target.code === action.status) return
    patch({ status: target.code, note: `Moved to ${target.label}` })
  }

  const saveTaken = () => {
    const text = takenText.trim()
    if (!text) return
    patch({ actionTaken: text, note: `Action taken: ${text}` })
    setTakenText('')
  }

  const saveOutcome = () => {
    const text = outcomeText.trim()
    if (!text) return
    const body: Omit<UpdateActionBody, 'clearOwner' | 'clearDue'> = {
      outcome: text,
      note: `Outcome recorded: ${text}`,
    }
    if (measureStart && measureEnd) {
      body.measurementWindow = { start: measureStart, end: measureEnd }
    }
    patch(body)
    setOutcomeText('')
  }

  const saveLog = () => {
    const text = logText.trim()
    if (!text) return
    patch({ note: text })
    setLogText('')
  }

  const saveMeta = () => {
    const owner = ownerInput.trim()
    const due = dueInput.trim()
    // `exactOptionalPropertyTypes` refuses an explicit `undefined` on an
    // optional field, so an unset value is left out of the object rather
    // than assigned — the field's absence, not its value, says "unchanged".
    update.mutate({
      id: action.id,
      body: {
        clearOwner: owner === '',
        clearDue: due === '',
        note: `Owner ${owner || 'cleared'}${due ? `, due ${formatDue(due)}` : ''}`,
        ...(owner !== '' ? { owner } : {}),
        ...(due !== '' ? { due } : {}),
      },
    })
  }

  const openCall = (callId: string) => {
    onClose()
    goToCall(callId)
  }

  let nextMoveText: string
  let nextMoveButton: { label: string; onClick: () => void } | null
  if (closed) {
    nextMoveText = 'This card is in a closed lane.'
    nextMoveButton = null
  } else if (nextIdx !== -1) {
    nextMoveText = action.steps[nextIdx]?.text ?? ''
    nextMoveButton = { label: 'Mark step done', onClick: () => { toggleStep(nextIdx, true) } }
  } else if (action.actionTaken === null) {
    nextMoveText = 'All steps are done. Record what was done.'
    nextMoveButton = { label: 'Log action taken', onClick: () => { takenRef.current?.focus() } }
  } else if (action.outcome === null) {
    nextMoveText = 'Measure the effect, then record the outcome.'
    nextMoveButton = { label: 'Record outcome', onClick: () => { outcomeRef.current?.focus() } }
  } else {
    nextMoveText = 'Outcome recorded. Choose a closed lane in Move to.'
    nextMoveButton = null
  }

  // Oldest first on the wire; the reader wants the newest update on top.
  const timeline = [...action.log].reverse()

  return (
    <>
      <div className="nv-am-head">
        <div>
          <span className="nv-am-list">
            in list{' '}
            <b style={{ color: lane ? colors.get(lane.code) : undefined }}>
              {lane?.label ?? action.statusLabel}
            </b>
          </span>
          <h2>{action.title}</h2>
        </div>
        <button type="button" className="nv-btn" onClick={onClose} aria-label="Close">
          ✕
        </button>
      </div>

      <div className="nv-am-body">
        <div className="nv-am-main">
          <div className={`nv-am-next${closed ? ' nv-closed' : ''}`}>
            <span className="nv-eyebrow">{closed ? 'Done' : 'Next step'}</span>
            <p>{nextMoveText}</p>
            {nextMoveButton ? (
              <button type="button" className="nv-btn" onClick={nextMoveButton.onClick}>
                {nextMoveButton.label}
              </button>
            ) : null}
          </div>

          {update.isError ? (
            <Note>
              {update.error instanceof Error ? update.error.message : 'The update failed.'}
            </Note>
          ) : null}

          <div className="nv-am-meta">
            <div>
              <h4>Labels</h4>
              <span className="nv-tlbl" style={{ background: priorityColor(action.priority) }}>
                {action.priority} priority
              </span>
              <span className="nv-tlbl" style={{ background: sourceKindColor(action.sourceKind) }}>
                {sourceKindLabel(action.sourceKind)}
              </span>
            </div>
            <div>
              <h4>Owner</h4>
              <span className="nv-am-who">
                <span className="nv-avatar">{initials(action.owner)}</span>
                {action.owner ?? 'Unassigned'}
              </span>
            </div>
            {action.due ? (
              <div>
                <h4>Due date</h4>
                <span className={`nv-due${action.pastDue ? ' nv-late' : ''}`}>
                  ◷ {formatDue(action.due)}
                </span>
              </div>
            ) : null}
          </div>

          <section>
            <h3>☰ Description</h3>
            <p>
              <b>Why it was raised.</b> {action.evidence}
            </p>
            {action.recommendation ? (
              <p>
                <b>Recommended.</b> {action.recommendation.text}
              </p>
            ) : null}
          </section>

          {action.steps.length > 0 ? (
            <section>
              <h3>
                ☑ Checklist <small>{done}/{action.steps.length}</small>
              </h3>
              <div className="nv-am-prog">
                <div
                  style={{ width: `${String(Math.round((done / action.steps.length) * 100))}%` }}
                />
              </div>
              <ul className="nv-am-check">
                {action.steps.map((step, index) => (
                  <li
                    key={`${String(index)}-${step.text}`}
                    className={`${step.done ? 'nv-done' : ''}${index === nextIdx && !closed ? ' nv-nx' : ''}`}
                  >
                    <button
                      type="button"
                      className="nv-bx"
                      aria-pressed={step.done}
                      aria-label={`Toggle step ${String(index + 1)}`}
                      onClick={() => { toggleStep(index, !step.done) }}
                    >
                      {step.done ? '✓' : ''}
                    </button>
                    <span>{step.text}</span>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          <section className="nv-am-forms">
            {!closed && action.actionTaken === null ? (
              <div className="nv-am-form-row">
                <h3>✎ What was done?</h3>
                <textarea
                  ref={takenRef}
                  rows={2}
                  placeholder="e.g. Called the member back and closed the claim query"
                  value={takenText}
                  onChange={(event) => { setTakenText(event.target.value) }}
                />
                <button type="button" className="nv-btn" onClick={saveTaken}>
                  Save and mark action taken
                </button>
              </div>
            ) : null}
            {!closed && action.actionTaken !== null && action.outcome === null ? (
              <div className="nv-am-form-row">
                <h3>◎ What changed?</h3>
                <textarea
                  ref={outcomeRef}
                  rows={2}
                  placeholder="e.g. No repeat contact on this topic in the following four weeks"
                  value={outcomeText}
                  onChange={(event) => { setOutcomeText(event.target.value) }}
                />
                <div className="nv-am-window">
                  <label>
                    Measured from{' '}
                    <input
                      type="date"
                      aria-label="Measurement window start"
                      value={measureStart}
                      onChange={(event) => { setMeasureStart(event.target.value) }}
                    />
                  </label>
                  <label>
                    to{' '}
                    <input
                      type="date"
                      aria-label="Measurement window end"
                      value={measureEnd}
                      onChange={(event) => { setMeasureEnd(event.target.value) }}
                    />
                  </label>
                </div>
                <button type="button" className="nv-btn" onClick={saveOutcome}>
                  Save outcome
                </button>
              </div>
            ) : null}
          </section>

          {action.callIds.length > 0 ? (
            <section>
              <h3>
                ☏ Calls behind it <small>{action.callIds.length}</small>
              </h3>
              <div className="nv-am-calls">
                {action.callIds.map((callId) => (
                  <button key={callId} type="button" onClick={() => { openCall(callId) }}>
                    <span className="nv-mono">{callId}</span>
                  </button>
                ))}
              </div>
            </section>
          ) : null}

          <section>
            <h3>↻ Activity</h3>
            <div className="nv-am-log">
              <textarea
                rows={2}
                placeholder="Log an update, e.g. Spoke to the employer, waiting on HR"
                value={logText}
                onChange={(event) => { setLogText(event.target.value) }}
              />
              <button type="button" className="nv-btn" onClick={saveLog}>
                Save update
              </button>
            </div>
            <ol className="nv-am-time">
              {timeline.map((entry) => (
                <li key={`${entry.at}-${entry.text}`}>
                  <b>{entry.text}</b>
                  <span>
                    {new Date(entry.at).toLocaleString([], {
                      day: 'numeric',
                      month: 'short',
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </span>
                </li>
              ))}
            </ol>
          </section>
        </div>

        <aside className="nv-am-side">
          <h4>Move to</h4>
          {lanes.map((target) => {
            const missing = missingRequirements(target, action)
            return (
              <button
                key={target.code}
                type="button"
                className={`nv-btn nv-mv${target.code === action.status ? ' nv-cur' : ''}`}
                disabled={target.code !== action.status && missing.length > 0}
                title={
                  missing.length > 0
                    ? `Needs ${missing.map(requirementLabel).join(', ')} first`
                    : undefined
                }
                onClick={() => { moveTo(target) }}
              >
                <i style={{ background: colors.get(target.code) }} />
                {target.label}
              </button>
            )
          })}

          <h4>Owner</h4>
          <input
            value={ownerInput}
            placeholder="Assign someone"
            onChange={(event) => { setOwnerInput(event.target.value) }}
          />
          <h4>Due date</h4>
          <input
            type="date"
            value={dueInput}
            onChange={(event) => { setDueInput(event.target.value) }}
          />
          <button
            type="button"
            className="nv-btn"
            style={{ marginTop: 8, justifyContent: 'center' }}
            onClick={saveMeta}
          >
            Save owner &amp; due
          </button>

          {action.issueKey ? (
            <>
              <h4>Playbook</h4>
              <Link
                className="nv-btn"
                onClick={onClose}
                to={`/actions?${new URLSearchParams({
                  focus: action.issueKey,
                  ...(action.employerRef ? { employer: action.employerRef } : {}),
                }).toString()}`}
              >
                Open the steps →
              </Link>
            </>
          ) : null}

          {action.employerRef ? (
            <>
              <h4>Account</h4>
              <Link
                className="nv-btn"
                onClick={onClose}
                to={`/accounts/${encodeURIComponent(action.employerRef)}`}
              >
                {employerName ?? action.employerRef} →
              </Link>
            </>
          ) : null}

          <p className="nv-am-note">Changes save to the server as soon as you make them.</p>
        </aside>
      </div>
    </>
  )
}
