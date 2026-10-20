# Milestone one: accounts and consent

Branch `m1-accounts-consent`, based on `main` at 335c641 (the commit the backend handoff reviewed).
The `codex/v0.3.0-alpha.1` branch does not touch any file changed here.

## Status

Levels are kept separate, as the handoff asks. "Local stack" means the Supabase CLI stack in Docker: the
real Auth (GoTrue v2.197.0), PostgREST and Postgres 17 services, with outgoing email captured by the
stack's Mailpit server instead of reaching a real inbox. It is not the cloud project.

| Deliverable | Implemented | Locally tested | Cloud tested | Hardware tested |
|---|---|---|---|---|
| Reproducible staging setup (`supabase/config.toml`, templates) | yes | yes | no | n/a |
| Ordered migrations, fresh-project blocker fixed | yes | yes: empty database, re-apply on existing schema, guard with and without `rls_auto_enable()` | no | n/a |
| Separate backend configuration | yes | yes: 5 unit tests, build validation | no | n/a |
| Signup, confirmation code, sign-in | existing code | yes (S01–S08) | no | n/a |
| Remembered sign-in across app restart (Keychain) | existing code | yes (S09–S10, real macOS Keychain) | no | n/a |
| Profile change | existing code | yes (S11) | no | n/a |
| Password recovery | existing code | yes (R01–R09) | no | n/a |
| Designated-account deletion and cascade | existing code | yes (D01–D04, I07) | no | n/a |
| Anonymous, tampered, expired-token and direct-table access | n/a | yes (A01–A05) | no | n/a |
| User A cannot list, alter or delete user B's records | n/a | yes (I01–I07) | no | n/a |
| Actionable Auth error wording | yes | yes (unit + S03, S04, S07, S13) | no | n/a |
| Real email delivery (custom SMTP to a real inbox) | not in code | **no**: local mail is captured, not delivered | **no** | n/a |

**Cloud tested is empty.** That needs a development Supabase project, or access to an approved staging
project, which this work did not have. See "Next step".

## What changed

- `supabase/migrations/`: renamed to unique ordered versions `20261008000001_privacy_foundation`,
  `…02_account_deletion` and `…03_erp_sharing`. SQL is unchanged except for the guard below.
- Fresh-project blocker: the `REVOKE … ON FUNCTION public.rls_auto_enable()` now runs only when
  `to_regprocedure('public.rls_auto_enable()')` finds the function. Reproduced first: on an empty
  database the original file fails with `function public.rls_auto_enable() does not exist`. With the
  guard, all three migrations apply. Where the function exists and clients can execute it, the
  migration still revokes that access (tested). RLS is not disabled anywhere.
- `backend_config.py` (new): one fixed backend per installation. Production is built in. A
  development or staging build may include `backend.json` beside the code, which is validated: an
  `https://<20-char ref>.supabase.co` address, or plain HTTP to 127.0.0.1/localhost with an explicit
  port for `development` only. It also requires a `sb_publishable_` key, refuses secret or JWT keys,
  extra fields and symlinks, and refuses to label the production project as staging. There is no
  environment-variable or runtime override. `accounts.py` reads `URL` and `PUBLISHABLE_KEY` from it,
  and account status reports the backend name. The Account dialog shows "· development server" or
  "· staging server" when not on production.
- `scripts/build_desktop.py`: `BANDSTAND_BACKEND_CONFIG=<file>` embeds a validated `backend.json`.
  It is checked before any slow work. Non-production archives are named
  `Bandstand-0.2.2-<name>-macos-arm64.zip`, and the bundle manifest records the backend. Bundle
  identifier and signing requirements are unchanged.
- `scripts/audit_release.py`: the source bundle now includes `supabase/*.toml` and the email
  templates. A `backend.json` inside the bundle is reported as a finding. This is a backstop: the
  current allowlist never copies it.
- `accounts.py` error wording: Auth error responses are still never shown. Only the machine-readable
  `error_code` is read, and ten allowlisted codes map to fixed sentences: wrong password, email not
  confirmed, account already exists, weak or reused password, wrong/expired/used code, invalid email,
  mail server not authorized for the address, signup disabled. Unknown codes stay generic. Before
  this, an existing user signing up again saw "Account request failed. Check your details and email
  confirmation."
- `supabase/config.toml` and `supabase/templates/`: confirmation required and minimum password 8,
  matching the app. Code-only email templates with `{{ .Token }}`, naming the app's actual screens
  ("Check your email", "Choose a new password"). The site URL is the static GitHub Pages page. No
  redirect URLs are allowed, and `localhost:3000` is not restored. The emails carry no links, because
  no desktop callback exists.
- `supabase/checks/verify_permissions.sql` (new): a read-only inventory of 55 checks covering
  tables, RLS, direct grants for `anon` and `authenticated`, policies, the SECURITY DEFINER flag and
  empty `search_path` on every RPC, execute grants, cascade constraints, the decoder constraint,
  public buckets and `rls_auto_enable()`. Paste it into any project's SQL editor; every row should
  read `ok = true`.
- `scripts/staging_accounts.py` (new): the acceptance harness below.
- Tests: `tests/test_backend_config.py` (new) plus two error-wording tests in `tests/test_accounts.py`.
  Account unit tests now pin the production address, so a developer's `backend.json` cannot change
  their outcome.

## How the pieces connect

```
Bandstand.app (macOS)
 ├─ Swift shell ──local pipes──► Python service: accounts.py
 │                                 ├─ macOS Keychain "org.bandstand.session": refresh token only
 │                                 └─ HTTPS ─► Supabase project (production built in; dev/staging via validated backend.json)
 │                                              ├─ Auth (GoTrue) ──SMTP──► participant inbox
 │                                              └─ PostgREST ─► Postgres
 │                                                   bandstand_consent, bandstand_erp_recordings, bandstand_model_releases
 │                                                   RLS on, no table grants; SECURITY DEFINER RPCs keyed on auth.uid()
 └─ Private data directory: recordings and writing stay local
```

## Configuration names (no values)

| Name | Where | Purpose |
|---|---|---|
| `backend.json` → `name`, `url`, `publishable_key` | beside the code (git-ignored) or embedded by the builder | non-production backend |
| `BANDSTAND_BACKEND_CONFIG` | build machine environment | path of the backend file to embed in a staging build |
| `BANDSTAND_SIGN_IDENTITY` | build machine environment | unchanged; Developer ID identity |
| `BANDSTAND_DATA_DIR` | environment | throwaway data directory for tests and acceptance runs |
| Supabase dashboard: Auth → Email → Confirm email (on), minimum password length (8), email OTP length (6) | cloud project | match the app and the templates |
| Supabase dashboard: Auth → SMTP host, port, user, password, sender | cloud project only | never in the repo, the app or logs |
| Supabase dashboard: Auth → Email templates (Confirm signup, Reset password) | cloud project | paste `supabase/templates/*.html`; both must show `{{ .Token }}` |
| Supabase dashboard: Auth → URL configuration: Site URL, Redirect URLs | cloud project | site URL as in `config.toml`; no redirect URLs until a desktop callback exists |

## Reproduce

```sh
# Unit and regression tests (production default; no backend.json present)
BANDSTAND_DATA_DIR="$(mktemp -d)" .venv/bin/python -m unittest discover -s tests
for test in tests/*.cjs; do node "$test" || exit 1; done

# Local staging stack (Docker). First start downloads images.
supabase start -x realtime,storage-api,imgproxy,edge-runtime,logflare,vector,supavisor,studio,postgres-meta
supabase status            # API URL and publishable key for the local stack
echo '{"name":"development","url":"http://127.0.0.1:54321","publishable_key":"<local publishable key>"}' > backend.json
docker exec -i supabase_db_bandstand-dev psql -U postgres -f - < supabase/checks/verify_permissions.sql
BANDSTAND_DATA_DIR="$(mktemp -d)" .venv/bin/python scripts/staging_accounts.py --mail mailpit
supabase db reset          # rebuild from the three migrations
rm backend.json            # back to production before building a release
```

Against a cloud development project, use `--mail prompt --email-a … --email-b … --email-c …` and type
the codes from the real inboxes. Checks that need direct database access are then reported as
"not run". Use the SQL editor and `verify_permissions.sql` for those.

## Results (2026-10-16, local stack)

- Unit tests: 111 Python tests pass (104 existing plus 7 new). All 11 JavaScript regression scripts pass.
- Release audit passes: 96 files, no findings.
- `verify_permissions.sql`: 55/55 ok on a freshly migrated database.
- Acceptance: 44 pass, 0 fail, 1 observed. Full matrix: `docs/acceptance/accounts-local-20261016.md`.
- The checks can fail. Granting `SELECT` on `bandstand_consent` to `authenticated` made the
  inventory and A03 fail. Making `bandstand_list_erp` return every user's rows made I03–I05 fail.
  The schema was then rebuilt with `supabase db reset`.
- An expired code (E01) was simulated by moving `confirmation_sent_at` back two hours in the local
  database. The expired access token (A05) was minted with the local stack's signing secret. A control
  token, identical except unexpired, was accepted, so the rejection is due to expiry.

## Findings that need a decision

1. **Sign-out is global.** `/auth/v1/logout` without a scope revokes every session the person has.
   Signing out on one Mac signs them out everywhere (O01). That suits password reset and deletion.
   For everyday sign-out, `?scope=local` would affect only this computer. This is a product
   decision; the code is unchanged.
2. **Revoked sessions keep database access until their access token expires.** After a password
   reset or sign-out, the other device's refresh token is refused and Auth's `/user` returns 403.
   Its unexpired access token was still accepted by the Bandstand RPCs (R09: HTTP 200). Supabase
   access tokens are self-contained, so this is platform behavior. The window is `jwt_expiry`: 3600 s
   locally, and the cloud setting is unverified. After deletion the practical effect is nil: listing
   returns 0 rows and consent writes fail (D03). Options: shorten JWT expiry, or have each RPC also
   require that `auth.jwt()->>'session_id'` still exists in `auth.sessions`. The second option
   changes production SQL and is not done here.
3. **Duplicate signup reveals an existing account.** The local Auth server answers
   `422 user_already_exists`. Any direct caller already learns this, so the new wording adds nothing.
   Cloud projects may obfuscate this response instead. The harness accepts either, as long as no
   second user is created and the password is unchanged.
4. **Consent receipts are still editable metadata.** The privacy acknowledgment lives in
   user-editable `user_metadata`. Server-side ERP consent is enforced, but no tamper-evident consent
   receipt exists, as the handoff notes. This is proposed for the next step, not built.
5. **`rls_auto_enable()`'s purpose on production is unverified.** On the fresh local stack it does
   not exist. It may be a project-specific helper. `verify_permissions.sql` reports whether it is
   present and callable.

## Production differences and what was not verified

- Nothing was applied to production, and no production record was read. Production was presumably
  set up by running these files by hand; whether it has a migration history is unknown. Do not
  `supabase db push` to production blind:
  1. Run `verify_permissions.sql` in the production SQL editor, and capture the schema with
     `supabase db dump --linked --schema public` once linked.
  2. Compare the result with a fresh local reset.
  3. Only if they match, record the three versions as applied with
     `supabase migration repair --status applied 20261008000001 20261008000002 20261008000003`.
- Email delivery through the configured SMTP provider (Gmail app password) has not been checked.
  Supabase's built-in mailer only sends to project team members; the new wording covers its
  `email_address_not_authorized` error.
- Cloud email OTP length and expiry, rate limits, JWT expiry, and whether the dashboard templates
  include `{{ .Token }}` are unverified.
- Email verification links were not tested; local links are `http`, which the app rejects by design.
  Codes are the tested path.
- Andrew's unpublished 1a/1b setup-screen fix was not needed for this milestone and was not obtained.

## Next step

Cloud acceptance needs one of the following:

- Andrew adds Nideesh to a development Supabase project, or creates one.
- Nideesh creates his own free development project and points `backend.json` at it.
- Andrew runs `scripts/staging_accounts.py --mail prompt` against his staging project himself.

Then set the dashboard items in the table above, run `verify_permissions.sql` in that project, and
run the harness with three readable inboxes. Never use the production project for these tests.
