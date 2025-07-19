"""
Resume Bullet Doctor – Streamlit app
• Collects target role / industry first
• Runs an ARM/STAR interview loop until it can craft one quantified bullet
• Refuses to accept a bullet without at least one number
"""

# ── Imports ────────────────────────────────────────────────────────────────
import re
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

# ── OpenAI client ──────────────────────────────────────────────────────────
load_dotenv()          # expects OPENAI_API_KEY in .env
client = OpenAI()      # key picked up from environment

# ── Streamlit UI config ────────────────────────────────────────────────────
st.set_page_config(page_title="Resume Bullet Doctor", page_icon="📄")
st.title("📄 Resume Bullet Doctor")

# ── Master system prompt ───────────────────────────────────────────────────
SYSTEM_PROMPT = """
You are a **Master Resume Writer** who turns rough job statements into
succinct, quantified bullets using ARM (Action - Result - Measure) or
STAR (Situation-Task-Action-Result).

──────────────────────────────── SESSION START ─────────────────────────────
Your FIRST message in every new session must be:
“What specific role / industry are you targeting?”

Save that reply as **TARGET_ROLE** and mention it in every follow-up
question and final bullet.

────────────────────────── INTERVIEW LOOP (per rough point) ───────────────
1. WHAT exactly did you do?  
2. HOW did you do it? (tools, methods, collaborators)  
3. WHY did you do it? (business goal; apply 5 WHYs)  
4. RESULT / METRICS? (%, $, time saved, volume, scale, awards)

If the user answers “I don’t know,” “not sure,” or gives no numbers:  
• Probe from a different angle—team size, frequency, timeframe, qualitative
  proof (awards, praise, urgency).  
• Ask **no more than two** crisp questions in each probing round.  
• **Do NOT** produce a final bullet until **at least one** numeric or clearly
  scaled detail is obtained.

──────────────────────────── OUTPUT RULES ─────────────────────────────────
When you have sufficient data, respond with exactly:

BULLET READY: • <one bullet ≤ 25 words, starts with a strong verb, contains at
least one NUMBER or explicit scale indicator, aligned to TARGET_ROLE>

Write **only one bullet at a time**, then wait for the user.

──────────────────────────── REVIEW / IMPROVE ─────────────────────────────
If the user requests tweaks, ask focused follow-ups and revise the *same*
bullet until they approve.

If the user supplies a **new** rough point, restart the Interview Loop.
"""


# ── Session-state setup ────────────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []

if "system_added" not in st.session_state:
    st.session_state.history.insert(0, {"role": "system", "content": SYSTEM_PROMPT})
    st.session_state.system_added = True

if "target_role" not in st.session_state:
    st.session_state.target_role = None          # not captured yet

if "bullets" not in st.session_state:
    st.session_state.bullets = []

# ── Helper: call GPT with role reminder ────────────────────────────────────
def ask_llm(history):
    role_note = {
        "role": "user",
        "content": f"(Reminder) Target role / industry: {st.session_state.target_role}"
    }
    # history[0] is the system prompt
    messages = [history[0], role_note] + history[1:]
    return client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        stream=True,
    )

# ── Helper: ensure bullet contains at least one digit ─────────────────────
def bullet_has_number(text: str) -> bool:
    return bool(re.search(r"\d", text))

# ── Replay previous chat (hide system msg) ────────────────────────────────
for msg in st.session_state.history:
    if msg["role"] == "system":
        continue
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ── Main chat input box ────────────────────────────────────────────────────
if prompt := st.chat_input("Paste a rough bullet, or answer the question above…"):

    # Show user bubble
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.history.append({"role": "user", "content": prompt})

    # 1️⃣  If target role not yet captured, save and acknowledge
    if st.session_state.target_role is None:
        st.session_state.target_role = prompt
        ack = (f"Great — I’ll tailor every bullet for **{prompt}**. "
               "Now paste your first rough point whenever you’re ready.")
        with st.chat_message("assistant"):
            st.markdown(ack)
        st.session_state.history.append({"role": "assistant", "content": ack})

    # 2️⃣  Otherwise pass full history to GPT
    else:
        with st.chat_message("assistant"):
            stream = ask_llm(st.session_state.history)
            full_response = st.write_stream(stream)
        st.session_state.history.append({"role": "assistant",
                                         "content": full_response})

        # 2a. If GPT produced a bullet, validate & stash
        if full_response.startswith("BULLET READY:"):
            cleaned = full_response.replace("BULLET READY:", "").strip()
            cleaned = cleaned.lstrip("• ").strip()
            if bullet_has_number(cleaned):
                st.session_state.bullets.append(cleaned)
            else:
                # Push a new assistant prompt asking for metrics
                need_num = ("I still need at least one number to show scale "
                            "or impact (team size, %, $, time). "
                            "Can you estimate any of those?")
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
