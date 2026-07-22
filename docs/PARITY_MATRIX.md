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
| `rnd-discovery` | `domain/discovery.py` | Verified, including bounded interactive ranking controls |
| `rnd-conversations` | `domain/conversations.py` | Verified session-only behavior |
| `rnd-relationship-phases` | `domain/relationship_phases.py` | Verified session-only behavior |
| `rnd-storage` | `domain/local_state.py` | Verified strict allowlist |
| `rnd-crypto-node` | `adapters/crypto/identifiers.py` | Golden-vector verified; synthetic helper only |
| `rnd-api` | `api/app.py` | Contract verified with in-memory store |
| `rnd-simulator` | `simulation/run.py` | Deterministic output verified |
| Expo orchestration | `application/session.py` + `desktop/app.py` | Recreated for laptop Tkinter R&D |

Verification uses unit, property, golden-vector, API contract, governance, and desktop smoke tests. These checks establish R&D behavior parity only; they do not close any real-user or production gate.
