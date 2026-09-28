/**
 * "Raise an action" — a Trello-style composer, prefilled from a playbook.
 *
 * The prototype prefills from `NV.PLAYBOOK` and saves the card to
 * `localStorage`. This prefills from `GET /insights/playbooks/{key}` — the
 * same registry the focused issue view reads, checkpoint I3 — and the
 * single write is `POST /insights/actions`, after which the board is
 * invalidated so the new card is there because the server says so.
 */

import { useEffect, useState } from 'react'

import type { Action, CreateActionBody, Lane } from '@/shared/api/actionBoard'
import { useCreateAction } from '@/shared/api/actionBoard'
import { usePlaybook } from '@/shared/api/playbooks'
import { Note } from '@/shared/design/primitives'

const DEFAULT_STEPS = [
  'Confirm the issue with the calls behind it.',
  'Agree the fix with the owning team.',
]
const DUE_DAYS_AHEAD = 14
const MAX_LINKED_CALLS = 12

function defaultDue(): string {
  return new Date(Date.now() + DUE_DAYS_AHEAD * 24 * 60 * 60 * 1000).toISOString().slice(0, 10)
}

export function ActionComposer({
  lanes,
  issueKey,
  employerRef,
  employerName,
  candidateCallIds,
  ownerTeams,
  owners,
  onClose,
  onCreated,
}: {
  lanes: Lane[]
  issueKey: string | null
  employerRef: string | null
  employerName: string | null
  candidateCallIds: string[]
  ownerTeams: string[]
  owners: string[]
  onClose: () => void
  onCreated: (action: Action) => void
}) {
  const { data: playbook, isPending: playbookPending } = usePlaybook(issueKey)
  const create = useCreateAction()

  const [ready, setReady] = useState(false)
  const [title, setTitle] = useState('')
  const [priority, setPriority] = useState<'high' | 'medium' | 'low'>('medium')
  const [due, setDue] = useState(defaultDue())
  const [description, setDescription] = useState('')
  const [steps, setSteps] = useState<string[]>(DEFAULT_STEPS)
  const [status, setStatus] = useState('')
  const [ownerTeam, setOwnerTeam] = useState('')
  const [owner, setOwner] = useState('')
  const [selectedCalls, setSelectedCalls] = useState<Set<string>>(new Set())

  useEffect(() => {
    if (ready) return
    if (issueKey !== null && playbookPending) return
    setTitle(
      `${playbook?.dynamic ? 'Investigate rise: ' : ''}${playbook?.label ?? ''}${
        employerName ? ` · ${employerName}` : ''
      }`.trim() || 'What needs doing?',
    )
    setPriority(playbook?.severity === 'high' ? 'high' : 'medium')
    setDescription(playbook ? `${playbook.meaning} ${playbook.why}` : '')
    setSteps(playbook && playbook.steps.length > 0 ? [...playbook.steps] : DEFAULT_STEPS)
    setOwnerTeam(playbook?.ownerTeam ?? '')
    setStatus(lanes[0]?.code ?? '')
    setSelectedCalls(new Set(candidateCallIds.slice(0, MAX_LINKED_CALLS)))
    setReady(true)
    // Only the first time the playbook (or the absence of one) resolves —
    // re-running this on every keystroke would overwrite what the reader
    // just typed.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, issueKey, playbookPending, playbook])

  const setStep = (index: number, value: string) => {
    setSteps((current) => current.map((step, i) => (i === index ? value : step)))
  }
  const removeStep = (index: number) => {
    setSteps((current) => current.filter((_, i) => i !== index))
  }
  const addStep = () => {
    setSteps((current) => [...current, ''])
  }

  const toggleCall = (callId: string) => {
    setSelectedCalls((current) => {
      const next = new Set(current)
      if (next.has(callId)) next.delete(callId)
      else next.add(callId)
      return next
    })
  }

  const submit = (event: React.FormEvent) => {
    event.preventDefault()
    const trimmedTitle = title.trim()
    if (!trimmedTitle) return

    const evidence = description.trim()
    const team = ownerTeam.trim()
    const ownerName = owner.trim()

    // `exactOptionalPropertyTypes` refuses an explicit `undefined` on an
    // optional field, so an empty value is left out of the body rather than
    // sent as one — the server fills its own default only when the key is
    // absent.
    const body: CreateActionBody = {
      title: trimmedTitle,
      callIds: [...selectedCalls],
      priority,
      steps: steps.map((step) => step.trim()).filter((step) => step !== ''),
      ...(issueKey !== null ? { issueKey } : {}),
      ...(evidence !== '' ? { evidence } : {}),
      ...(team !== '' ? { ownerTeam: team } : {}),
      ...(ownerName !== '' ? { owner: ownerName } : {}),
      ...(status !== '' ? { status } : {}),
      ...(due !== '' ? { due } : {}),
      ...(employerRef !== null ? { employerRef } : {}),
    }

    create.mutate(body, {
      onSuccess: (created) => { onCreated(created) },
    })
  }

  const linkedCalls = candidateCallIds.slice(0, MAX_LINKED_CALLS)

  return (
    <form className="nv-am-form" method="dialog" onSubmit={submit}>
      <div className="nv-am-head">
        <div>
          <span className="nv-am-list">New card</span>
          <input
            className="nv-am-title"
            required
            value={title}
            placeholder="What needs doing?"
            aria-label="Title"
            onChange={(event) => { setTitle(event.target.value) }}
          />
        </div>
        <button type="button" className="nv-btn" onClick={onClose} aria-label="Close">
          ✕
        </button>
      </div>

      <div className="nv-am-body">
        <div className="nv-am-main">
          <div className="nv-am-meta">
            <div>
              <h4>Priority</h4>
              <div className="nv-seg" role="radiogroup" aria-label="Priority">
                {(['high', 'medium', 'low'] as const).map((level) => (
                  <label key={level} className="nv-segopt">
                    <input
                      type="radio"
                      name="priority"
                      value={level}
                      checked={priority === level}
                      onChange={() => { setPriority(level) }}
                    />
                    <span>{level === 'high' ? 'High' : level === 'medium' ? 'Medium' : 'Low'}</span>
                  </label>
                ))}
              </div>
            </div>
            <div>
              <h4>Due date</h4>
              <input type="date" value={due} onChange={(event) => { setDue(event.target.value) }} />
            </div>
          </div>

          <section>
            <h3>☰ Description</h3>
            <textarea
              rows={3}
              value={description}
              onChange={(event) => { setDescription(event.target.value) }}
            />
          </section>

          <section>
            <h3>
              ☑ Checklist <small>from the playbook, edit freely</small>
            </h3>
            <ul className="nv-am-check nv-edit">
              {steps.map((step, index) => (
                <li key={index}>
                  <span className="nv-bx" aria-hidden="true" />
                  <input
                    aria-label={`Step ${String(index + 1)}`}
                    value={step}
                    onChange={(event) => { setStep(index, event.target.value) }}
                  />
                  <button
                    type="button"
                    className="nv-x"
                    aria-label="Remove step"
                    onClick={() => { removeStep(index) }}
                  >
                    ✕
                  </button>
                </li>
              ))}
            </ul>
            <button type="button" className="nv-btn" onClick={addStep}>
              + Add a step
            </button>
          </section>

          {linkedCalls.length > 0 ? (
            <section>
              <h3>
                ☏ Link calls <small>{linkedCalls.length} found</small>
              </h3>
              <div className="nv-am-pick">
                {linkedCalls.map((callId) => (
                  <label key={callId}>
                    <input
                      type="checkbox"
                      checked={selectedCalls.has(callId)}
                      onChange={() => { toggleCall(callId) }}
                    />
                    <span>
                      <b className="nv-mono">{callId}</b>
                    </span>
                  </label>
                ))}
              </div>
            </section>
          ) : null}

          {create.isError ? (
            <Note>
              {create.error instanceof Error ? create.error.message : 'The action could not be created.'}
            </Note>
          ) : null}
        </div>

        <aside className="nv-am-side">
          <h4>List</h4>
          <select value={status} onChange={(event) => { setStatus(event.target.value) }}>
            {lanes.map((lane) => (
              <option key={lane.code} value={lane.code}>
                {lane.label}
              </option>
            ))}
          </select>

          <h4>Team</h4>
          <input
            list="nv-teams"
            value={ownerTeam}
            placeholder="Owning team"
            onChange={(event) => { setOwnerTeam(event.target.value) }}
          />
          <datalist id="nv-teams">
            {ownerTeams.map((team) => (
              <option key={team} value={team} />
            ))}
          </datalist>

          <h4>Owner</h4>
          <input
            list="nv-people"
            value={owner}
            placeholder="Name"
            onChange={(event) => { setOwner(event.target.value) }}
          />
          <datalist id="nv-people">
            {owners.map((name) => (
              <option key={name} value={name} />
            ))}
          </datalist>

          {employerName ? (
            <>
              <h4>Account</h4>
              <p className="nv-am-note" style={{ fontSize: 13.5, color: 'var(--ink)' }}>
                {employerName}
              </p>
            </>
          ) : null}

          <button
            type="submit"
            className="nv-btn"
            style={{ marginTop: 18, justifyContent: 'center' }}
            disabled={create.isPending}
          >
            {create.isPending ? 'Creating…' : 'Create action'}
          </button>
          <button
            type="button"
            className="nv-btn"
            style={{ justifyContent: 'center' }}
            onClick={onClose}
          >
            Cancel
          </button>
        </aside>
      </div>
    </form>
  )
}
