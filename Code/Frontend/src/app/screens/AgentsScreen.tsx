/**
 * `/agents` — "How are agents handling calls?", as `agents.html` has it.
 *
 * ## An event can name a person; an average cannot
 *
 * The whole shape of the page, and the prototype's own reasoning: *"A
 * compliance exception is a breach on that call, whatever the sample. So
 * are a rule stated wrongly and a warranted escalation not given. These
 * can be attributed to a person at any volume; averages cannot."*
 *
 * So events are counted per agent at any volume, and a **score** is
 * withheld until the agent has enough calls to carry one. The API decides
 * that, not this screen, and the roster's coverage bar shows how far off
 * everyone is rather than leaving the withholding unexplained.
 *
 * ## The expected score is design input and is labelled as one
 *
 * The roster was written before the calls and the corpus was generated
 * from it, so an agent matching their expected score is the data agreeing
 * with itself. It sits in the roster beside what happened, and the panel
 * says so in words.
 *
 * ## One prototype panel asks a question this page refuses to answer
 *
 * **"Coach the agent, or fix the rule?"** asks how many distinct agents got
 * each rule wrong. That answer comes from schema field 8, which **D7
 * forbids attributing to an agent anywhere**; the `knowledge_error` signal
 * is the agent-conduct event and carries no rule id.
 *
 * The panel is **rendered, and withheld in words** — the question, why it
 * cannot be joined, and a link to `/rules`, where the rule-level counts do
 * live. It was absent entirely until `/rules` shipped, and dropping a
 * panel the prototype has is indistinguishable, to a reader, from
 * forgetting it.
 */

import { Link } from 'react-router-dom'

import { useAgents, useGeneratedInsights } from '@/shared/api/insights'
import type { Agent, Agents } from '@/shared/api/insights'
import { IssueCue, IssueValue } from '@/shared/actions/IssueLink'
import { InsightStrip } from '@/shared/insights/Insights'
import { useDrawer } from '@/shared/design/drawer'
import { CallList } from '@/shared/design/drawer/Evidence'
import { useFilters } from '@/shared/filters/useFilters'
import { Screen } from '@/shared/screens/Screen'
import {
  Empty,
  EpistemicChip,
  KpiTile,
  Panel,
  Tooltip,
} from '@/shared/design/primitives'

type Roster = Agents['roster'][number]
type Band = Agents['bands'][number]

/** Compliance exceptions are counted per call, across every type. */
function exceptions(agent: Agent): number {
  return agent.controlExceptions.reduce((total, entry) => total + entry.calls, 0)
}

function events(agent: Agent): number {
  return exceptions(agent) + agent.knowledgeErrors.length + agent.escalationsMissed.length
}

/**
 * Whether this agent has enough calls for a figure of their own.
 *
 * Not "has a scored call": `agent_quality` returns a median over whatever
 * was scored, however little, and carries a caveat saying a distribution
 * that small separates nobody. The tile above the page counts the agents
 * who have cleared the roster's own bar, which is the page's finding —
 * counting the other thing produced "20 of 20 have a score" over "busiest
 * has 5 of 30 calls", a tile disagreeing with its own meta line.
 */
function clearsTheBar(agent: Agent, minimum: number | null | undefined): boolean {
  if (minimum === null || minimum === undefined) return false
  return agent.calls.length >= minimum
}

export function AgentsScreen() {
  const filters = useFilters()
  const { data, isPending, error } = useAgents(filters.apiSearch)
  // `agents.html` opens with the strip. Its own query, so the events never
  // wait on a model.
  const insights = useGeneratedInsights('agents', filters.apiSearch)

  return (
    <Screen
      title="How are agents handling calls?"
      lede={
        data === undefined
          ? 'Conduct events by agent: disclosures missed, rules explained wrongly and escalations not given.'
          : `Tracks conduct events by agent: disclosures missed, rules explained wrongly and escalations not given. Per-agent scores are held back until each agent has ${String(data.minCallsForARate ?? 0)} calls, so nobody is judged on a handful.`
      }
      compactFilters
      scope={data?.scope}
      isPending={isPending}
      error={error}
    >
      {data === undefined ? null : <AgentsBody data={data} insights={insights} />}
    </Screen>
  )
}

function AgentsBody({
  data,
  insights,
}: {
  data: Agents
  insights: ReturnType<typeof useGeneratedInsights>
}) {
  const agents = data.agents
  const names = new Map(data.roster.map((entry) => [entry.agentRef, entry]))
  const withEvents = agents
    .filter((agent) => events(agent) > 0)
    .sort(
      (a, b) =>
        events(b) - events(a) || exceptions(b) - exceptions(a) || a.agentRef.localeCompare(b.agentRef),
    )

  return (
    <div className="nv-grid">
      <div className="nv-c12">
        <InsightStrip data={insights.data} pending={insights.isFetching} />
      </div>

      <div className="nv-c12">
        <AgentTiles data={data} />
      </div>

      <div className="nv-c12">
        <IssuesByAgent agents={withEvents} names={names} />
      </div>

      <div className="nv-c6">
        <CoachOrRewrite />
      </div>

      <div className="nv-c6">
        <ByBand bands={data.bands} unavailable={data.complexityUnavailable} />
      </div>

      <div className="nv-c12">
        <FullRoster data={data} />
      </div>
    </div>
  )
}

/**
 * The four tiles, all totals over the same window as the table below them.
 *
 * The fourth is the page's real finding at batch-1 volume: nobody has
 * enough calls for a score. It carries the withheld tone rather than a
 * warm one, because "nought of twenty" here is a sample rule working, not
 * something anybody did wrong.
 */
function AgentTiles({ data }: { data: Agents }) {
  const totals = {
    exceptions: data.agents.reduce((sum, agent) => sum + exceptions(agent), 0),
    rules: data.agents.reduce((sum, agent) => sum + agent.knowledgeErrors.length, 0),
    escalations: data.agents.reduce((sum, agent) => sum + agent.escalationsMissed.length, 0),
  }
  const withRules = data.agents.filter((agent) => agent.knowledgeErrors.length > 0).length
  const scoredCount = data.agents.filter((agent) => clearsTheBar(agent, data.minCallsForARate)).length
  const busiest = data.agents.reduce((most, agent) => Math.max(most, agent.calls.length), 0)
  const minimum = data.minCallsForARate

  return (
    <div className="nv-bigrow">
      <KpiTile
        label="Compliance exceptions"
        value={String(totals.exceptions)}
        meta={<span className="nv-indcount">breaches on a specific call</span>}
        tone={totals.exceptions > 0 ? 'hot' : 'plain'}
        todo={totals.exceptions > 0 ? <IssueCue issue="control_exception" /> : undefined}
      />
      <KpiTile
        label="Rules stated wrongly"
        value={String(totals.rules)}
        meta={<span className="nv-indcount">across {withRules} agents</span>}
        tone={totals.rules > 0 ? 'warm' : 'plain'}
        todo={totals.rules > 0 ? <IssueCue issue="knowledge_failure" /> : undefined}
      />
      <KpiTile
        label="Escalations missed"
        value={String(totals.escalations)}
        meta={
          <span className="nv-indcount">
            {data.escalationsRefused.length} where the caller asked
          </span>
        }
        tone={totals.escalations > 0 ? 'hot' : 'plain'}
        todo={totals.escalations > 0 ? <IssueCue issue="escalation_missed" /> : undefined}
      />
      <KpiTile
        label="Agents with a score"
        value={`${String(scoredCount)} of ${String(data.agents.length)}`}
        meta={
          <span className="nv-indcount">
            {minimum === null || minimum === undefined
              ? 'no minimum is set for an agent-level rate'
              : `busiest has ${String(busiest)} of ${String(minimum)} calls`}
          </span>
        }
        tone="withheld"
        info={
          <Tooltip>
            <p>
              The roster sets {minimum ?? '—'} calls as the minimum for an agent-level rate.
              At batch-1 volume no agent is there yet, so per-agent scores are withheld
              rather than shown on a handful of calls.
            </p>
          </Tooltip>
        }
      />
    </div>
  )
}

function IssuesByAgent({
  agents,
  names,
}: {
  agents: Agent[]
  names: Map<string, Roster>
}) {
  const { open } = useDrawer()

  return (
    <Panel
      title="Issues by agent"
      sub="Agents with at least one event, most first. Select an agent for their calls; select a number for what to do."
      info={
        <Tooltip>
          <p>
            A <b>compliance exception</b> is a breach on that call, whatever the sample. So
            are a rule stated wrongly and a warranted escalation not given. These can be
            attributed to a person at any volume; averages cannot.
          </p>
        </Tooltip>
      }
      chip={<EpistemicChip kind="observed" />}
    >
      {agents.length === 0 ? (
        <Empty title="No conduct events in this period">
          No compliance exception, misstated rule or missed escalation was recorded against
          any agent in scope.
        </Empty>
      ) : (
        <div className="nv-tblwrap">
          <table>
            <caption className="nv-visually-hidden">Conduct events by agent</caption>
            <thead>
              <tr>
                <th scope="col">Agent</th>
                <th className="nv-num" scope="col">
                  Calls
                </th>
                <th className="nv-num" scope="col">
                  Compliance
                </th>
                <th className="nv-num" scope="col">
                  Rule stated wrongly
                </th>
                <th className="nv-num" scope="col">
                  Escalation missed
                </th>
                <th className="nv-num" scope="col">
                  Total
                </th>
              </tr>
            </thead>
            <tbody>
              {agents.map((agent) => {
                const entry = names.get(agent.agentRef)
                const everyCall = exceptions(agent) === agent.calls.length && agent.calls.length > 1
                return (
                  <tr
                    key={agent.agentRef}
                    className="nv-clickable"
                    tabIndex={0}
                    onClick={(event) => {
                      if ((event.target as HTMLElement).closest('a, button')) return
                      open({
                        title: entry?.name ?? agent.agentRef,
                        chip: 'observed',
                        body: <AgentDrawer agent={agent} entry={entry} />,
                      })
                    }}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault()
                        open({
                          title: entry?.name ?? agent.agentRef,
                          chip: 'observed',
                          body: <AgentDrawer agent={agent} entry={entry} />,
                        })
                      }
                    }}
                  >
                    <th scope="row">
                      <span className="nv-nm">{entry?.name ?? agent.agentRef}</span>
                      <small>{entry?.band ?? agent.agentRef}</small>
                    </th>
                    <td className="nv-num">{agent.calls.length}</td>
                    <td className="nv-num">
                      <Count
                        value={exceptions(agent)}
                        issue="control_exception"
                        agent={agent.agentRef}
                      />
                    </td>
                    <td className="nv-num">
                      <Count
                        value={agent.knowledgeErrors.length}
                        issue="knowledge_failure"
                        agent={agent.agentRef}
                      />
                    </td>
                    <td className="nv-num">
                      <Count
                        value={agent.escalationsMissed.length}
                        issue="escalation_missed"
                        agent={agent.agentRef}
                      />
                    </td>
                    <td className="nv-num">
                      <b>{events(agent)}</b>
                      {everyCall ? <small className="nv-worse">every call</small> : null}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  )
}

function AgentDrawer({ agent, entry }: { agent: Agent; entry: Roster | undefined }) {
  // Each label carries its own plural. The prototype appends an "s",
  // which turns two of these into "escalation misseds" and "rule stated
  // wronglys" — the noun is not the last word.
  const lines = [
    [exceptions(agent), 'compliance exception', 'compliance exceptions'],
    [agent.knowledgeErrors.length, 'rule stated wrongly', 'rules stated wrongly'],
    [agent.escalationsMissed.length, 'escalation missed', 'escalations missed'],
  ] as const

  return (
    <>
      <div>
        <h4>Roster</h4>
        <p>
          {entry?.band ?? 'Band not on the roster'}
          {entry?.expectedScore === null || entry?.expectedScore === undefined
            ? ''
            : ` · expected score ${String(entry.expectedScore)}`}
          {' · '}
          {agent.calls.length} call{agent.calls.length === 1 ? '' : 's'} in the window
        </p>
      </div>
      <div>
        <h4>Events</h4>
        <p>
          {events(agent) === 0
            ? 'None recorded'
            : lines
                .filter(([count]) => count > 0)
                .map(([count, one, many]) => `${String(count)} ${count === 1 ? one : many}`)
                .join(' · ')}
        </p>
      </div>
      <div>
        <h4>Calls</h4>
        <CallList callIds={agent.calls} />
      </div>
    </>
  )
}

/**
 * The prototype's "Coach the agent, or fix the rule?", and why it is a
 * pointer rather than a panel.
 */
function CoachOrRewrite() {
  return (
    <Panel
      title="Coach the agent, or fix the rule?"
      sub="Rules stated wrongly on calls, and what that suggests."
      info={
        <Tooltip>
          <p>
            A rule one agent gets wrong is probably training. The same rule misstated by{' '}
            <b>more than one</b> agent, especially across bands, points at the rule&rsquo;s
            own wording.
          </p>
          <p>
            Answering it needs schema field 8 joined to the agent who took the call.{' '}
            <b>D7</b> is open on exactly that join and forbids attributing field 8 to an
            agent anywhere, so this page does not make it — the `knowledge_error` signal is
            the agent-conduct event and carries no rule id.
          </p>
        </Tooltip>
      }
      chip={<EpistemicChip kind="inference" />}
    >
      <Empty title="Not answered here, by decision">
        D7 is open on attributing a misstated rule to an agent. The same failures roll up by
        rule and by touchpoint on <Link to="/rules">the rules we fail to explain</Link>.
      </Empty>
    </Panel>
  )
}

function ByBand({ bands, unavailable }: { bands: Band[]; unavailable: string }) {
  return (
    <Panel
      title="By experience level"
      sub="Grouping recovers the sample one agent lacks."
      info={
        <Tooltip>
          <p>
            A band pools thirty-odd calls, enough to publish a median where one agent&rsquo;s
            handful is not. Admissible where an employer roll-up is not: the Metrics sheet
            forbids averaging metric 12 to employer, product line or broker, and a band is
            none of those.
          </p>
          <p>{unavailable}</p>
        </Tooltip>
      }
      chip={<EpistemicChip kind="observed" />}
    >
      {bands.length === 0 ? (
        <Empty title="No band has a call in this period">
          Widen the period to compare experience levels.
        </Empty>
      ) : (
        <div className="nv-tblwrap">
          <table>
            <caption className="nv-visually-hidden">Events and quality by experience band</caption>
            <thead>
              <tr>
                <th scope="col">Band</th>
                <th className="nv-num" scope="col">
                  Agents
                </th>
                <th className="nv-num" scope="col">
                  Calls
                </th>
                <th className="nv-num" scope="col">
                  Events
                </th>
                <th className="nv-num" scope="col">
                  Hard calls
                </th>
                <th className="nv-num" scope="col">
                  Median quality
                </th>
              </tr>
            </thead>
            <tbody>
              {bands.map((row) => (
                <tr key={row.band}>
                  <th scope="row">
                    <span className="nv-nm">{row.band}</span>
                  </th>
                  <td className="nv-num">{row.agents}</td>
                  <td className="nv-num">{row.calls}</td>
                  <td className="nv-num">
                    {row.events === 0 ? <span className="nv-nd">–</span> : <b>{row.events}</b>}
                  </td>
                  {/* Never a nought: the field does not exist, so the share
                      was not measured rather than measured at zero. */}
                  <td className="nv-num" title={unavailable}>
                    <span className="nv-nd">not measured</span>
                  </td>
                  <td className="nv-num">
                    {row.medianScore === null || row.medianScore === undefined ? (
                      <span className="nv-nd">–</span>
                    ) : (
                      <b>{Math.round(row.medianScore)}</b>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  )
}

/**
 * The whole roster, folded.
 *
 * Folded because it is the reference list rather than the finding: nothing
 * in it is ranked and most of it is agents with nothing against them.
 */
function FullRoster({ data }: { data: Agents }) {
  const byRef = new Map(data.agents.map((agent) => [agent.agentRef, agent]))
  const minimum = data.minCallsForARate

  return (
    <section className="nv-panel">
      <details className="nv-more nv-drill">
        <summary>Full roster · {data.roster.length} agents</summary>
        <p className="nv-lede">
          Scores are withheld per agent until the coverage bar is full. The roster was
          written before the calls, so an agent matching their expected score is the data
          agreeing with itself, not a finding.
        </p>
        {data.roster.length === 0 ? (
          <Empty title="No agent roster in this scope">
            Reference data carries no agent for this period.
          </Empty>
        ) : (
          <div className="nv-tblwrap">
            <table>
              <caption className="nv-visually-hidden">The agent roster</caption>
              <thead>
                <tr>
                  <th scope="col">Agent</th>
                  <th scope="col">Band</th>
                  <th className="nv-num" scope="col">
                    Expected score
                  </th>
                  <th scope="col">Coverage</th>
                  <th className="nv-num" scope="col">
                    Events
                  </th>
                </tr>
              </thead>
              <tbody>
                {[...data.roster]
                  .sort((a, b) => {
                    const left = byRef.get(a.agentRef)
                    const right = byRef.get(b.agentRef)
                    return (
                      (right ? events(right) : 0) - (left ? events(left) : 0) ||
                      (right?.calls.length ?? 0) - (left?.calls.length ?? 0) ||
                      a.agentRef.localeCompare(b.agentRef)
                    )
                  })
                  .map((entry) => {
                    const agent = byRef.get(entry.agentRef)
                    const count = agent ? events(agent) : 0
                    return (
                      <tr key={entry.agentRef}>
                        <th scope="row">
                          <span className="nv-nm">{entry.name}</span>
                        </th>
                        <td>{entry.band}</td>
                        <td className="nv-num">
                          {entry.expectedScore === null || entry.expectedScore === undefined
                            ? '–'
                            : `${String(entry.expectedScore)}${
                                entry.scoreVariance === null || entry.scoreVariance === undefined
                                  ? ''
                                  : ` ± ${String(entry.scoreVariance)}`
                              }`}
                        </td>
                        <td>
                          <Coverage calls={agent?.calls.length ?? 0} minimum={minimum} />
                        </td>
                        <td className="nv-num">
                          {count === 0 ? <span className="nv-nd">–</span> : <b>{count}</b>}
                        </td>
                      </tr>
                    )
                  })}
              </tbody>
            </table>
          </div>
        )}
      </details>
    </section>
  )
}

/**
 * How far an agent is from carrying a rate of their own.
 *
 * With no minimum there is no bar to draw — not a bar that is always
 * full — so the count stands on its own instead.
 */
function Coverage({ calls, minimum }: { calls: number; minimum: number | null | undefined }) {
  if (minimum === null || minimum === undefined) {
    return <span className="nv-indcount">{calls} calls</span>
  }
  const share = Math.min((calls / minimum) * 100, 100)
  return (
    <span className="nv-cov">
      <span className="nv-cov-track">
        <span className="nv-cov-fill" style={{ width: `${String(Math.round(share))}%` }} />
      </span>
      <span className="nv-cov-n">
        {calls}/{minimum}
      </span>
    </span>
  )
}

/** A count that links to its playbook, or a plain dash that does not. */
function Count({
  value,
  issue,
  agent,
}: {
  value: number
  issue: 'control_exception' | 'knowledge_failure' | 'escalation_missed'
  agent: string
}) {
  if (value === 0) return <span className="nv-nd">–</span>
  return (
    <IssueValue issue={issue} tone="warm" scope={{ agent }}>
      {String(value)}
    </IssueValue>
  )
}
