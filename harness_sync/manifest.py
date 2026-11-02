"""The manifest a sync leaves in a target: harness commit and a hash per managed file (spec 5.3)."""

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path


def file_hash(data: bytes) -> str:
    # CRLF is normalised so a Windows checkout hashes like the payload (spec 6, Windows checkouts).
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


@dataclass
class Manifest:
    harness_commit: str
    files: dict[str, str] = field(default_factory=dict)

    def dumps(self) -> str:
        body = {"harness_commit": self.harness_commit, "files": dict(sorted(self.files.items()))}
        return json.dumps(body, indent=2) + "\n"

    @classmethod
    def read(cls, path: Path) -> "Manifest | None":
        path = Path(path)
        if not path.is_file():
            return None
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls(harness_commit=raw["harness_commit"], files=dict(raw["files"]))

    def write(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.dumps().encode("utf-8"))
