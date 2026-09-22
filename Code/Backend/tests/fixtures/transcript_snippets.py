"""Small, real snippets extracted from the corpus transcripts PDF (plan §3.2),
exactly as `pypdf` extracts them (interpunct `·` and em-dash `—` separators,
a leading space before the second speaker's label). All content is
fictional per the plan's own Context section.

`C0001_RAW_BLOCK` is call C-0001 verbatim, used across the stripper,
speaker-resolution and leak tests — it's the one call the plan calls out by
name (§11's known trap; the caller resolution regression test).
"""

from __future__ import annotations

C0001_RAW_BLOCK = (
    "C-0001 — Claims & EOB\n"
    "Mon 06 Jul 2026 09:14 · AHT 6m 20s · Competent and resolved · rules C-12, P-14\n"
    "MEMBER · CB-7700205 | RESOLVED | score 91/100 | agent AGT-01|Sarah Whitlock\n"
    "Sarah: Choice Administrators, Sarah speaking. This call may be recorded for quality and "
    "training. Can I take your name and\n"
    "member ID?\n"
    " Leon: Leon Castellano. CB-7700205.\n"
    "Sarah: Thanks Leon, I have you.\n"
    " Leon: I had a crown done three weeks ago and the claim's come back denied. The letter "
    "just says ineligible. I've been paying in\n"
    "since March.\n"
    "Sarah: Let me pull the claim and your enrolment together, because I think those two "
    "things explain each other. One moment...\n"
    "right. Effective the first of March, crown on the twenty-third of June.\n"
    " Leon: That's right.\n"
    "Sarah: There are two different waiting periods on a dental plan and I think you've hit "
    "the second one. The first is your employer's —\n"
    "that's the one you clear when you join, and you cleared it in March. The second is on "
    "the plan itself and applies only to major work.\n"
    "Crowns, bridges, dentures. Yours is twelve months from your effective date.\n"
    " Leon: So next March.\n"
    "Sarah: First of March, yes.\n"
    " Leon: Nobody told me that. I asked at sign-up whether I was covered and they said yes.\n"
    "Sarah: And that was true as far as it went — cleanings and exams have been available to "
    "you since March. It's the major work that\n"
    "waits, and that distinction almost never gets made at the point somebody signs up.\n"
    " Leon: So I'm out eleven hundred dollars.\n"
    "Sarah: For that one, yes, and I'm not going to pretend otherwise. Is there more work "
    "planned?\n"
    " Leon: He mentioned a second crown. Not urgent.\n"
    "Sarah: Then that matters. Done after the first of March it's covered at fifty percent, "
    "so roughly half of what you've just paid. I'd rather\n"
    "you knew now than found out afterwards.\n"
    " Leon: Alright. That is useful.\n"
    "Sarah: I'm emailing you both dates in writing, and I'm logging that the denial letter "
    "should say which waiting period applied and\n"
    "when it ends. It said ineligible and stopped, and that's not good enough.\n"
    " Leon: Thank you for actually explaining it.\n"
    "CALL TAGS\n"
    " outcome   RESOLVED\n"
    "category   Claims & EOB\n"
    "product_lines   dental\n"
    "complaint   present|CHOICE\n"
    "signals   member_communication_gap|MEDIUM|Member Communications\n"
    "escalation   triggered false\n"
    "control_exceptions   none\n"
    "knowledge_failure   present|C-12|major-service waiting period is a plan feature, "
    "separate from the employer's new-hire period\n"
    "intent   none\n"
    "process_gap   present|denial letter should name the waiting period and the eligibility "
    "date|denial_letter_eob|AGENT|UNVALIDATED\n"
    "touchpoint   denial_letter_eob\n"
    "quality_score   91\n"
    "aht_seconds   380\n"
    "caller_ref   CB-7700205\n"
    "broker_named_aloud   absent"
)

# A synthetic block reproducing the blank-line-after-title anomaly that
# batch 1 actually has (calls C-0033, C-0046, C-0064) — content invented,
# structure real.
C0999_RAW_BLOCK_WITH_BLANK_HEADER_LINE = (
    "C-0999 — Provider Network\n"
    "\n"
    "Mon 27 Jul 2026 11:25 · AHT 2m 00s · Competent and resolved · rules —\n"
    "EMPLOYER · CON-118 | RESOLVED | score 90/100 | agent AGT-07|Linda Braithwaite\n"
    "Linda: Choice Administrators, Linda speaking. How can I help?\n"
    " Priya: Quick question about the network.\n"
    "Linda: Go ahead.\n"
    " Priya: Never mind, found it.\n"
    "CALL TAGS\n"
    " outcome   RESOLVED\n"
    "caller_ref   CON-118"
)
