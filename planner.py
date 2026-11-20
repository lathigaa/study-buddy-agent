"""
planner.py - your day-by-day study plan (saved in data/plan.json).
"""

import json
from datetime import date

import memory


def _path():
    return memory.DATA_DIR / "plan.json"


def load_plan() -> dict:
    try:
        plan = json.loads(_path().read_text(encoding="utf-8"))
        if isinstance(plan, dict) and isinstance(plan.get("days"), list):
            return plan
    except (OSError, ValueError):
        pass
    return {"title": "", "exam_date": "", "days": []}


def save_plan_data(plan: dict) -> None:
    memory.DATA_DIR.mkdir(parents=True, exist_ok=True)
    _path().write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")


def _valid_date(text: str) -> bool:
    try:
        date.fromisoformat(text)
        return True
    except (TypeError, ValueError):
        return False


def save_plan(title: str, exam_date: str, days: list[dict]) -> str:
    """Replace the study plan. days = [{date: 'YYYY-MM-DD', tasks: [str, ...]}]."""
    if exam_date and not _valid_date(exam_date):
        return f"exam_date '{exam_date}' is not a valid YYYY-MM-DD date - try again."
    clean = []
    for d in days:
        if not isinstance(d, dict) or not _valid_date(d.get("date")):
            return f"Every day needs a valid 'date' in YYYY-MM-DD format (got {d!r:.80}) - try again."
        tasks = [str(t).strip() for t in d.get("tasks", []) if str(t).strip()]
        if tasks:
            clean.append({"date": d["date"], "tasks": [{"text": t, "done": False} for t in tasks]})
    if not clean:
        return "The plan had no days with tasks - try again."
    clean.sort(key=lambda d: d["date"])
    save_plan_data({"title": title.strip(), "exam_date": exam_date or "", "days": clean})
    n = sum(len(d["tasks"]) for d in clean)
    return f"Saved study plan '{title}' with {len(clean)} days and {n} tasks (see the Study plan tab)."


def set_done(day_index: int, task_index: int, done: bool) -> None:
    plan = load_plan()
    try:
        plan["days"][day_index]["tasks"][task_index]["done"] = done
    except (IndexError, KeyError):
        return
    save_plan_data(plan)


def progress(plan: dict | None = None) -> tuple[int, int]:
    plan = plan or load_plan()
    tasks = [t for d in plan["days"] for t in d["tasks"]]
    return sum(t["done"] for t in tasks), len(tasks)


def days_left(plan: dict | None = None) -> int | None:
    plan = plan or load_plan()
    if not _valid_date(plan.get("exam_date")):
        return None
    return (date.fromisoformat(plan["exam_date"]) - date.today()).days


def summary() -> str:
    plan = load_plan()
    if not plan["days"]:
        return "No study plan yet."
    done, total = progress(plan)
    today = date.today().isoformat()
    lines = [f"Plan '{plan['title']}': {done}/{total} tasks done."]
    left = days_left(plan)
    if left is not None:
        lines.append(f"Exam on {plan['exam_date']} ({left} days left).")
    todays = [d for d in plan["days"] if d["date"] == today]
    if todays:
        lines.append("Today's tasks: " + "; ".join(
            ("[done] " if t["done"] else "[todo] ") + t["text"] for t in todays[0]["tasks"]))
    overdue = [t["text"] for d in plan["days"] if d["date"] < today for t in d["tasks"] if not t["done"]]
    if overdue:
        lines.append(f"{len(overdue)} overdue tasks, e.g.: " + "; ".join(overdue[:3]))
    return " ".join(lines)
