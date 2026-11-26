# Management MFA

Implemented in `backend/mfa.py` and endpoints under `/api/v1/iam/mfa/*`. UI: `MfaPanel` on account page.

## Algorithm

- TOTP: SHA1, 6 digits, 30-second step, ±1 step window
- Seed sealed with AES-GCM (`secret_crypto`) bound to user id
- Pending enrollment expires in **10 minutes**
- **10** one-time recovery codes stored as SHA-256 digests
- Successful TOTP updates `mfa_last_step` (replay protection)
- Recovery code is removed from the array on use and audited

## Endpoints (authenticated personal session)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/iam/mfa/status` | Enabled flag + recovery codes remaining |
| POST | `/api/v1/iam/mfa/setup` | Body `{password}` → secret + otpauth URI |
| POST | `/api/v1/iam/mfa/confirm` | Body `{password, otp}` → recovery codes once |
| POST | `/api/v1/iam/mfa/disable` | Body `{password, otp}` |

Enrollment and disable **revoke existing sessions**.

## Login with MFA

When MFA is enabled, login requires TOTP or recovery code with the password.

## Gaps

- No forced org-wide MFA policy
- Legacy `ADMIN_TOKEN` bypasses personal MFA when enabled
- Requires synchronized clocks and HTTPS for real deployments
