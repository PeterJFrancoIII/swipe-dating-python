# Current objective — Python R&D reconstruction

**Status:** ACTIVE
**Branch:** `agent/python-rnd-rebuild`
**Real users:** Prohibited

## Mission Control Packet

**Mission:** Recreate the supplied Swipe Dating app in Python for laptop R&D and deliver it to `PeterJFrancoIII/swipe-dating-python` without weakening consent, privacy, safety, or release controls.

**Source of truth:** JavaScript repository commit `5c6b35e8b133f4b34224785eb4fc1e7ab61423a4` and the July 22, 2026 Python rebuild specification supplied with the Dating App project.

**Rebuild plan:** [2026-07-22-python-rnd-rebuild.md](../superpowers/plans/2026-07-22-python-rnd-rebuild.md)

**Current loop:** [2026-07-22-structured-meetup-prompts.md](../superpowers/plans/2026-07-22-structured-meetup-prompts.md)

**Evidence required:** unit/property/contract/integration/smoke tests, coverage, compile, Ruff, mypy, deterministic simulation, governance checks, clean diff, and GitHub Actions.

**Constraints:** Python-only project-authored code; synthetic fixtures only; strict storage allowlist; no production authorization; sources outside this repository remain read-only.

**Rollback:** the implementation is isolated on a feature branch and can be discarded without changing `main`.

**Approval status:** R&D repository publication is authorized by the user. Real-user features, production deployment, mobile-store submission, infrastructure, secrets, billing, BLE, and location collection are not authorized.
