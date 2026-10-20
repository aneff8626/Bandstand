# Account acceptance run 20261016-225626-27d6

Backend: development (http://127.0.0.1:54321), mail: mailpit

| ID | Area | Check | Outcome | Level | Evidence |
|---|---|---|---|---|---|
| S01 | signup | Signup with privacy acknowledgment asks the person to confirm by email | pass | local stack | Check your email to confirm your account, then sign in. |
| S02 | signup | Confirmation email arrives with a visible code and Bandstand instructions | pass | local stack | subject: Your Bandstand confirmation code; code length 6 |
| S03 | signup | Sign-in is refused before the email is confirmed | pass | local stack | Confirm your email with the code we sent before signing in. |
| S04 | signup | A wrong confirmation code is rejected | pass | local stack | 403 This code is wrong, expired or already used. Request a new email. |
| S05 | signup | Confirmation accepts the code with the email typed in different letter case | pass | local stack | Email confirmed. You can now sign in. |
| S06 | signup | A used confirmation code cannot be reused | pass | local stack | 403 This code is wrong, expired or already used. Request a new email. |
| S07 | signin | A wrong password is refused with a generic message | pass | local stack | Email or password is incorrect. |
| S08 | signin | Sign-in with remember-me works with mixed-case email | pass | local stack | signed in; remembered; display name restored |
| S09 | session | Remember-me stores only a refresh token in macOS Keychain | pass | local stack | Keychain item present for this data directory; it equals the refresh token and holds no password |
| S10 | session | Closing and reopening the app restores the remembered identity | pass | local stack | {"signed_in": true, "remembered": true, "backend": "development"} |
| S11 | profile | Display-name change is saved to the account and survives a restart | pass | local stack | name updated in cloud metadata and visible after reopen |
| S12 | session | An expired access token is refreshed transparently with the stored refresh token | pass | local stack | new access token issued; still signed in |
| S13 | signup | Duplicate signup for an existing account does not create a second user or change the password | pass | local stack | HTTP 422; app message: This email already has an account. Sign in, or use Forgot password? to reset it.; users with this email: 1; no new email sent; original password still works |
| A01 | access | Anonymous callers cannot execute any Bandstand RPC | pass | local stack | {"bandstand_sharing_status": 401, "bandstand_list_erp": 401, "bandstand_set_erp_consent": 401, "bandstand_upload_erp": 401, "bandstand_delete_erp": 401, "bandstand_delete_own_account": 401, "bandstand_valid_erp": 401} |
| A02 | access | Publishable key is not an authorization boundary (user token without it) | observed | local stack | HTTP 200 without the publishable key. Authorization rests on the user token and database grants, as the handoff states. |
| A03 | access | Direct table reads and writes are refused for anonymous and signed-in callers, and nothing changes | pass | local stack | 24 well-formed probes refused with [401, 403]; row counts unchanged |
| A04 | access | A tampered access token is rejected by Auth and the database API | pass | local stack | Auth 403, REST 401 |
| A05 | access | An expired but correctly signed access token is rejected (control: same token unexpired is accepted) | pass | local stack | control 200; expired: REST 401, Auth 403 |
| I01 | isolation | Second synthetic account B is created and confirmed | pass | local stack | confirmed through emailed code |
| I02 | isolation | A and B each consent and upload one synthetic ERP record | pass | local stack | two consents and two records stored |
| I03 | isolation | Each person lists only their own records | pass | local stack | A sees only A; B sees only B |
| I04 | isolation | RPCs ignore attempts to name another user | pass | local stack | extra user_id argument rejected: {"bandstand_list_erp": 404, "bandstand_delete_erp": 404, "bandstand_sharing_status": 404} |
| I05 | isolation | B withdrawing consent and deleting records leaves A untouched | pass | local stack | A consent and record intact |
| I06 | isolation | B cannot upload without consent after withdrawing | pass | local stack | HTTP 400 |
| I07 | isolation | B deleting their own account removes only B | pass | local stack | B user, consent and record rows: 0; A intact |
| R01 | recovery | Recovery request returns the same message for real and unknown addresses | pass | local stack | If this address has an account, a password reset email will arrive shortly. Check spam too. |
| R03 | recovery | A second request inside the resend interval is rate limited with a clear message | pass | local stack | Too many attempts. Please wait before trying again. |
| R02 | recovery | Recovery email arrives with a code and in-app instructions | pass | local stack | subject: Your Bandstand password reset code |
| R04 | recovery | A recovery code cannot reset a different email address | pass | local stack | This code is wrong, expired or already used. Request a new email.; original password still works |
| R05 | recovery | Malformed proofs are rejected before contacting the server | pass | local stack | three malformed proofs refused |
| R06 | recovery | Reset with the emailed code sets the new password and ends the app session | pass | local stack | Password updated. Sign in with your new password. |
| R07 | recovery | The old password stops working and the new one works | pass | local stack | old password HTTP 400; new password accepted |
| R08 | recovery | A used recovery code cannot be reused | pass | local stack | refused |
| R09 | recovery | Reach of the reset: other devices' sessions (documents actual scope) | pass | local stack | other device refresh token HTTP 400; its unexpired access token: Auth /user HTTP 403, database RPC HTTP 200 |
| O01 | signout | Sign-out clears the app session and Keychain; reach to other devices documented | pass | local stack | local session and Keychain cleared; reopened app signed out; another device's refresh token afterwards: HTTP 400 (revoked: sign-out is global) |
| E01 | signup | An expired confirmation code is rejected (send time backdated two hours in the local database) | pass | local stack | 403 This code is wrong, expired or already used. Request a new email. |
| E02 | signup | Signing up again sends a fresh code that confirms the account (as the email instructions say) | pass | local stack | Email confirmed. You can now sign in. |
| E03 | email | Mail-server failure produces an actionable error and no false success | pass | local stack | The account server failed to complete this request. For signup or recovery, the administrator should check the email delivery configuration. No email delivery is confirmed. |
| N01 | network | Unreachable account server: clear message, local recording unaffected | pass | local stack | Account service unavailable. Local recording remains available. |
| N02 | network | A server that accepts but never answers times out with the same clear message | pass | local stack | Account service unavailable. Local recording remains available. (after 15s) |
| D01 | deletion | Deleting designated account A removes the cloud account and clears the local session | pass | local stack | Account and consent record deleted. Local recordings remain on this computer. |
| D02 | deletion | A's auth user, consent row and shared ERP rows are gone | pass | local stack | auth.users 0, bandstand_consent 0, bandstand_erp_recordings 0 |
| D03 | deletion | After deletion the old credentials no longer work (documents token behavior) | pass | local stack | password sign-in HTTP 400; refresh HTTP 400; Auth /user HTTP 403; unexpired access token on RPCs: list HTTP 200 (0 rows), set-consent HTTP 409 |
| D04 | deletion | Local files are untouched by cloud account deletion, as the app message says | pass | local stack | synthetic local file still present after deletion |
| H01 | hygiene | No user-visible message or result contains a password, token or email code | pass | local stack | 31 messages scanned |
