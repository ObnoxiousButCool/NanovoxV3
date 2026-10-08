# Decisions and Questions — login

2026-10-08 · `feature/email-otp-login`, not on main

Ranjit originally asked for an email-OTP sign-in system: enter an address,
get a 6-digit code, enter the code, get in. Leadership later changed that to
a single shared username and password for the whole application. This is
the running record of what got decided through both versions and what is
still genuinely open — kept here rather than only in commit messages and
code comments, so the next person (including whoever eventually reviews
this for main) does not have to reconstruct the reasoning from a diff.

## Current approach: one shared username and password

**Leadership, 2026-10-08: skip email entirely, use a fixed username and
password.** `Technossus` / `Tech@2026`. Not a per-person account — one
credential gates the whole application. Replaces the email-OTP flow below
outright; the email-sending work, the allowlist, and the OTP machinery are
all removed, not just unused.

**The credential lives in settings (`.env`), not a database.** A table made
sense for the allowlist this replaces, because that was a list expected to
grow. One hardcoded pair has nothing to grow — a table would be overhead
with nothing bought for it. `AUTH_USERNAME` and `AUTH_PASSWORD_HASH` behave
like `JWT_SECRET` already does: required outside local development, with no
safe default.

**The password is hashed with PBKDF2-HMAC-SHA256, never stored in
plaintext.** Even a leadership-issued shared password gets the same
treatment a per-person one would — `domain/value_objects/password_hash.py`,
stdlib only (no new dependency). This is also why it was not reused for the
OTP code's hashing before it: a password is long-lived and not from a
cryptographic RNG, which is exactly what a slow, salted KDF exists to
protect; a fast hash (right for the old OTP code) would be the wrong tool
here.

**A wrong username and a wrong password answer identically.** `Login`
checks both before raising, rather than stopping at the first mismatch, so
neither a timing difference nor a different message tells a caller which
one was wrong — same principle the email-OTP flow applied to "not approved"
vs. "wrong code."

**The session mechanism is unchanged.** The JWT bearer session, the
`require_session` gate on every router but `/health` and `/auth`, the
frontend's whole-app gate, `localStorage` persistence, and auto-logout on a
401 all carried over from the email-OTP build untouched — only the
credential check in front of them changed. See below for why those were
built the way they were.

**The login page is one step now, not two.** No "enter your email, then
enter the code" — just a username field and a password field, reusing the
card/branding already built for the email flow.

**This still stays on its own branch.** Ranjit's original instruction
("let's work on the login page and keep it in the other branch, let's not
merge it to main") was never reversed, and the credential-model change
doesn't reverse it either.

## Superseded: the email-OTP approach this branch started with

Kept for the reasoning, not as a description of what currently runs.

**The allowlist was a database table, not a config file.** First cut shipped
as `config/approved_emails.yaml`, a developer-edited file matching the
pattern `dashboard.yaml` and `action_lifecycle.yaml` use. Ranjit asked for
the database route instead (2026-10-08), so it briefly became the
`approved_emails` table before the whole email approach was dropped.

**Email delivery was a swappable adapter, defaulting to a console logger.**
`EmailSender` was a port with two adapters: `ConsoleEmailSender` (logged the
code instead of mailing it, so the flow was demoable with nothing
configured) and `SmtpEmailSender` (stdlib `smtplib`). The intent — swapping
the real sending account in later without touching anything above the port
— is the same reasoning the current credential-storage split follows.

**Requesting a code answered the same way regardless of whether the address
was approved, and verifying gave one message for wrong, expired, or
never-issued.** The enumeration-resistance principle this established is
exactly what `Login` applies to username/password today.

**Going through Shehbaz for email configuration is moot.** Ranjit's
2026-10-08 reply ("connect with Shehbaz... similar to the Technossus
Website... check whether there would be any additional cost") no longer
needs following up — there is no email to send.

## Questions — genuinely open

**Is one shared credential the end state, or will per-person accounts
matter later?** Nobody asked for individual logins, but this system touches
compliance-adjacent data, and "everyone is Technossus" means there is no way
to answer "who did this" from the login alone. Worth naming now rather than
assuming either way.

**Should a sign-in be logged anywhere a human can see it?** More relevant
with one shared credential than it would be with per-person ones: right now
nothing records when the password was used, so "who was in the system
Tuesday afternoon" has no answer beyond the standard request log's
incidental detail.

**Is a 12-hour session the right length?** No "remember me," no shorter
option for a shared machine, no longer one for someone who does not want to
re-enter the password daily. Picked as a reasonable default, not requested
by anyone.

**The action board's `trustNote` is now wrong.** `GET /insights/actions/board`
still carries the line "there is no sign-in, and anyone who can reach the
service can edit" (D14, R9 — decided before this feature existed). Once
login ships, that sentence is no longer true. Left unchanged deliberately:
rewording it is a product decision about what the new sentence should say,
not a technical one, and is out of scope for this branch until someone
signs off on the replacement wording.

**Is a JWT the right call long-term, or will this need to revoke a session
before it expires?** More pointed now than it was with per-address OTP
sessions: there is exactly one credential, so if it needs to be invalidated
mid-use (a leak, an offboarding), rotating `JWT_SECRET` logs out everyone at
once — there is no "kick this one session out right now" short of that. If
that capability turns out to matter, a session needs to become a database
row, not a signed token.

**How does the password actually get rotated, and by whom?** Today that is
an `.env` edit and a redeploy. Fine for a POC; worth asking whether that is
still fine once this is something other than Ranjit and Shloka testing it.

**Does this ship to main at all, and on what condition?** Not asked yet.
Worth naming as a question rather than an assumption.
