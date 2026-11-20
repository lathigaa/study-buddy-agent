"""
web_tools.py - free web research for Study Buddy (no API key needed).

- web_search: searches the web with the free `ddgs` library (Bing, Yahoo, DuckDuckGo...).
- read_webpage: downloads a page and turns it into plain text the AI can read.
- youtube_transcript: gets what is said in a YouTube video (from its captions).
"""

import ipaddress
import re
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx
from ddgs import DDGS

MAX_PAGE_CHARS = 12000  # keep pages short so we stay well inside the free limits
MAX_TRANSCRIPT_CHARS = 40000  # about a 45-60 minute lecture
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; StudyBuddy/1.0; +https://github.com)"}


# Free search engines the ddgs library can use. Any one can be down or busy at
# times, so we try them in turn until one gives results.
SEARCH_BACKENDS = ["auto", "bing", "yahoo", "google", "duckduckgo", "brave", "mojeek"]


def web_search(query: str, max_results: int = 6) -> str:
    """Search the web and return a numbered list of results (title, link, snippet)."""
    max_results = max(1, min(int(max_results), 10))
    results, last_error = [], None
    for backend in SEARCH_BACKENDS:
        try:
            results = DDGS(timeout=10).text(query, max_results=max_results, backend=backend)
        except Exception as e:  # network problems, rate limits, no results...
            last_error = e
            continue
        if results:
            break
    if not results:
        reason = f" ({type(last_error).__name__})" if last_error else ""
        return f"Web search found nothing{reason}. Try a shorter or different query, or answer from what you know."
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r.get('title', '').strip()}\n   {r.get('href', '')}\n   {r.get('body', '').strip()}")
    return "\n".join(lines)


class _TextExtractor(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "nav", "footer", "header", "form", "aside", "iframe"}
    BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "pre", "table"}

    MAIN = {"main", "article"}  # where the real content usually is

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []       # all visible text
        self.main_parts: list[str] = []  # text inside <main>/<article> only
        self.title = ""
        self._skip = 0
        self._main = 0
        self._in_title = False

    def _add(self, text: str):
        self.parts.append(text)
        if self._main:
            self.main_parts.append(text)

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip += 1
            return
        if tag in self.MAIN:
            self._main += 1
        if tag == "title":
            self._in_title = True
        elif tag in self.BLOCK:
            self._add("\n")
        if tag in ("h1", "h2", "h3"):
            self._add("## ")
        elif tag == "li":
            self._add("- ")

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self._skip = max(0, self._skip - 1)
        elif tag in self.MAIN:
            self._main = max(0, self._main - 1)
        elif tag == "title":
            self._in_title = False
        elif tag in self.BLOCK:
            self._add("\n")

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self._skip:
            self._add(data)

    def text(self) -> str:
        main = "".join(self.main_parts)
        raw = main if len(main.strip()) > 500 else "".join(self.parts)
        lines = [" ".join(line.split()) for line in raw.splitlines()]
        out, blank = [], False
        for line in lines:
            if line:
                out.append(line)
                blank = False
            elif not blank:
                out.append("")
                blank = True
        return "\n".join(out).strip()


def _is_public_url(url: str) -> bool:
    """Only allow normal public web pages (not files or this computer's local network)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    host = parsed.hostname.lower()
    if host == "localhost" or host.endswith(".local") or host.endswith(".localhost"):
        return False
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_global
    except ValueError:
        return True  # a normal domain name


_YT_ID = re.compile(r"(?:v=|youtu\.be/|shorts/|embed/|live/)([A-Za-z0-9_-]{11})")


def youtube_transcript(url_or_id: str) -> str:
    """Get the spoken text of a YouTube video (from its captions), with timestamps."""
    from youtube_transcript_api import YouTubeTranscriptApi

    match = _YT_ID.search(url_or_id)
    video_id = match.group(1) if match else url_or_id.strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        return "That doesn't look like a YouTube link."
    api = YouTubeTranscriptApi()
    try:
        try:
            fetched = api.fetch(video_id, languages=["en", "en-IN", "hi"])
        except Exception:
            # No English/Hindi captions: take whatever language exists.
            transcript = next(iter(api.list(video_id)))
            fetched = transcript.fetch()
    except Exception as e:
        return f"Couldn't get captions for this video ({type(e).__name__}). It may have no captions."

    lines, size = [], 0
    for s in fetched.snippets:
        minutes, seconds = divmod(int(s.start), 60)
        line = f"[{minutes}:{seconds:02d}] {s.text.strip()}"
        lines.append(line)
        size += len(line)
        if size > MAX_TRANSCRIPT_CHARS:
            lines.append("[...transcript shortened...]")
            break
    return f"Transcript of https://www.youtube.com/watch?v={video_id} (language: {fetched.language}):\n" + "\n".join(lines)


def read_webpage(url: str) -> str:
    """Download a web page and return its readable text (shortened)."""
    if not _is_public_url(url):
        return "Can only read public http(s) web pages."
    try:
        resp = httpx.get(url, headers=_HEADERS, timeout=20, follow_redirects=True)
        resp.raise_for_status()
    except Exception as e:
        return f"Could not open the page ({type(e).__name__}). Try another result."
    if not _is_public_url(str(resp.url)):
        return "Can only read public http(s) web pages."

    ctype = resp.headers.get("content-type", "")
    if "html" in ctype:
        parser = _TextExtractor()
        parser.feed(resp.text)
        title, text = parser.title.strip(), parser.text()
    elif ctype.startswith("text/") or "json" in ctype:
        title, text = "", resp.text
    else:
        return f"This page is not text (it is '{ctype}'), so it can't be read. Try another result."

    if not text:
        return "The page had no readable text. Try another result."
    if len(text) > MAX_PAGE_CHARS:
        text = text[:MAX_PAGE_CHARS] + "\n\n[...page shortened...]"
    header = f"Title: {title}\nURL: {resp.url}\n\n" if title else f"URL: {resp.url}\n\n"
    return header + text
