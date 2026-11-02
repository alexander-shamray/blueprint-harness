"""The manifest a sync leaves in a target: harness commit and a hash per managed file (spec 5.3)."""

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path


def file_hash(data: bytes) -> str:
    # CRLF is normalised so a Windows checkout hashes like the payload (spec 6, Windows checkouts).
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


class ManifestError(Exception):
    """The manifest file does not match the schema."""


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
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ManifestError(f"cannot read {path}: {exc}") from exc
        if not isinstance(raw, dict) or set(raw) != {"harness_commit", "files"}:
            raise ManifestError("must be an object with exactly harness_commit and files")
        if not isinstance(raw["harness_commit"], str) or not re.fullmatch(r"[0-9a-f]{40}", raw["harness_commit"]):
            raise ManifestError("harness_commit must be 40 lowercase hex characters")
        files = raw["files"]
        if not isinstance(files, dict) or not all(
            isinstance(k, str) and isinstance(v, str) and re.fullmatch(r"[0-9a-f]{64}", v) for k, v in files.items()
        ):
            raise ManifestError("files must map paths to 64-character lowercase hex hashes")
        return cls(harness_commit=raw["harness_commit"], files=dict(files))

    def write(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.dumps().encode("utf-8"))
