"""
library.py - your own study materials (PDFs, notes) that the agent can search.

Uploaded files are stored in data/library/. We pull the text out once and
save it next to the file, then search it with a simple keyword ranking
(no paid services, works offline).
"""

import json
import math
import re
from collections import Counter

import memory

SUPPORTED = ("pdf", "txt", "md")
CHUNK_CHARS = 1500

_STOP = set("""a an and are as at be by for from has have how i in is it its of on or that the this to was
were what when where which who why will with you your do does did can could should would about into than
then them they there these those not no yes we our us me my explain define""".split())


def _dir():
    return memory.DATA_DIR / "library"


def _safe_name(name: str) -> str:
    stem, _, ext = name.rpartition(".")
    stem = re.sub(r"[^\w\- ]+", "", stem).strip()[:80] or "file"
    return f"{stem}.{ext.lower()}"


def add_file(filename: str, data: bytes) -> str:
    """Save an uploaded file and extract its text. Returns a status message."""
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext not in SUPPORTED:
        return f"'{filename}': only {', '.join(SUPPORTED)} files are supported."
    folder = _dir()
    folder.mkdir(parents=True, exist_ok=True)
    name = _safe_name(filename)
    path = folder / name
    path.write_bytes(data)

    try:
        if ext == "pdf":
            from pypdf import PdfReader
            reader = PdfReader(path)
            pages = [(p.extract_text() or "").strip() for p in reader.pages]
        else:
            text = data.decode("utf-8", errors="replace")
            pages = [text[i:i + 6000] for i in range(0, len(text), 6000)] or [""]
    except Exception as e:
        path.unlink(missing_ok=True)
        return f"'{filename}': couldn't read it ({type(e).__name__})."

    if not any(pages):
        path.unlink(missing_ok=True)
        return (f"'{filename}': no text found. It may be a scanned PDF (just images); "
                "try a PDF where you can select the text.")
    (folder / (name + ".json")).write_text(json.dumps({"name": name, "pages": pages}, ensure_ascii=False),
                                           encoding="utf-8")
    return f"Added '{name}' ({len(pages)} pages)."


def list_files() -> list[dict]:
    """[{name, pages}] for every material."""
    out = []
    for meta in sorted(_dir().glob("*.json")) if _dir().exists() else []:
        try:
            doc = json.loads(meta.read_text(encoding="utf-8"))
            out.append({"name": doc["name"], "pages": len(doc["pages"])})
        except (OSError, ValueError, KeyError):
            continue
    return out


def remove_file(name: str) -> None:
    (_dir() / name).unlink(missing_ok=True)
    (_dir() / (name + ".json")).unlink(missing_ok=True)


def _load(name: str) -> dict | None:
    meta = _dir() / (name + ".json")
    if not meta.exists():  # allow loose matching on the name
        for f in list_files():
            if name.lower() in f["name"].lower():
                meta = _dir() / (f["name"] + ".json")
                break
        else:
            return None
    try:
        return json.loads(meta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 1 and w not in _STOP]


def search(query: str, top_k: int = 5) -> str:
    """Find the passages in your materials that best match the query."""
    files = list_files()
    if not files:
        return "No study materials uploaded yet. (The learner can add PDFs/notes in the 'My materials' tab.)"
    chunks = []  # (file, page_no, text)
    for f in files:
        doc = _load(f["name"])
        for page_no, page in enumerate(doc["pages"] if doc else [], 1):
            for i in range(0, max(len(page), 1), CHUNK_CHARS):
                piece = page[max(0, i - 200): i + CHUNK_CHARS]  # small overlap between chunks
                if piece.strip():
                    chunks.append((f["name"], page_no, piece))
    terms = set(_words(query))
    if not terms:
        return "Search query has no useful words - try more specific terms."

    tokenized = [Counter(_words(c[2])) for c in chunks]
    n = len(chunks)
    idf = {t: math.log(1 + n / (1 + sum(1 for tok in tokenized if t in tok))) for t in terms}
    scored = []
    for (name, page_no, text), tok in zip(chunks, tokenized):
        score = sum((1 + math.log(tok[t])) * idf[t] for t in terms if tok[t])
        matched = sum(1 for t in terms if tok[t])
        if score:
            scored.append((score * (matched / len(terms)), name, page_no, text))
    if not scored:
        return f"No passages in the learner's materials matched '{query}'."
    scored.sort(key=lambda s: -s[0])
    out = []
    for score, name, page_no, text in scored[:top_k]:
        out.append(f"[{name}, page {page_no}]\n{' '.join(text.split())}")
    return "\n\n---\n\n".join(out)


def read(name: str, start_page: int = 1, end_page: int | None = None) -> str:
    """Read pages of one material (max ~15,000 characters at a time)."""
    doc = _load(name)
    if doc is None:
        names = ", ".join(f["name"] for f in list_files()) or "none"
        return f"No material called '{name}'. Available: {names}"
    pages = doc["pages"]
    start = max(1, start_page)
    end = min(len(pages), end_page or start + 4)
    out, size = [], 0
    for i in range(start, end + 1):
        text = pages[i - 1]
        if size + len(text) > 15000 and out:
            out.append(f"[stopped at page {i - 1}; ask for page {i} onward to continue]")
            break
        out.append(f"--- page {i} of {len(pages)} ---\n{text}")
        size += len(text)
    return f"{doc['name']}\n\n" + "\n\n".join(out)


def summary() -> str:
    files = list_files()
    if not files:
        return "No study materials uploaded."
    return "Uploaded materials: " + ", ".join(f"{f['name']} ({f['pages']} pages)" for f in files)
