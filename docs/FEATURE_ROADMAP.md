# KisanSetu feature roadmap

Impact/effort are estimates, not proof of demand. Review observations are summarized in [`MARKET_RESEARCH.md`](MARKET_RESEARCH.md); small review samples are not universal findings. Use synthetic data in tests. Do not build real lender access or imply health, credit, scheme eligibility, or government approval without authoritative data and legal review.

| # | Feature | User problem solved | Gap to test | Impact | Effort | Status |
|---:|---|---|---|---|---|---|
| 1 | Scheme discovery uses farm/crop text only and clearly says it is not eligibility | Demo trust/loan signals could look like official scheme criteria | Users need understandable discovery without a false approval signal | High | Medium | Implemented locally: trust score removed from discovery; reasons name the matched crop; no percentage score or eligibility claim; bilingual note and backend tests added |
| 2 | Official scheme source URL and verified-at date | Farmer cannot tell if rules are current or official | Public portals distribute fragmented or stale information | High | Medium | Planned; owner must supply verified sources |
| 3 | Farmer-controlled data-sharing consent receipts | Farmer needs to know exactly what left the account | No institution-scoped consent flow exists | High | High | Planned; lender access remains disabled |
| 4 | Simple account-data export and deletion request flow | User needs control over personal records | Export exists; deletion rules need counterparty/legal review | High | High | Export implemented; deletion blocked pending policy |
| 5 | Offline-first farm record drafts | Low-connectivity users lose entry work | Web platform assumes connectivity for most flows | High | High | Planned |
| 6 | SMS/voice-friendly notification preferences | Important notices may be missed | App pushes alone may not reach every user | High | Medium | Planned; needs opt-in and provider cost review |
| 7 | Local buyer quote comparison | Farmer wants to compare offers before accepting | Marketplace workflow does not prove settlement or best price | High | High | Planned; no price guarantees |
| 8 | Transparent listing readiness checklist | Farmer misses photos, quantity, or pickup details | Marketplace trust depends on complete listings | Medium | Low | Planned |
| 9 | Complaint status timeline with next action | Farmer cannot see who owns a complaint or what happens next | Basic status may lack clear time expectations | High | Medium | Planned |
| 10 | Scheme application document checklist | Applications can be delayed by missing documents | Scheme records do not verify each scheme's current requirements | High | Medium | Planned; only from approved official sources |
| 11 | FPO workspace with scoped staff roles | Small groups coordinate without sharing every farmer record | Existing individual roles do not create an FPO boundary | High | High | Planned |
| 12 | Crop calendar with user-edited reminders | Seasonal tasks are easy to forget | Generic advice may not match a local crop calendar | Medium | Medium | Planned; no unsourced agronomy claims |
| 13 | Data-quality warnings for duplicate/incomplete farm records | Incorrect records reduce usefulness | Existing forms need clearer correction guidance | Medium | Medium | Planned |
| 14 | Bilingual assisted onboarding with save/resume | First use can be hard on mobile | Existing bilingual UI may still require lengthy entry | High | Medium | Planned |
| 15 | Partner dashboard for aggregated, consented service demand | FPOs need operational demand indicators | Current role analytics need validation and privacy review | Medium | High | Planned; never expose farmer-level sensitive data by default |

## Build order

Start with item 1 and source/date integrity before growth features. No anonymous behavioral tracking, bulk marketing, unconsented bank access, or real-person data in demos. Every shipped item needs focused tests, accessible UI states, help text, and a first-time user walkthrough.
