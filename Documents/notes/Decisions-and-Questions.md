# Decisions and Questions — email-OTP login

2026-10-08 · `feature/email-otp-login`, not on main

Ranjit asked for an email-OTP sign-in system: enter an address, get a
6-digit code, enter the code, get in. This is the running record of what
got decided while building it, and what is still genuinely open — kept here
rather than only in commit messages and code comments, so the next person
(including whoever eventually reviews this for main) does not have to
reconstruct the reasoning from a diff.

## Decisions

**The allowlist is a database table, not a config file.** First cut shipped
as `config/approved_emails.yaml`, a developer-edited file matching the
pattern `dashboard.yaml` and `action_lifecycle.yaml` already use. Ranjit
asked for the database route instead (2026-10-08), so it is now the
`approved_emails` table, managed through
`python -m frameworks_drivers.cli.manage_approved_emails` (`add`, `remove`,
`list`). No admin screen yet — see the open question below.

**Email delivery is a swappable adapter, defaulting to a console logger.**
`EmailSender` is a port with two adapters today: `ConsoleEmailSender` (logs
the code instead of mailing it — the default, so the whole flow runs and is
demoable with nothing configured) and `SmtpEmailSender` (stdlib `smtplib`,
works with any account that speaks SMTP). Switching is `EMAIL_BACKEND=smtp`
plus credentials in `.env` — no code change. Which real account to use is
still Ranjit's call (see questions).

**A code is six digits, random, and never stored in plaintext.** Generated
with `secrets` (not `random`), hashed with SHA-256 before it touches the
database, compared with a constant-time check. See
`domain/value_objects/otp_code.py` for why a slow salted KDF (the right
choice for a password) is not the right choice here.

**Requesting a code answers the same way regardless of whether the address
is approved.** `POST /auth/otp/request` always returns the same generic
message. The alternative — a distinct "not approved" response — turns the
endpoint into a way to enumerate who is on the list.

**Verifying a code gives one message for wrong, expired, or never-issued.**
Same reasoning as above, one level in: a caller should not be able to tell
"that code expired" from "no code was ever sent to this address" from "you
got it wrong."

**An OTP expires in 10 minutes, allows 5 attempts, and a resend is throttled
to one per 30 seconds.** All three are settings
(`OTP_EXPIRY_MINUTES`/`OTP_MAX_ATTEMPTS`/`OTP_RESEND_COOLDOWN_SECONDS`), not
hard-coded — defaults chosen as reasonable, not measured against anything.

**Sessions are a signed JWT, no refresh token, 12-hour default lifetime.**
Bearer token in the `Authorization` header, verified by one dependency
(`require_session`) that every router depends on except `/health` and
`/auth` itself — gating is whole-app, not per-route. Chosen over a
cookie-based session to avoid touching the existing CORS configuration
(`allow_credentials=False`) for a POC-stage feature.

**The frontend gates the whole app in one place.** `App.tsx` checks
`isAuthenticated` once and renders either the login screen or everything
else — not a per-route guard. The session is persisted to `localStorage` so
a reload does not sign the reader out, and a 401 on any authenticated
request logs the reader out automatically rather than leaving the screen
stuck retrying a request it can never complete.

**This stays on its own branch.** Ranjit: "let's work on the login page and
keep it in the other branch, let's not merge it to main." Nothing here has
been merged, and nothing should be until that changes.

## Questions — genuinely open

**Which account actually sends the email?** SMTP (a company mailbox, or a
relay like SendGrid's) is the fast path — credentials in, working in hours.
Azure Communication Services fits the existing Azure-first infrastructure
but needs a verified sending domain first, which is a DNS wait measured in
days, separate from any engineering time. This is blocking real email
delivery; the console backend is a stand-in, not a destination.

**How does the allowlist actually get managed day to day?** Right now,
adding or removing an approved address means someone with shell access to
the server runs a CLI command. That is fine for a handful of internal
testers. It is worth asking out loud whether the client is expected to
manage their own list eventually, and if so, whether that needs a real
admin screen rather than a command line — that is a meaningfully bigger
piece of work than anything built so far, so it is worth deciding before it
is assumed either way.

**Is a 12-hour session the right length?** No "remember me," no shorter
option for a shared machine, no longer one for someone who does not want to
re-enter a code daily. Picked as a reasonable default, not requested by
anyone.

**Should a sign-in be logged anywhere a human can see it?** Right now
nothing records who signed in or when, beyond whatever the standard request
log already captures incidentally. If "who has accessed this" ever matters
(and for a system with compliance-adjacent data, it plausibly does), that is
a deliberate gap today.

**Is per-address throttling enough, or does this need IP-based rate
limiting too?** The cooldown and attempt cap stop one address from being
spammed or brute-forced. Nothing stops one caller from doing that across
many different addresses at once. Not a concern for a closed pilot; worth
revisiting before this is reachable by anyone who isn't already trusted.

**The action board's `trustNote` is now wrong.** `GET /insights/actions/board`
still carries the line "there is no sign-in, and anyone who can reach the
service can edit" (D14, R9 — decided before this feature existed). Once
login ships, that sentence is no longer true. Left unchanged deliberately:
rewording it is a product decision about what the new sentence should say,
not a technical one, and is out of scope for this branch until someone
signs off on the replacement wording.

**Is a JWT the right call long-term, or will this need to revoke a session
before it expires?** A JWT is only as revocable as the infrastructure around
it — short of rotating the signing secret (which logs out everyone, not one
person), there is no "kick this one person out right now." If that
capability turns out to matter, the session needs to become a database row,
not a signed token.

**Does this ship to main at all, and on what condition?** Not asked yet.
Worth naming as a question rather than an assumption: is the plan "once
Ranjit picks an email provider and the client confirms they want a login
screen," or something else?
