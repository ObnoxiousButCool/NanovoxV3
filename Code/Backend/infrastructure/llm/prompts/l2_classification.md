---
id: l2_classification
version: 1.1.0
description: L2 — outcome, category, product lines, complaint, intent, escalation detection, broker mention, touchpoint, a short summary, primary/secondary issue and impact scope.
---
You are classifying one call for a health-benefits call centre (ChoiceBuilder). Read the transcript below and answer strictly according to the schema. Every claim you make must be something a reader could check against the transcript.

TRANSCRIPT (turn 0 first):
{transcript}

Answer these fields:

**outcome** — one of RESOLVED, PARTIALLY_RESOLVED, ESCALATED, UNRESOLVED. Apply these tests in order and stop at the first that holds:
1. ESCALATED: is there a named owner outside the agent's own authority, a reference number, and a committed timeframe — all three? If yes, ESCALATED.
2. PARTIALLY_RESOLVED: was at least one substantive question answered, AND does at least one committed action remain with a named owner and a timeframe? If both, PARTIALLY_RESOLVED.
3. RESOLVED: at disconnect, is there any open action owed by anyone (the agent, Choice, a carrier, a broker)? If no, RESOLVED.
4. Otherwise UNRESOLVED — the caller's issue is materially unchanged and nothing is owed.
A call handled politely and correctly can still be UNRESOLVED if the caller is left unable to act. A dependency on a third party like a carrier is PARTIALLY_RESOLVED, not ESCALATED — escalation means ownership moved inside the organisation to someone with authority the agent lacks.

**category** — the single best-fitting value: Coverage & Benefits, Claims & EOB, Provider Network, Billing & Premium, Enrollment & ID Cards, Life & Beneficiary, Broker Conduct.

**product_lines** — every line this call touches, zero or more of: dental, vision, life, chiro, program. Shares can exceed 100% of calls; list every line genuinely discussed.

**complaint** — {{present: bool, attributed_to}}. attributed_to is one of CHOICE, BROKER, CARRIER, PROVIDER when present is true, or NONE when it is false. A complaint is dissatisfaction the caller directs at a party's conduct or failure, not merely an unwelcome answer.

**intent** — every verbatim statement of expansion (wanting more coverage), market_test (going out to bid, comparing quotes) or cancellation (leaving, terminating) language, each with its exact quote and the turn number it came from (0-indexed). Only what was actually said — inferred intent is an opinion, not a fact, and must be left out.

**escalation_triggered** — did this call contain a condition that would warrant escalation, independent of whether the agent actually escalated it? Triggers include: the caller explicitly asking for a supervisor; a compliance exception on the call; a disputed document or signature; verbatim exit or market-test language; a health or safety situation; a benefit dispute with care already booked within days; a billing action beyond ordinary authority; broker conduct adversely affecting the caller, named aloud.

**escalation_requested_by_caller** — did the caller explicitly ask, in their own words, for a supervisor, a manager or someone senior? True only when the words say so.

**broker_named_aloud** — {{present, broker_ref, sentiment}}. True only when the caller actually names their broker or brokerage. broker_ref is the business reference of the broker as best you can identify it from the name spoken (e.g. "BRK-02") — leave it empty if you cannot tie the name to a specific broker. sentiment is ADVERSE when the broker is described as having caused a problem, POSITIVE when described as having helped, or NONE when present is false.

**touchpoint** — where in the member/employer journey this call's issue originated, if you can tell (a point such as enrolment, a renewal, a denial letter, a billing statement) — a short lowercase snake_case reference, or empty string if you cannot tell.

**summary** — one or two plain sentences describing what happened on the call.

**primary_issue** — what this call is fundamentally about, in a few plain words (e.g. "claims & eob", "missing ID card"). Not the same axis as `category` or commercial `intent` — a call can be primarily about a denial and secondarily about a card and a dependent. Empty string only if the call genuinely has no identifiable issue.

**secondary_issues** — every other issue the call also raised, besides `primary_issue`. Zero or more short phrases, same style as `primary_issue`. Empty list if there is nothing else.

**impact_scope** — how many people the caller says are affected, one of: `1_member` (just the caller/one member), `1_group` (one employer group as a whole, not a headcount), `n_employees` (a stated number of employees), `n_members_and_dependents` (a stated number of members plus their dependents). Use `n_employees` or `n_members_and_dependents` only when the caller states or clearly implies a number greater than one — e.g. "eleven of my people cannot find a provider" — and put that number in `impact_scope_count`. Otherwise use `1_member` or `1_group` and leave `impact_scope_count` at 0.
