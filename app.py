"""
Resume Bullet Doctor – Streamlit app
• Assistant greets first and asks for target role / industry
• Runs an ARM/STAR interview loop until it can craft one quantified bullet
• Refuses to accept a bullet without at least one number
"""

# ── Imports ────────────────────────────────────────────────────────────────
import re, os
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

# ── OpenAI client ──────────────────────────────────────────────────────────
load_dotenv()                      # .env when running locally
client = OpenAI()                  # OPENAI_API_KEY picked up from env

# ── Streamlit UI config ────────────────────────────────────────────────────
st.set_page_config(page_title="Resume Helper", page_icon="📄")
st.title("📄 Resume Helper")

# ── Master system prompt ───────────────────────────────────────────────────
SYSTEM_PROMPT = """
You are a **Master Resume Writer** who turns rough job statements into
succinct, quantified bullets using ARM (Action-Result-Measure) or
STAR (Situation-Task-Action-Result).

──────────────────────────────── SESSION START ─────────────────────────────
Your FIRST message must be:
“What specific role / industry are you targeting?”

Save that reply as TARGET_ROLE and mention it in every follow-up question
and final bullet.

────────────────────────── INTERVIEW LOOP (per rough point) ───────────────
1. WHAT exactly did you do?  
2. HOW did you do it? (tools, methods, collaborators)  
3. WHY did you do it? (business goal; apply 5 WHYs)  
4. RESULT / METRICS? (%, $, time saved, volume, scale, awards)

If the user says “I don't know”, “not sure”, or gives no numbers:  
• Probe from another angle—team size, frequency, timeframe, qualitative proof.  
• Ask **≤ 2** concise questions each round.  
• **Never** produce a final bullet until at least one numeric or scaled detail
  is obtained.

──────────────────────────── OUTPUT RULES ─────────────────────────────────
When ready, respond with:
BULLET READY: • <one bullet ≤ 25 words, strong verb, contains a NUMBER or scale>

Write **one bullet at a time**, then wait for the user.

If the user wants tweaks, iterate on the same bullet;
if they paste a new rough point, restart the loop.
"""

# ── Session-state setup ───────────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []

if "system_added" not in st.session_state:
    st.session_state.history.insert(0, {"role": "system", "content": SYSTEM_PROMPT})
    st.session_state.system_added = True

if "asked_role" not in st.session_state:
    st.session_state.asked_role = False     # have we asked the question?

if "target_role" not in st.session_state:
    st.session_state.target_role = None     # user answer stored here

if "bullets" not in st.session_state:
    st.session_state.bullets = []

# ── Ask for role / industry exactly once ──────────────────────────────────
if not st.session_state.asked_role:
    q = "What specific role / industry are you targeting?"
    st.session_state.history.append({"role": "assistant", "content": q})
    st.session_state.asked_role = True

# ── Helper: call GPT with role reminder ───────────────────────────────────
def ask_llm(history):
    role_note = {
        "role": "user",
        "content": f"(Reminder) Target role / industry: {st.session_state.target_role}"
    }
    messages = [history[0], role_note] + history[1:]
    return client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        stream=True,
    )

# ── Helper: ensure bullet contains at least one digit ─────────────────────
def bullet_has_number(text: str) -> bool:
    return bool(re.search(r"\d", text))

# ── Replay previous chat (skip system msg) ────────────────────────────────
for msg in st.session_state.history:
    if msg["role"] == "system":
        continue
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ── Main chat input ───────────────────────────────────────────────────────
if prompt := st.chat_input("Paste a rough bullet, or answer the question above…"):

    # Show user bubble
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.history.append({"role": "user", "content": prompt})

    # 1️⃣  Capture target role / industry
    if st.session_state.target_role is None:
        st.session_state.target_role = prompt.strip()
        ack = (f"Great — I'll tailor every bullet for **{st.session_state.target_role}**. "
               "Now paste your first rough point whenever you’re ready.")
        with st.chat_message("assistant"):
            st.markdown(ack)
        st.session_state.history.append({"role": "assistant", "content": ack})
        st.stop()   # don’t fall through to GPT on this message

    # 2️⃣  Otherwise pass full history to GPT
    with st.chat_message("assistant"):
        stream = ask_llm(st.session_state.history)
        full_response = st.write_stream(stream)
    st.session_state.history.append({"role": "assistant",
                                     "content": full_response})

    # 2a. If GPT produced a bullet, validate & stash
    if full_response.startswith("BULLET READY:"):
        cleaned = full_response.replace("BULLET READY:", "").lstrip("• ").strip()
        if bullet_has_number(cleaned):
            st.session_state.bullets.append(cleaned)
        else:
            need_num = ("I still need at least one number to show scale or impact "
                        "(team size, %, $, time).  Can you estimate any of those?")
            with st.chat_message("assistant"):
                st.markdown(need_num)
            st.session_state.history.append({"role": "assistant",
                                             "content": need_num})

# ── Sidebar: harvested bullets ────────────────────────────────────────────
with st.sidebar:
    st.header("📌 Draft bullets")
    if st.session_state.bullets:
        for b in st.session_state.bullets:
            st.markdown(f"• {b}")
    else:
        st.write("No bullets yet — answer the questions to generate one.")
    if st.button("🔄 Reset bullets"):
        st.session_state.bullets.clear()
