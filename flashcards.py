"""
flashcards.py - flashcards with spaced repetition (saved in data/flashcards.json).

Spaced repetition = you see a card again right before you'd forget it.
Cards you get wrong come back soon; cards you know well come back after
longer and longer gaps (1 day, 3 days, a week, a month...). This is a
simplified version of the SM-2 method used by apps like Anki.
"""

import json
import uuid
from datetime import date, timedelta

import memory

GRADES = ("again", "hard", "good", "easy")


def _path():
    return memory.DATA_DIR / "flashcards.json"


def load_cards() -> list[dict]:
    try:
        cards = json.loads(_path().read_text(encoding="utf-8"))
        return cards if isinstance(cards, list) else []
    except (OSError, ValueError):
        return []


def save_cards(cards: list[dict]) -> None:
    memory.DATA_DIR.mkdir(parents=True, exist_ok=True)
    _path().write_text(json.dumps(cards, indent=2, ensure_ascii=False), encoding="utf-8")


def add_cards(deck: str, new_cards: list[dict]) -> str:
    """Add cards [{front, back}] to a deck. Skips exact duplicates."""
    deck = deck.strip() or "General"
    cards = load_cards()
    existing = {(c["deck"].lower(), c["front"].strip().lower()) for c in cards}
    today = date.today().isoformat()
    added = 0
    for c in new_cards:
        front, back = str(c.get("front", "")).strip(), str(c.get("back", "")).strip()
        if not front or not back or (deck.lower(), front.lower()) in existing:
            continue
        cards.append({
            "id": uuid.uuid4().hex[:10], "deck": deck, "front": front, "back": back,
            "created": today, "due": today, "interval": 0, "ease": 2.5, "reps": 0, "lapses": 0,
        })
        existing.add((deck.lower(), front.lower()))
        added += 1
    save_cards(cards)
    return f"Added {added} flashcards to deck '{deck}' (they're due for review today in the Flashcards tab)."


def decks(cards: list[dict] | None = None) -> list[str]:
    return sorted({c["deck"] for c in (cards if cards is not None else load_cards())})


def due_cards(deck: str | None = None, cards: list[dict] | None = None) -> list[dict]:
    today = date.today().isoformat()
    cards = cards if cards is not None else load_cards()
    due = [c for c in cards if c["due"] <= today and (deck in (None, "All decks") or c["deck"] == deck)]
    return sorted(due, key=lambda c: (c["due"], c["reps"]))


def review(card_id: str, grade: str) -> dict | None:
    """Record how well you remembered a card and schedule its next review."""
    if grade not in GRADES:
        raise ValueError(f"grade must be one of {GRADES}")
    cards = load_cards()
    card = next((c for c in cards if c["id"] == card_id), None)
    if card is None:
        return None

    if grade == "again":
        card["lapses"] += 1
        card["reps"] = 0
        card["interval"] = 0  # see it again in this session
        card["ease"] = max(1.3, card["ease"] - 0.2)
    else:
        if grade == "hard":
            interval = max(1, round(card["interval"] * 1.2))
            card["ease"] = max(1.3, card["ease"] - 0.15)
        else:
            if card["reps"] == 0:
                interval = 1
            elif card["reps"] == 1:
                interval = 3
            else:
                interval = max(card["interval"] + 1, round(card["interval"] * card["ease"]))
            if grade == "easy":
                interval = max(interval + 1, round(interval * 1.3))
                card["ease"] += 0.15
        card["interval"] = interval
        card["reps"] += 1
    card["due"] = (date.today() + timedelta(days=card["interval"])).isoformat()
    card["last_review"] = date.today().isoformat()
    save_cards(cards)
    return card


def delete_card(card_id: str) -> None:
    save_cards([c for c in load_cards() if c["id"] != card_id])


def summary() -> str:
    cards = load_cards()
    if not cards:
        return "No flashcards yet."
    due = due_cards(cards=cards)
    by_deck = {}
    for c in cards:
        by_deck[c["deck"]] = by_deck.get(c["deck"], 0) + 1
    hardest = sorted((c for c in cards if c["lapses"]), key=lambda c: -c["lapses"])[:3]
    text = f"{len(cards)} flashcards, {len(due)} due today. Decks: " + ", ".join(f"{d} ({n})" for d, n in by_deck.items())
    if hardest:
        text += ". Most-forgotten cards: " + "; ".join(f"'{c['front']}' ({c['lapses']}x)" for c in hardest)
    return text
