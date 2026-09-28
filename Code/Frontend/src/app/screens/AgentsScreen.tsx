/**
 * `/agents` — "How are agents handling calls?"
 *
 * The last dead entry in the rail. `Prototype/v2/agents.html`, with the two
 * panels our data can honestly fill.
 *
 * ## An event can name a person; an average cannot
 *
 * This is the whole shape of the page, and it is the prototype's own
 * reasoning: *"A compliance exception is a breach on that call, whatever
 * the sample. So are a rule stated wrongly and a warranted escalation not
 * given. These can be attributed to a person at any volume; averages
 * cannot."*
 *
 * So events are counted per agent at any volume, and a **score** is
 * withheld until the agent has enough calls to carry one. The API decides
 * that, not this screen: `quality.medianScore` arrives null with a caveat,
 * and the roster prints the caveat rather than a dash.
 *
 * ## Two prototype panels are absent, and neither is an oversight
 *
 * **"Coach the agent, or fix the rule?"** needs, per rule, how many
 * distinct agents misstated it. `AgentResponse.knowledgeErrors` is a list
 * of *calls*, not of rules, so the join does not exist on this endpoint.
 * The question has a home already — **C5 (D14)** rules that `/rules` ships
 * and is reachable from here — so this page links to it rather than
 * rebuilding half of it from the wrong field.
 *
 * **"By experience level"** groups agents by band to recover the sample one
 * agent lacks. No band reaches the wire: `AgentResponse` carries a
 * reference and nothing else about the person. Grouping by anything else
 * would be inventing the grouping.
 */

import { Link } from 'react-router-dom'

import { useAgents } from '@/shared/api/insights'
import type { Agent, Agents } from '@/shared/api/insights'
import { IssueValue } from '@/shared/actions/IssueLink'
import { useFilters } from '@/shared/filters/useFilters'
import { Screen } from '@/shared/screens/Screen'
import {
  BigRow,
  Empty,
  EpistemicChip,
  KpiTile,
  Note,
  Panel,
  Withheld,
} from '@/shared/design/primitives'

/** Compliance exceptions are counted per call, across every type. */
function exceptions(agent: Agent): number {
  return agent.controlExceptions.reduce((total, entry) => total + entry.calls, 0)
}

function events(agent: Agent): number {
  return exceptions(agent) + agent.knowledgeErrors.length + agent.escalationsMissed.length
}

function scored(agent: Agent): boolean {
  return agent.quality.medianScore !== null && agent.quality.medianScore !== undefined
}

export function AgentsScreen() {
  const filters = useFilters()
  const { data, isPending, error } = useAgents(filters.apiSearch)

  return (
    <Screen
      title="How are agents handling calls?"
      lede="Events that can be attributed to a person at any volume, and a score only where there are enough calls to carry one."
      scope={data?.scope}
      isPending={isPending}
      error={error}
    >
      {data === undefined ? null : <AgentsBody data={data} />}
    </Screen>
  )
}

function AgentsBody({ data }: { data: Agents }) {
  const agents = data.agents
  const withEvents = agents
    .filter((agent) => events(agent) > 0)
    .sort((a, b) => events(b) - events(a) || a.agentRef.localeCompare(b.agentRef))
  const scoredCount = agents.filter(scored).length

  const total = (pick: (agent: Agent) => number) =>
    agents.reduce((sum, agent) => sum + pick(agent), 0)

  return (
    <div className="nv-grid">
      <div className="nv-c12">
        <Panel
          title="Conduct events in the window"
          sub={`Counted over ${String(data.windowWeeks)} weeks, ending ${data.asOf}.`}
          chip={<EpistemicChip kind="observed" />}
        >
          <BigRow>
            <KpiTile
              label="Compliance exceptions"
              value={
                <IssueValue issue="control_exception">{String(total(exceptions))}</IssueValue>
              }
              meta={<span className="nv-indcount">breaches on a specific call</span>}
            />
            <KpiTile
              label="Rules stated wrongly"
              value={
                <IssueValue issue="knowledge_failure">
                  {String(total((agent) => agent.knowledgeErrors.length))}
                </IssueValue>
              }
              meta={
                <span className="nv-indcount">
                  across {String(agents.filter((a) => a.knowledgeErrors.length > 0).length)}{' '}
                  agents
                </span>
              }
            />
            <KpiTile
              label="Escalations missed"
              value={
                <IssueValue issue="escalation_missed">
                  {String(total((agent) => agent.escalationsMissed.length))}
                </IssueValue>
              }
              meta={<span className="nv-indcount">warranted, not given</span>}
            />
            <KpiTile
              label="Agents with a score"
              value={`${String(scoredCount)} of ${String(agents.length)}`}
              // The reason this is a tile rather than a footnote: at batch
              // volume it is usually zero, and a reader should see that the
              // absence is a sample rule rather than a missing feature.
              // The meta line has to follow the number: "the rest have too
              // few calls" is false when there is no rest, and a tile that
              // contradicts itself is worse than one with no meta at all.
              meta={
                <span className="nv-indcount">
                  {scoredCount === agents.length
                    ? 'every agent has enough calls'
                    : `${String(agents.length - scoredCount)} have too few calls to publish one`}
                </span>
              }
            />
          </BigRow>
        </Panel>
      </div>

      <div className="nv-c12">
        <Panel
          title="Issues by agent"
          sub="Agents with at least one event, most first. A number opens what to do about it."
          chip={<EpistemicChip kind="observed" />}
        >
          {withEvents.length === 0 ? (
            <Empty title="No conduct events in this period">
              No compliance exception, misstated rule or missed escalation was recorded
              against any agent in scope.
            </Empty>
          ) : (
            <table className="nv-risktable">
              <thead>
                <tr>
                  <th scope="col">Agent</th>
                  <th scope="col" className="nv-num">
                    Calls
                  </th>
                  <th scope="col" className="nv-num">
                    Compliance
                  </th>
                  <th scope="col" className="nv-num">
                    Rule stated wrongly
                  </th>
                  <th scope="col" className="nv-num">
                    Escalation missed
                  </th>
                  <th scope="col" className="nv-num">
                    Total
                  </th>
                </tr>
              </thead>
              <tbody>
                {withEvents.map((agent) => (
                  <tr key={agent.agentRef}>
                    <td>
                      <span className="nv-mono">{agent.agentRef}</span>
                    </td>
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
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>
      </div>

      <div className="nv-c12">
        <Panel
          title="The roster"
          sub="Every agent with calls in the window, scored or not."
          chip={<EpistemicChip kind="observed" />}
        >
          {agents.length === 0 ? (
            <Empty title="No agent has a call in this period">
              Widen the period to see the roster.
            </Empty>
          ) : (
            <table className="nv-risktable">
              <thead>
                <tr>
                  <th scope="col">Agent</th>
                  <th scope="col" className="nv-num">
                    Calls
                  </th>
                  <th scope="col" className="nv-num">
                    Scored calls
                  </th>
                  <th scope="col">Median quality</th>
                </tr>
              </thead>
              <tbody>
                {[...agents]
                  .sort((a, b) => b.calls.length - a.calls.length)
                  .map((agent) => (
                    <tr key={agent.agentRef}>
                      <td>
                        <span className="nv-mono">{agent.agentRef}</span>
                      </td>
                      <td className="nv-num">{agent.calls.length}</td>
                      <td className="nv-num">{agent.quality.scoredCalls.length}</td>
                      <td>
                        {scored(agent) ? (
                          <b>{agent.quality.medianScore}</b>
                        ) : (
                          // The API's own caveat, not wording invented here:
                          // "too few calls" and "none were scored" are
                          // different facts and only one is fixed by waiting.
                          <Withheld caveats={[agent.quality.caveat]} />
                        )}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          )}
        </Panel>
      </div>

      <div className="nv-c12">
        <Note>
          A rule more than one agent states wrongly is more likely a problem with the rule
          than with the agents. That comparison needs the rule behind each error, which this
          endpoint does not carry — it is on <Link to="/rules">the rules we fail to explain</Link>.
        </Note>
      </div>
    </div>
  )
}

/** A count that links to its playbook, or a plain zero that does not. */
function Count({
  value,
  issue,
  agent,
}: {
  value: number
  issue: 'control_exception' | 'knowledge_failure' | 'escalation_missed'
  agent: string
}) {
  if (value === 0) return <span className="nv-acct-none">0</span>
  return (
    <IssueValue issue={issue} scope={{ agent }}>
      {String(value)}
    </IssueValue>
  )
}
