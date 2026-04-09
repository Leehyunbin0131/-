from __future__ import annotations

import json
from pathlib import Path

from app.chat.models import CounselingSession, utc_now


class SessionStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def create(self, session: CounselingSession) -> CounselingSession:
        session.updated_at = utc_now()
        self.save(session)
        return session

    def save(self, session: CounselingSession) -> CounselingSession:
        session.updated_at = utc_now()
        self.path_for(session.session_id).write_text(
            json.dumps(session.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return session

    def get(self, session_id: str) -> CounselingSession:
        path = self.path_for(session_id)
        if not path.exists():
            raise ValueError(f"Unknown session_id: {session_id}")
        return CounselingSession.model_validate(json.loads(path.read_text(encoding="utf-8")))

    def path_for(self, session_id: str) -> Path:
        return self.root / f"{session_id}.json"
