"""Deployment-key encryption of Strata's own stateless reasoning replay items.

No response records are stored. The private key survives server restarts; rotating
it invalidates old replay tokens. Foreign-provider tokens are never interpreted.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

PREFIX = "strata-r1."


def default_key_path():
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "Strata/responses.key"
    return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "strata/responses.key"


class ReplayCodec:
    def __init__(self, key):
        self.cipher = Fernet(key)

    @classmethod
    def load(cls, path=None):
        path = Path(path) if path is not None else default_key_path()
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        # Exclusive creation prevents overwriting an existing deployment key.
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, "wb") as keyfile:
                keyfile.write(Fernet.generate_key())
                keyfile.flush()
                os.fsync(keyfile.fileno())
        return cls(path.read_bytes())  # malformed keys fail startup; never silently rotate

    def seal(self, model, item):
        payload = {"version": 1, "model": model, "id": item["id"], "content": item["content"],
                   "summary": item["summary"], "status": item["status"]}
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return PREFIX + self.cipher.encrypt(raw).decode("ascii")

    def restore(self, model, item):
        token = item.get("encrypted_content")
        if not isinstance(token, str) or not token.startswith(PREFIX):
            raise ValueError("expected a Strata-issued reasoning replay token")
        try:
            payload = json.loads(self.cipher.decrypt(token[len(PREFIX):].encode("ascii")))
        except (InvalidToken, ValueError, UnicodeError) as exc:
            raise ValueError("reasoning replay token is invalid or belongs to a different deployment key") from exc
        if payload.get("version") != 1 or payload.get("model") != model or payload.get("id") != item.get("id"):
            raise ValueError("reasoning replay token does not match this model and item ID")
        if payload.get("status") != "completed":
            raise ValueError("only completed reasoning can be replayed")
        for key in ("content", "summary", "status"):
            if key in item and item[key] != payload[key]:
                raise ValueError(f"visible reasoning {key} conflicts with its replay token")
        return {**item, "content": payload["content"], "summary": payload["summary"]}
