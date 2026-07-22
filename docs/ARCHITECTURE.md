# Architecture

The project uses a domain-first hexagonal layout:

```text
Tkinter desktop ─┐
FastAPI adapter ─┼─> application session ─> pure domain transitions
simulator ───────┘             │
                               ├─> in-memory rendezvous adapter
                               ├─> strict local-state repository
                               └─> synthetic HMAC identifier adapter
```

Domain modules never import FastAPI, Tkinter, the file system, or environment variables. External wire validation uses Pydantic; domain state uses frozen dataclasses, enums, tuples, and copied mappings. Clocks and timestamps are passed explicitly for deterministic tests.

The API and desktop application are research adapters, not trust boundaries. All reciprocal participant activity is a deterministic fixture. No adapter collects real location, scans Bluetooth, sends messages over a network, authenticates a person, or persists sensitive dating state.
