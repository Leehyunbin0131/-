from __future__ import annotations

from app.chat.models import UserProfile


def recommend_focus_areas(profile: UserProfile) -> list[str]:
    recommendations: list[str] = []
    if profile.current_stage:
        recommendations.append(f"compare outcomes for users in stage={profile.current_stage}")
    if profile.target_region:
        recommendations.append(f"prioritize data filtered by region={profile.target_region}")
    if profile.interests:
        recommendations.append("map interests to related majors, degrees, and employment indicators")
    if profile.priorities:
        recommendations.append(f"weight recommendations by priorities={', '.join(profile.priorities)}")
    if profile.avoidances:
        recommendations.append("exclude directions that conflict with the user's avoidances")
    if profile.constraints:
        recommendations.append("highlight options that acknowledge financial or geographic constraints")
    return recommendations
