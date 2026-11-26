# Login namespace guard

Migration 0027 protects exact, case-sensitive unified usernames from independent radcheck, Device AAA, L2TP, EAP, IAM and Hotspot voucher accounts. Existing legacy-to-legacy overlaps remain supported. Linked Device AAA/L2TP/IAM rows rely on their existing composite foreign keys. The voucher username pattern is reserved from unified identities. No existing users are merged or deleted.

Migration stops on existing unified/legacy conflicts or reserved unified names. Inspect those conflicts as database owner and resolve explicitly before retrying. Triggers serialize namespace mutations with the existing hashtext advisory lock, and reject namespace changes outside READ COMMITTED. Administrative writes that disable triggers are outside this guarantee. Username matching remains exact; this is not a case-folding or realm-normalization migration. The API returns HTTP 409 for unhandled unique violations without exposing SQL details.

Stop API and RADIUS before migration; back up PostgreSQL. Runtime tests and build have not been executed.
