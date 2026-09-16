import json
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
PROFILE_FILE = PROJECT_DIR / "profile.json"


def load_profile() -> dict:
    with PROFILE_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def profile_to_text(profile: dict) -> str:
    lines = []
    basics = profile.get("basics", {})
    lines.append(f"Name: {basics.get('name', '')}")
    lines.append(f"Label: {basics.get('label', '')}")
    lines.append(f"Email: {basics.get('email', '')}")
    lines.append(f"Phone: {basics.get('phone', '')}")
    loc = basics.get("location", {})
    lines.append(
        f"Location: {', '.join(x for x in [loc.get('city', ''), loc.get('region', ''), loc.get('country', '')] if x)}"
    )
    lines.append(f"PIN: {loc.get('pin', '')}")
    links = "; ".join(f"{p.get('network')}: {p.get('url')}" for p in basics.get("profiles", []))
    lines.append(f"Profiles: {links}")

    prefs = profile.get("jobPreferences", {})
    for k, v in prefs.items():
        if isinstance(v, list):
            lines.append(f"{k}: {', '.join(str(x) for x in v)}")
        elif isinstance(v, bool):
            lines.append(f"{k}: {'Yes' if v else 'No'}")
        else:
            lines.append(f"{k}: {v}")

    skills = profile.get("skills", {})
    if skills:
        lines.append(f"Skills: {', '.join(sorted(skills.keys()))}")

    edu = []
    for e in profile.get("education", []):
        edu.append(
            f"{e.get('area', '')} ({e.get('studyType', '')}) at {e.get('institution', '')}, {e.get('location', '')} "
            f"{e.get('startDate', '')} to {e.get('endDate', '')} | score: {e.get('score', '')}"
        )
    if edu:
        lines.append("Education: " + " | ".join(edu))

    return "\n".join(lines)