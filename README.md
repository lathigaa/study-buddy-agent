# 📚 Study Buddy — your free AI agent for exam & interview prep

**100% free to use.** It runs on Google's free Gemini API (no credit card) and free web search.

Give Study Buddy a topic and tell it what you need. It does the whole job: it researches, teaches you **your way**, makes notes and flashcards, plans your days, tests you, and **remembers your weak spots** between sessions.

## ✨ Features

| | What it does |
|---|---|
| 🔎 **Researches for you** | Searches the web, reads the best pages, and cites its sources |
| 📚 **Learns from your materials** | Upload your syllabus, textbook chapters, class notes or past papers (PDF/TXT/MD). It searches them first and teaches from them, citing the page |
| 🎥 **Turns YouTube lectures into notes** | Paste a lecture link and it reads the captions and makes notes and flashcards with timestamps |
| 🧑‍🏫 **Teaches your way** | Remembers how you like to learn (short points, simple words, Hinglish, examples…) |
| 🃏 **Flashcards with spaced repetition** | Makes flashcards after each topic. You review them in the app, and cards you forget come back sooner (like Anki) |
| 📅 **Study planner** | Builds a day-by-day plan up to your exam date. Tick off tasks and see what's overdue |
| ❓ **Quizzes & mock interviews** | One question at a time, with feedback and model answers |
| 🧠 **Remembers your weak topics** | Tracks 🔴 weak / 🟡 improving / 🟢 strong topics and every quiz score, and focuses practice on your gaps |
| 📊 **Progress dashboard** | Quiz scores over time, topic strengths, and your 🔥 study streak |
| 📝 **Saved notes** | Notes and cheat sheets you can read, download or delete |

### Try asking

> *Teach me DBMS normalization for my semester exam, then quiz me.*
> *Using my syllabus PDF, make a 30-day plan. My exam is on 7 Feb, I have 3 hours a day.*
> *Summarise this lecture into notes + flashcards: https://youtube.com/watch?v=…*
> *Mock interview for a data analyst fresher role, SQL and Excel focus.*
> *What should I study today?*

---

## 🚀 Setup (about 5 minutes, no coding needed)

### 1. Install Python
Download Python 3.10 or newer from [python.org/downloads](https://www.python.org/downloads/).
**Windows:** on the first install screen, tick **"Add python.exe to PATH"**.

### 2. Download Study Buddy
On this GitHub page, click the green **Code** button → **Download ZIP**, then unzip it.
(If you use Git: `git clone` this repo instead.)

### 3. Get a free Gemini API key (no credit card)
1. Go to [aistudio.google.com/apikey](https://aistudio.google.com/apikey) and sign in with your Google account.
2. Click **Create API key** and copy it.

That's it. Don't add billing; the free tier is all you need.

### 4. Start it
- **Windows:** double-click **`start.bat`**
- **Mac / Linux:** open a terminal in the folder and run `bash start.sh`

The first start installs what it needs (about a minute). Your browser then opens Study Buddy.
Paste your key in the sidebar and press **Enter**. Keep "Remember it on this computer" ticked so you only do this once.

---

## 🧠 Your data

Everything Study Buddy remembers is saved as plain files in the `data/` folder on **your** computer:

| File | What's in it |
|---|---|
| `profile.json` | Goal, learning style, weak/strong topics, quiz scores, study days |
| `flashcards.json` | Your flashcards and when each is due |
| `plan.json` | Your study plan |
| `notes/` | Notes and cheat sheets |
| `library/` | PDFs and notes you uploaded |

**Privacy:** the `data/` folder is never uploaded to GitHub. To answer, your messages, a summary of your profile, and the parts of your materials or web pages it reads are sent to Google's Gemini API. **On the free tier, Google may use what you send to improve its products**, so don't upload anything private.

---

## 💸 Cost: free

- Gemini's free tier has a **daily limit**. One question with web research uses a few requests.
- If one model runs out for the day, Study Buddy switches to the next free model automatically (`gemini-3.8-flash` → `gemini-3.6-flash` → `gemini-3.5-flash-lite`).
- The limit resets every day at midnight US Pacific time.
- To make it last longer: use **Answer depth → Quick**, and click **🆕 New chat** when you switch topics (your memory, notes and flashcards are kept).
- Flashcards, the study plan and the dashboard don't use the AI at all, so you can use them as much as you like.

See your exact limits at [aistudio.google.com](https://aistudio.google.com) → **Usage & limits**.

---

## 🛠️ How it works (for the curious)

An **agent** is an AI model + **tools** + a **loop**:

1. Your message goes to Gemini together with your current state (profile, weak topics, due flashcards, today's plan) and a list of tools it can use.
2. Gemini either answers, or asks to use a tool: search the web, read a page or your PDFs, get a YouTube transcript, save notes, make flashcards, save a plan, mark a topic as weak, record a quiz score…
3. The app runs the tool on your computer, sends back the result, and repeats until Gemini has finished.

| File | What's inside |
|---|---|
| `app.py` | The web page (built with [Streamlit](https://streamlit.io)) |
| `agent.py` | The agent: instructions (`SYSTEM_PROMPT`), tools (`FUNCTIONS`), and the loop |
| `web_tools.py` | Free web search, page reading, YouTube transcripts |
| `library.py` | Your uploaded materials: text extraction and search |
| `flashcards.py` | Flashcards and spaced-repetition scheduling |
| `planner.py` | The study plan |
| `memory.py` | Your profile, topics, quiz history, streak and notes |

**Make it your own:** edit `SYSTEM_PROMPT` in `agent.py` to change how it teaches, or add a new tool in `FUNCTIONS` + `run_tool()`.

---

## ❓ Troubleshooting

| Problem | Fix |
|---|---|
| `python is not recognized` | Reinstall Python and tick "Add python.exe to PATH" |
| "Your Gemini API key was rejected" | Copy the key again from aistudio.google.com/apikey, with no spaces |
| "You've used up today's free Gemini requests" | Wait for the daily reset. Meanwhile, review flashcards or your plan |
| "Web search found nothing" | The free search engines are busy for a moment. Wait a minute; Study Buddy still answers from what it knows |
| PDF "no text found" | It's a scanned PDF (just images). Use a PDF where you can select the text |
| Browser didn't open | Go to <http://localhost:8501> |

---

## License

MIT, free to use, change and share.
