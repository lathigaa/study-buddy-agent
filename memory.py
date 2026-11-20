"""
memory.py - the agent's long-term memory about YOU.

Everything is saved as plain files in the `data/` folder next to this file:
  data/profile.json   - your goals, learning style, preferences, weak/strong topics, quiz history
  data/notes/*.md     - study notes the agent wrote for you
  (flashcards.py, planner.py and library.py keep their files in data/ too)

The `data/` folder is in .gitignore, so your personal data is never uploaded to GitHub.
"""

import json
import re
from datetime import date
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
PROFILE_PATH = DATA_DIR / "profile.json"
NOTES_DIR = DATA_DIR / "notes"

TOPIC_STATUSES = ("weak", "improving", "strong")

EMPTY_PROFILE = {
    "name": "",
    "goal": "",            # e.g. "GATE CS 2027" or "Data analyst fresher interviews"
    "learning_style": "",  # e.g. "simple language, real-life examples, short bullet points"
    "preferences": [],     # other things the agent learned about you
    "topics": {},          # topic -> {"status": "weak|improving|strong", "notes": str, "updated": date}
    "quiz_history": [],    # [{"date", "topic", "score", "total", "mistakes": [...]}]
    "study_days": [],      # dates you studied, for your streak
}


def _today() -> str:
    return date.today().isoformat()


def load_profile() -> dict:
    if not PROFILE_PATH.exists():
        return json.loads(json.dumps(EMPTY_PROFILE))  # deep copy
    try:
        profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return json.loads(json.dumps(EMPTY_PROFILE))
    # Fill in any keys added in newer versions of the app.
    for key, value in EMPTY_PROFILE.items():
        profile.setdefault(key, json.loads(json.dumps(value)))
    return profile


def save_profile(profile: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROFILE_PATH.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")


def reset_profile() -> None:
    if PROFILE_PATH.exists():
        PROFILE_PATH.unlink()


def profile_summary(profile: dict) -> str:
    """A short text version of the profile that we put in the agent's instructions."""
    if not any([profile["name"], profile["goal"], profile["learning_style"],
                profile["preferences"], profile["topics"], profile["quiz_history"]]):
        return "(Empty - this is a new user. Get to know them first.)"

    lines = []
    if profile["name"]:
        lines.append(f"Name: {profile['name']}")
    if profile["goal"]:
        lines.append(f"Goal: {profile['goal']}")
    if profile["learning_style"]:
        lines.append(f"Learning style: {profile['learning_style']}")
    if profile["preferences"]:
        lines.append("Other preferences / facts:")
        lines += [f"  - {p}" for p in profile["preferences"]]

    for status in TOPIC_STATUSES:
        topics = [(t, info) for t, info in profile["topics"].items() if info.get("status") == status]
        if topics:
            lines.append(f"{status.capitalize()} topics:")
            for topic, info in topics:
                note = f" - {info['notes']}" if info.get("notes") else ""
                lines.append(f"  - {topic}{note} (updated {info.get('updated', '?')})")

    recent = profile["quiz_history"][-5:]
    if recent:
        lines.append("Recent quiz results:")
        for q in recent:
            mistakes = f"; mistakes: {', '.join(q['mistakes'])}" if q.get("mistakes") else ""
            lines.append(f"  - {q['date']} {q['topic']}: {q['score']}/{q['total']}{mistakes}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Actions the agent can take (called from agent.py tools)
# ---------------------------------------------------------------------------

def update_profile(field: str, value: str) -> str:
    profile = load_profile()
    value = value.strip()
    if field in ("name", "goal", "learning_style"):
        profile[field] = value
    elif field == "preference":
        if value not in profile["preferences"]:
            profile["preferences"].append(value)
    elif field == "remove_preference":
        before = len(profile["preferences"])
        profile["preferences"] = [p for p in profile["preferences"] if p.lower() != value.lower()]
        if len(profile["preferences"]) == before:
            return f"No saved preference matched '{value}'. Current: {profile['preferences']}"
    else:
        return f"Unknown field '{field}'."
    save_profile(profile)
    return f"Saved {field}: {value}"


def set_topic_status(topic: str, status: str, notes: str = "") -> str:
    if status not in TOPIC_STATUSES:
        return f"status must be one of {TOPIC_STATUSES}"
    profile = load_profile()
    # Match existing topics case-insensitively so "dbms" and "DBMS" are the same.
    key = next((t for t in profile["topics"] if t.lower() == topic.lower()), topic.strip())
    profile["topics"][key] = {"status": status, "notes": notes.strip(), "updated": _today()}
    save_profile(profile)
    return f"Marked '{key}' as {status}."


def record_quiz(topic: str, score: int, total: int, mistakes: list[str]) -> str:
    profile = load_profile()
    profile["quiz_history"].append({
        "date": _today(), "topic": topic, "score": score, "total": total, "mistakes": mistakes,
    })
    profile["quiz_history"] = profile["quiz_history"][-200:]  # keep the file small
    save_profile(profile)
    pct = round(100 * score / total) if total else 0
    return f"Recorded {topic}: {score}/{total} ({pct}%)."


def log_study_day() -> None:
    """Remember that you studied today (for the streak)."""
    profile = load_profile()
    if _today() not in profile["study_days"]:
        profile["study_days"] = (profile["study_days"] + [_today()])[-400:]
        save_profile(profile)


def streak(profile: dict | None = None) -> int:
    """How many days in a row you've studied (counting today or yesterday)."""
    days = set((profile or load_profile())["study_days"])
    current = date.today()
    if current.isoformat() not in days:
        current = current.fromordinal(current.toordinal() - 1)
    count = 0
    while current.isoformat() in days:
        count += 1
        current = current.fromordinal(current.toordinal() - 1)
    return count


def _slug(title: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", title).strip("-").lower()
    return slug[:80] or "notes"


def save_note(title: str, content: str) -> str:
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    path = NOTES_DIR / f"{_slug(title)}.md"
    path.write_text(f"# {title}\n\n_Saved {_today()}_\n\n{content.strip()}\n", encoding="utf-8")
    return f"Saved notes as '{path.name}'."


def list_notes() -> list[Path]:
    if not NOTES_DIR.exists():
        return []
    return sorted(NOTES_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)


def read_note(name: str) -> str:
    wanted = _slug(name.removesuffix(".md"))
    for path in list_notes():
        if path.stem == wanted:
            return path.read_text(encoding="utf-8")
    names = ", ".join(p.stem for p in list_notes()) or "none yet"
    return f"No note called '{name}'. Saved notes: {names}"
