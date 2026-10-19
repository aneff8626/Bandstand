# Backend and distribution status — 19 October 2026

## Scope

Nideesh invitation/publication is on hold while Andrew edits the app. Shared decoder
aggregation is deferred, and real decoder contributions remain prohibited. A weekly
reminder checks for 20 confirmed non-test users, then requests a design/privacy review;
it must not activate contributions automatically. Twenty registrations do not imply
twenty available participants or a validated privacy threshold.

## Verified locally

- Existing Developer ID signature identity preserved while adding hardened runtime,
  secure timestamps and explicit inside-out signing of native dependencies.
- Strict code-signature verification passes. Hardened bundled Python imports its
  dependencies and computes an offline synthetic semantic embedding successfully.
- 31 PostgreSQL SQL checks pass using PGlite 0.5.10, covering fresh and upgrade paths,
  permission inventory, consent, account isolation, idempotency, v1/v2 payload validation,
  quotas, ERP deletion, account deletion cascades and the decoder-sharing prohibition.
- Added a migration serializing per-user upload checks with consent updates to avoid
  concurrent requests exceeding quotas. No production migration was applied.

Reproduce SQL checks with Node and an installed `@electric-sql/pglite` package:

```
node scripts/check_migrations.mjs /absolute/path/to/pglite/dist/index.js
```

The report is `.audit/migrations.json`. This engine runs actual PostgreSQL SQL but
uses minimal auth/storage fixtures and one connection. It does not verify GoTrue,
PostgREST, SMTP, concurrent sessions, or hosted Supabase configuration.

## Remaining gates

1. Store an Apple notarization credential in Keychain using Apple's interactive
   `xcrun notarytool store-credentials Bandstand --apple-id YOUR_APPLE_ID --team-id XRB42223Z4`.
   Enter an Apple app-specific password privately at the secure prompt, never in source.
2. Run `python scripts/notarize_app.py release/Bandstand.app`. It submits without waiting
   indefinitely. Resume with the returned UUID using `--resume`; only Accepted results
   proceed to stapling, Gatekeeper assessment and rebuilding the download archive.
3. Test a quarantined download/install on a clean Mac, then permissions across an update.
4. Provision isolated hosted/local Supabase staging, apply all migrations in filename
   order, and run `scripts/staging_accounts.py` and `scripts/staging_erp_sharing.py`.
   Do not point destructive acceptance scripts at production.
5. In staging, use two simultaneous connections at the quota boundary; exactly one
   new upload should succeed. Verify consent withdrawal versus in-flight upload ordering.
6. After staging passes, record production schema/backup recovery evidence and deploy
   pending migrations in order; perform a synthetic opt-in upload/retry/delete smoke test.

The existing production ordinary-user signup/email-confirmation/sign-in test passed
earlier. That does not replace these remaining staging and installation checks.
