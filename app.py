"""
app.py - the web page for Study Buddy (built with Streamlit).

Run it with:   streamlit run app.py
"""

import os
from datetime import date

import streamlit as st
from google.genai import errors

import flashcards
import library
import memory
import planner
from agent import MODELS, OutOfFreeQuota, StudyAgent

st.set_page_config(page_title="Study Buddy", page_icon="📚", layout="wide")

KEY_FILE = memory.DATA_DIR / "gemini_key.txt"  # only if you tick "remember"; data/ is never uploaded

DEPTH_OPTIONS = {"Quick": "low", "Balanced": "medium", "Deep": "high"}

EXAMPLES = [
    "Teach me DBMS normalization (1NF to BCNF) for my semester exam, then quiz me.",
    "Make a study plan for my exam. Ask me what you need to know.",
    "Mock interview for a data analyst fresher role - SQL and Excel focus.",
    "What should I study today?",
    "Summarise this lecture into notes + flashcards: <paste a YouTube link>",
    "Quiz me on my weak topics.",
]

STATUS_ICONS = {"weak": "🔴", "improving": "🟡", "strong": "🟢"}

for key, default in {"chat": [], "agent": None, "pending": None, "fc_show": False, "uploaded": set()}.items():
    if key not in st.session_state:
        st.session_state[key] = default


def new_chat():
    st.session_state.chat = []
    st.session_state.agent = None


def saved_key() -> str:
    try:
        return KEY_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


# ===========================================================================
# Sidebar: key, settings, profile
# ===========================================================================

with st.sidebar:
    st.title("📚 Study Buddy")

    env_key = os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")
    if env_key:
        api_key = env_key
        st.caption("✅ Using the Gemini key from your GEMINI_API_KEY environment variable.")
    elif saved_key():
        api_key = saved_key()
        st.caption("✅ Free Gemini key saved on this computer.")
        if st.button("Forget my key"):
            KEY_FILE.unlink(missing_ok=True)
            st.session_state.agent = None
            st.rerun()
    else:
        api_key = st.text_input(
            "Free Gemini API key",
            type="password",
            help="Free, no credit card: aistudio.google.com/apikey → Create API key. Paste it here and press Enter.",
        ).strip()
        st.caption("No key yet? Get one free at [aistudio.google.com/apikey](https://aistudio.google.com/apikey) "
                   "(sign in with Google → **Create API key**).")
        if api_key and st.checkbox("Remember it on this computer", value=True):
            memory.DATA_DIR.mkdir(parents=True, exist_ok=True)
            KEY_FILE.write_text(api_key, encoding="utf-8")

    depth = st.radio("Answer depth", list(DEPTH_OPTIONS), index=1, horizontal=True,
                     help="Deep = more careful answers, but slower and uses your free limit faster.")
    model = st.selectbox("AI model", MODELS, index=0,
                         help="All free. If one runs out of free uses for today, Study Buddy switches to the next.")
    if st.button("🆕 New chat", use_container_width=True):
        new_chat()
        st.rerun()

    st.divider()
    profile = memory.load_profile()
    streak = memory.streak(profile)
    st.subheader("🧠 What I know about you")
    if streak:
        st.markdown(f"🔥 **{streak}-day study streak**")
    due_count = len(flashcards.due_cards())
    if due_count:
        st.markdown(f"🃏 **{due_count} flashcard(s) due** — see the Flashcards tab")
    if profile["name"]:
        st.markdown(f"**Name:** {profile['name']}")
    st.markdown(f"**Goal:** {profile['goal'] or '_not set yet_'}")
    st.markdown(f"**Learning style:** {profile['learning_style'] or '_not set yet_'}")
    for pref in profile["preferences"]:
        st.markdown(f"- {pref}")

    with st.expander("✏️ Edit my profile"):
        with st.form("profile_form"):
            name = st.text_input("Name", profile["name"])
            goal = st.text_input("Goal", profile["goal"], placeholder="e.g. GATE CS 2027, or SDE fresher interviews")
            style = st.text_area("How you like to learn", profile["learning_style"],
                                 placeholder="e.g. simple words, real-life examples, short bullet points")
            if st.form_submit_button("Save"):
                profile.update(name=name.strip(), goal=goal.strip(), learning_style=style.strip())
                memory.save_profile(profile)
                st.rerun()
        confirm = st.checkbox("I want to erase my profile, topics and quiz history")
        if st.button("Reset memory", disabled=not confirm):
            memory.reset_profile()
            st.rerun()


# ===========================================================================
# Tabs
# ===========================================================================

# Tab names must stay the same between reruns, or Streamlit jumps back to the first tab.
tab_chat, tab_cards, tab_plan, tab_progress, tab_materials, tab_notes = st.tabs([
    "💬 Chat",
    "🃏 Flashcards",
    "📅 Study plan",
    "📊 Progress",
    "📚 My materials",
    "📝 Notes",
])


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

def run_agent(prompt: str):
    if not api_key:
        st.warning("First add your **free** Gemini API key in the sidebar "
                   "(get it at [aistudio.google.com/apikey](https://aistudio.google.com/apikey)).")
        return

    if st.session_state.agent is None:
        st.session_state.agent = StudyAgent(api_key=api_key, model=model)
        st.session_state.agent_model = model
    agent: StudyAgent = st.session_state.agent
    if st.session_state.get("agent_model") != model:  # user picked a different model
        agent.model = st.session_state.agent_model = model
    agent.depth = DEPTH_OPTIONS[depth]

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        status = st.status("Working on it…", expanded=False)
        placeholder = st.empty()
        reply = {"text": "", "steps": []}

        def on_text(chunk: str):
            reply["text"] += chunk
            placeholder.markdown(reply["text"] + "▌")

        def on_status(label: str):
            if not reply["steps"] or reply["steps"][-1] != label:
                reply["steps"].append(label)
                status.write(label)
            status.update(label=label + "…")

        def fail(message: str):
            status.update(label="Error", state="error")
            st.error(message)
            st.stop()

        try:
            agent.send(prompt, on_text, on_status)
        except OutOfFreeQuota:
            fail("You've used up today's free Gemini requests on every model. The free limit resets every day "
                 "at midnight US Pacific time (1:30 PM in India). Meanwhile, review your flashcards or study plan!")
        except errors.ClientError as e:
            text = str(e).lower()
            if e.code in (400, 401, 403) and ("api key" in text or "api_key" in text or "permission" in text):
                st.session_state.agent = None
                KEY_FILE.unlink(missing_ok=True)
                fail("Your Gemini API key was rejected. Copy it again from aistudio.google.com/apikey "
                     "and paste it in the sidebar.")
            fail(f"Gemini error {e.code}: {e.message or e}")
        except errors.ServerError:
            fail("Gemini is busy right now. Wait a minute and send your message again.")
        except Exception as e:  # usually no internet connection
            fail(f"Couldn't get an answer ({type(e).__name__}). "
                 "Check your internet connection and send your message again.")

        status.update(label=f"Done ({agent.model})", state="complete")
        placeholder.markdown(reply["text"])

    memory.log_study_day()
    st.session_state.chat.append({"role": "user", "text": prompt})
    st.session_state.chat.append({"role": "assistant", "text": reply["text"], "steps": reply["steps"]})
    st.rerun()  # refresh tabs (notes, flashcards, plan, profile may have changed)


with tab_chat:
    if not st.session_state.chat:
        st.header("Your exam & interview prep assistant")
        st.markdown(
            "Give me a topic and tell me what you need: notes, a quiz, flashcards, a study plan or a mock "
            "interview. I research it (the web, YouTube lectures, **your own PDFs**), teach it your way, and "
            "remember your weak spots."
        )
        cols = st.columns(2)
        for i, example in enumerate(EXAMPLES):
            if cols[i % 2].button(example, key=f"ex-{i}", use_container_width=True):
                st.session_state.pending = example
                st.rerun()

    for msg in st.session_state.chat:
        with st.chat_message(msg["role"]):
            if msg.get("steps"):
                with st.expander("What I did", expanded=False):
                    for step in msg["steps"]:
                        st.markdown(f"- {step}")
            st.markdown(msg["text"])

    prompt = st.chat_input("Topic + what you want, e.g. 'OS deadlocks: notes + 5 tricky questions'")
    if st.session_state.pending:
        prompt, st.session_state.pending = st.session_state.pending, None
    if prompt:
        run_agent(prompt)


# ---------------------------------------------------------------------------
# Flashcards (spaced repetition)
# ---------------------------------------------------------------------------

with tab_cards:
    cards = flashcards.load_cards()
    if not cards:
        st.info("No flashcards yet. Ask in the chat, e.g. *'Make flashcards on SQL joins'*, "
                "or add your own below.")
    else:
        deck = st.selectbox("Deck", ["All decks"] + flashcards.decks(cards))
        due = flashcards.due_cards(deck, cards)
        st.caption(f"{len(due)} card(s) due now · {len(cards)} total")

        if not due:
            st.success("🎉 All caught up! Come back tomorrow for your next reviews.")
        else:
            card = due[0]
            with st.container(border=True):
                st.caption(card["deck"])
                st.markdown(f"### {card['front']}")
                if st.session_state.fc_show:
                    st.divider()
                    st.markdown(card["back"])
            if not st.session_state.fc_show:
                if st.button("Show answer", type="primary"):
                    st.session_state.fc_show = True
                    st.rerun()
            else:
                st.write("How well did you remember it?")
                cols = st.columns(4)
                labels = {"again": "😵 Forgot", "hard": "😬 Hard", "good": "🙂 Good", "easy": "😎 Easy"}
                for col, grade in zip(cols, flashcards.GRADES):
                    if col.button(labels[grade], key=f"grade-{grade}", use_container_width=True):
                        flashcards.review(card["id"], grade)
                        st.session_state.fc_show = False
                        memory.log_study_day()
                        st.rerun()
                st.caption("Forgot = see it again today · Hard/Good/Easy = see it again in a few days or later")

        with st.expander(f"Browse all cards ({len(cards)})"):
            for c in sorted(cards, key=lambda c: (c["deck"], c["due"])):
                col1, col2 = st.columns([6, 1])
                col1.markdown(f"**{c['front']}**  \n{c['back']}  \n"
                              f"<small>{c['deck']} · next review {c['due']}</small>", unsafe_allow_html=True)
                if col2.button("🗑️", key=f"del-{c['id']}", help="Delete card"):
                    flashcards.delete_card(c["id"])
                    st.rerun()

    with st.expander("➕ Add a card yourself"):
        with st.form("add_card", clear_on_submit=True):
            deck_name = st.text_input("Deck", placeholder="e.g. Operating Systems")
            front = st.text_input("Front (question)")
            back = st.text_area("Back (answer)")
            if st.form_submit_button("Add card") and front and back:
                st.success(flashcards.add_cards(deck_name or "General", [{"front": front, "back": back}]))


# ---------------------------------------------------------------------------
# Study plan
# ---------------------------------------------------------------------------

with tab_plan:
    plan = planner.load_plan()
    if not plan["days"]:
        st.info("No study plan yet. Ask in the chat, e.g. *'Make me a 30-day plan for GATE CS, "
                "exam on 2027-02-07, 3 hours a day'*.")
    else:
        st.subheader(plan["title"] or "My study plan")
        done, total = planner.progress(plan)
        left = planner.days_left(plan)
        c1, c2, c3 = st.columns(3)
        c1.metric("Tasks done", f"{done}/{total}")
        if left is not None:
            c2.metric("Days to exam", left if left >= 0 else "Done")
        c3.metric("Streak", f"🔥 {memory.streak()}")
        st.progress(done / total if total else 0.0)

        today = date.today().isoformat()
        for di, day in enumerate(plan["days"]):
            d = date.fromisoformat(day["date"])
            day_done = all(t["done"] for t in day["tasks"])
            if day["date"] == today:
                label = f"📍 Today · {d.strftime('%a %d %b')}"
            elif day["date"] < today and not day_done:
                label = f"⚠️ {d.strftime('%a %d %b')} (overdue)"
            else:
                label = ("✅ " if day_done else "") + d.strftime("%a %d %b")
            with st.expander(label, expanded=(day["date"] == today)):
                for ti, task in enumerate(day["tasks"]):
                    checked = st.checkbox(task["text"], value=task["done"], key=f"task-{day['date']}-{ti}")
                    if checked != task["done"]:
                        planner.set_done(di, ti, checked)
                        if checked:
                            memory.log_study_day()
                        st.rerun()


# ---------------------------------------------------------------------------
# Progress dashboard
# ---------------------------------------------------------------------------

with tab_progress:
    profile = memory.load_profile()
    quizzes = profile["quiz_history"]
    cards = flashcards.load_cards()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Streak (days)", f"🔥 {memory.streak(profile)}")
    c2.metric("Quizzes taken", len(quizzes))
    if quizzes:
        avg = sum(q["score"] / q["total"] for q in quizzes if q["total"]) / max(1, len(quizzes))
        c3.metric("Average score", f"{round(100 * avg)}%")
    c4.metric("Flashcards due", len(flashcards.due_cards(cards=cards)))

    if quizzes:
        st.subheader("Quiz scores over time")
        st.line_chart(
            {"Score %": [round(100 * q["score"] / q["total"]) if q["total"] else 0 for q in quizzes]},
            x_label="Quiz number", y_label="Score %",
        )
        with st.expander("All quizzes"):
            for q in reversed(quizzes):
                mistakes = f" — missed: {', '.join(q['mistakes'])}" if q.get("mistakes") else ""
                st.markdown(f"- {q['date']} · **{q['topic']}**: {q['score']}/{q['total']}{mistakes}")

    st.subheader("Topics")
    if not profile["topics"]:
        st.caption("Topics appear here as you study and take quizzes.")
    else:
        cols = st.columns(3)
        for col, status in zip(cols, memory.TOPIC_STATUSES):
            col.markdown(f"**{STATUS_ICONS[status]} {status.capitalize()}**")
            for topic, info in profile["topics"].items():
                if info.get("status") == status:
                    col.markdown(f"- **{topic}**" + (f"  \n  <small>{info['notes']}</small>" if info.get("notes") else ""),
                                 unsafe_allow_html=True)
        weak = [t for t, i in profile["topics"].items() if i.get("status") == "weak"]
        if weak and st.button(f"🎯 Practise my weak topics ({len(weak)})"):
            st.session_state.pending = "Quiz me on my weak topics: " + ", ".join(weak)
            st.rerun()

    if profile["study_days"]:
        st.subheader("Days studied (last 4 weeks)")
        last = [date.fromordinal(date.today().toordinal() - i).isoformat() for i in range(27, -1, -1)]
        days = set(profile["study_days"])
        st.markdown(" ".join("🟩" if d in days else "⬜" for d in last))


# ---------------------------------------------------------------------------
# My materials (PDF / notes upload)
# ---------------------------------------------------------------------------

with tab_materials:
    st.markdown("Upload your **syllabus, textbook chapters, class notes or past papers**. "
                "Study Buddy searches them first and teaches from them, citing the page.")
    uploads = st.file_uploader("Add files (PDF, TXT, MD)", type=list(library.SUPPORTED), accept_multiple_files=True)
    for up in uploads or []:
        marker = (up.name, up.size)
        if marker not in st.session_state.uploaded:
            with st.spinner(f"Reading {up.name}…"):
                message = library.add_file(up.name, up.getvalue())
            st.session_state.uploaded.add(marker)
            (st.success if message.startswith("Added") else st.warning)(message)

    files = library.list_files()
    if files:
        st.subheader("Your materials")
        for f in files:
            col1, col2 = st.columns([6, 1])
            col1.markdown(f"📄 **{f['name']}** · {f['pages']} pages")
            if col2.button("Remove", key=f"rm-{f['name']}"):
                library.remove_file(f["name"])
                st.rerun()
        st.caption("Try: *'Using my syllabus, make a study plan'* or *'Explain chapter 3 of my notes, then quiz me'*.")


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------

with tab_notes:
    notes = memory.list_notes()
    if not notes:
        st.info("Notes Study Buddy makes for you will appear here.")
    for path in notes:
        with st.expander(path.stem.replace("-", " ").title()):
            text = path.read_text(encoding="utf-8")
            st.markdown(text)
            col1, col2 = st.columns(2)
            col1.download_button("⬇️ Download", text, file_name=path.name, key=f"dl-{path.name}")
            if col2.button("🗑️ Delete", key=f"delnote-{path.name}"):
                path.unlink(missing_ok=True)
                st.rerun()
