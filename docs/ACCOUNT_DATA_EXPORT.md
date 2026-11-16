# Account data export

Authenticated users can download a JSON export from **Profile → Your account data** or call `GET /api/auth/me/export/` with their access token.

The export contains the signed-in account's profile and linked records: farmer or buyer profile, land and crop records, listings, the user's side of transactions, complaints, scheme applications, trust score, loan estimates, and notifications. Records are filtered by the authenticated user. Transaction exports omit the other party's identifier and private profile fields.

Uploaded files are represented by their stored path; file contents are not bundled. The JSON response is marked `private, no-store`. The export can include sensitive profile data such as an Aadhaar number, so users should keep the downloaded file private and delete it when no longer needed.
