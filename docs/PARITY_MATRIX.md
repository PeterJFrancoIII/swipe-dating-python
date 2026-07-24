# JavaScript-to-Python parity matrix

| JavaScript module | Python destination | Status |
|---|---|---|
| `rnd-domain/adult.js` | `domain/adult.py` | Verified |
| `rnd-domain/alignment.js` | `domain/alignment.py` | Verified |
| `rnd-domain/preferences.js` | `domain/preferences.py` | Verified |
| `rnd-domain/matching.js` | `domain/matching.py` | Verified |
| `rnd-domain/proximity.js` | `domain/proximity.py` | Verified decision model; no Bluetooth |
| `rnd-domain/location-grants.js` | `domain/location_grants.py` | Verified metadata model; no coordinates |
| `rnd-domain/risk.js` | `domain/risk.py` | Verified |
| `rnd-domain/skin-shop.js` | `domain/skin_shop.py` | Verified validation; catalog remains mock |
| `rnd-discovery` | `domain/discovery.py` | Verified, including bounded ranking controls and visible public boundary starter context |
| `rnd-conversations` | `domain/conversations.py` | Verified session-only behavior, including structured public-meetup prompts |
| `rnd-relationship-phases` | `domain/relationship_phases.py` | Verified session-only behavior |
| `rnd-storage` | `domain/local_state.py` | Verified strict allowlist |
| `rnd-crypto-node` | `adapters/crypto/identifiers.py` | Golden-vector verified; synthetic helper only |
| `rnd-api` | `api/app.py` | Contract verified with in-memory store |
| `rnd-simulator` | `simulation/run.py` | Deterministic output verified |
| Expo orchestration | `application/session.py` + `web/app.py` | Focused server-rendered laptop flow |
| New bot-control slice | `domain/bot_moderation.py` + `web/app.py` | Synthetic extension; not baseline parity |

Verification uses unit, property, golden-vector, API contract, governance, web integration, and
headless-browser acceptance tests. These checks establish synthetic R&D behavior only; they do not
close any real-user or production gate.
