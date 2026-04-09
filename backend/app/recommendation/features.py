from __future__ import annotations

from typing import Any

from app.chat.models import UserProfile


def build_profile_features(profile: UserProfile) -> dict[str, Any]:
    return {
        "target_region": profile.target_region,
        "current_stage": profile.current_stage,
        "interest_count": len(profile.interests),
        "avoidance_count": len(profile.avoidances),
        "priority_count": len(profile.priorities),
        "constraint_count": len(profile.constraints),
        "goal_keywords": profile.goals,
        "decision_pain": profile.decision_pain,
    }
