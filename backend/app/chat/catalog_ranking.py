from __future__ import annotations

from app.chat.admissions_files import AdmissionsFileCandidate, structured_input_tier
from app.chat.models import UserProfile


def _candidate_text(candidate: AdmissionsFileCandidate) -> str:
    return f"{candidate.school_name or ''} {candidate.title} {candidate.source_path}"


def score_admissions_candidate(profile: UserProfile, candidate: AdmissionsFileCandidate) -> float:
    """Higher = more relevant to this user for LLM file-input batches (prototype heuristic)."""
    text = _candidate_text(candidate)
    score = 0.0
    if candidate.kind == "result":
        score += 1.0
    for field in profile.interest_fields:
        stripped = (field or "").strip()
        if stripped and stripped in text:
            score += 2.0
    for track in profile.track_preferences:
        stripped = (track or "").strip()
        if stripped and stripped in text:
            score += 2.0
    for blocked in profile.blocked_tracks:
        stripped = (blocked or "").strip()
        if stripped and stripped in text:
            score -= 3.0
    return score


def rank_and_cap_admissions_candidates(
    profile: UserProfile,
    candidates: list[AdmissionsFileCandidate],
    *,
    max_files: int,
) -> list[AdmissionsFileCandidate]:
    if max_files <= 0 or len(candidates) <= max_files:
        return list(candidates)
    ranked = sorted(
        candidates,
        key=lambda c: (
            -score_admissions_candidate(profile, c),
            structured_input_tier(c.path),
            c.kind != "result",
            c.source_path,
        ),
    )
    return ranked[:max_files]
