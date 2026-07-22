from __future__ import annotations

import base64
import io
import shutil
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARTS = sorted((ROOT / "bootstrap_payload").glob("source_*"))
if not PARTS:
    raise SystemExit("No source payload parts found")
encoded = "".join(part.read_text(encoding="ascii").strip() for part in PARTS)
archive = base64.b64decode(encoded)
with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tf:
    members = tf.getmembers()
    for member in members:
        target = (ROOT / member.name).resolve()
        if ROOT not in target.parents and target != ROOT:
            raise SystemExit(f"Unsafe archive path: {member.name}")
    tf.extractall(ROOT)
shutil.rmtree(ROOT / "bootstrap_payload", ignore_errors=True)
print(f"Reconstructed repository from {len(PARTS)} payload parts")
