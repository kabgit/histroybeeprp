import streamlit as st
import openai
import wikipedia
import json
import os
from datetime import datetime
import re

# === Custom Style to Expand App Width ===
st.markdown("""
    <style>
        html, body, [data-testid="stAppViewContainer"] > .main {
            max-width: 100vw;
            padding: 0 2rem;
        }

        [data-testid="stHorizontalBlock"] {
            gap: 2rem;
        }

        [data-testid="column"] {
            min-width: 0;
        }

        .block-container {
            padding-top: 1rem;
            padding-bottom: 1rem;
            padding-left: 2rem;
            padding-right: 2rem;
        }
    </style>
""", unsafe_allow_html=True)




# === OpenAI Setup ===
client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])  # <-- PUT YOUR API KEY HERE

# === Constants ===
PROGRESS_FILE = "user_progress.json"
LINKS_FILE = "links.txt"

# === Load Wikipedia Links ===
@st.cache_data
def load_links(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return [line.strip() for line in file if line.strip()]

# === Save/Load Progress ===
def save_progress():
    data = {
        "current_article_index": st.session_state.current_article_index,
        "scores_per_article": st.session_state.scores_per_article
    }
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(data, f)

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r') as f:
            data = json.load(f)
            st.session_state.current_article_index = data.get("current_article_index", 0)
            st.session_state.scores_per_article = data.get("scores_per_article", {})

# === Session State Initialization ===
if 'links' not in st.session_state:
    st.session_state.links = load_links(LINKS_FILE)
if 'current_article_index' not in st.session_state:
    st.session_state.current_article_index = 0
if 'summary_text' not in st.session_state:
    st.session_state.summary_text = ""
if 'current_title' not in st.session_state:
    st.session_state.current_title = ""
if 'quiz' not in st.session_state:
    st.session_state.quiz = []
if 'quiz_started' not in st.session_state:
    st.session_state.quiz_started = False
if 'current_question' not in st.session_state:
    st.session_state.current_question = 0
if 'score' not in st.session_state:
    st.session_state.score = 0
if 'show_feedback' not in st.session_state:
    st.session_state.show_feedback = False
if 'selected_option' not in st.session_state:
    st.session_state.selected_option = None
if 'scores_per_article' not in st.session_state:
    st.session_state.scores_per_article = {}
if 'progress_loaded' not in st.session_state:
    load_progress()
    st.session_state.progress_loaded = True


# === Load Current Wikipedia Article Summary ===
def load_current_article():
    try:
        link = st.session_state.links[st.session_state.current_article_index]
        title = link.split("/wiki/")[-1]
        page = wikipedia.page(title=title, auto_suggest=False)
        st.session_state.current_title = page.title
        return page.summary
    except Exception as e:
        return f"Error loading article: {e}"

if not st.session_state.summary_text:
    st.session_state.summary_text = load_current_article()

# === Page Layout ===
left_col, center_col, right_col = st.columns([2, 4, 1])

# === Left Column: Article List ===
with left_col:
    st.markdown("""
        <style>
        .left-panel-scroll {
            max-height: 80vh;
            overflow-y: auto;
            padding-top: 1rem;
            padding-right: 0.5rem;
        }
        </style>
        <div class="left-panel-scroll">
    """, unsafe_allow_html=True)

    st.subheader("📜 Select Article")

    article_titles = [link.split("/wiki/")[-1].replace("_", " ") for link in st.session_state.links]
    current_index = st.session_state.current_article_index

    selected_title = st.selectbox("Choose an article:", article_titles, index=current_index)

    # Update the article if selection has changed
    if article_titles.index(selected_title) != current_index:
        st.session_state.current_article_index = article_titles.index(selected_title)
        st.session_state.summary_text = load_current_article()
        st.session_state.quiz = []
        st.session_state.quiz_started = False
        st.session_state.current_question = 0
        st.session_state.score = 0
        st.session_state.show_feedback = False
        st.session_state.selected_option = None
        st.rerun()



# === Center Column: Summary, Quiz, Navigation ===
with center_col:
    st.title("📚 History Bee Prep")
    total_articles = len(st.session_state.links)
    st.header(f"Article {st.session_state.current_article_index + 1}: {st.session_state.current_title}")
    st.markdown(
        f"""
        <div style='max-height: 400px; overflow-y: auto;
                    padding: 15px; background-color: #e9ecef;
                    border: 1px solid #ccc; border-radius: 8px;
                    font-size: 16px; line-height: 1.6;
                    color: #333;'>
            {st.session_state.summary_text.replace('\n', '<br>')}
        </div>
        """,
        unsafe_allow_html=True
    )


    if st.button("Generate Quiz 🛠️") and not st.session_state.quiz:
        with st.spinner("Generating quiz..."):
            prompt = f"""
            Create a 5-question multiple-choice quiz from this Wikipedia summary:

            {st.session_state.summary_text}

            Each question should have 4 options. Mark the correct answer clearly.

            Format like this:
            Question: ...
            A) ...
            B) ...
            C) ...
            D) ...
            Answer: (Letter)
            """

            response = client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5
            )

            raw_quiz = response.choices[0].message.content
            questions = []
            blocks = raw_quiz.strip().split("Question:")
            for block in blocks[1:]:
                lines = block.strip().splitlines()
                q_text = lines[0].strip()
                options = [line[2:].strip() for line in lines[1:5]]
                match = re.search(r"Answer:\s*\(?([A-D])\)?", lines[5], re.IGNORECASE)
                if match:
                    correct_letter = match.group(1).upper()
                    correct_index = ord(correct_letter) - ord('A')
                    correct_answer = options[correct_index]
                else:
                    raise ValueError(f"Could not extract answer from line: {lines[5]}")

                questions.append({
                    "question": q_text,
                    "options": options,
                    "answer": correct_answer
                })

            st.session_state.quiz = questions
            st.session_state.quiz_started = True
            st.success("✅ Quiz ready!")

    if st.session_state.quiz_started and st.session_state.quiz:
        current = st.session_state.quiz[st.session_state.current_question]
        st.subheader(f"Question {st.session_state.current_question + 1}")
        st.write(current["question"])

        selected = st.radio(
            "Choose your answer:",
            current["options"],
            index=None,
            key=f"q{st.session_state.current_article_index}_{st.session_state.current_question}"
        )

        if st.button("Submit Answer"):
            if selected:
                st.session_state.selected_option = selected
                st.session_state.show_feedback = True
                if selected == current["answer"]:
                    st.success("✅ Correct!")
                    st.session_state.score += 1
                else:
                    st.error(f"❌ Incorrect! Correct answer: {current['answer']}")

        if st.session_state.show_feedback and st.session_state.selected_option:
            if st.button("Next Question ➡️"):
                if st.session_state.current_question < len(st.session_state.quiz) - 1:
                    st.session_state.current_question += 1
                    st.session_state.show_feedback = False
                    st.session_state.selected_option = None
                    st.rerun()
                else:
                    percent = (st.session_state.score / len(st.session_state.quiz)) * 100
                    article_index = st.session_state.current_article_index
                    timestamp = datetime.now().isoformat()
                    st.session_state.scores_per_article[str(article_index)] = {
                        "score": percent,
                        "timestamp": timestamp
                    }
                    save_progress()
                    st.success(f"🎉 Quiz done! Score: {percent:.1f}%")
                    st.balloons()
                    st.session_state.quiz = []
                    st.session_state.quiz_started = False
                    st.session_state.current_question = 0
                    st.session_state.score = 0
                    st.session_state.selected_option = None
                    st.session_state.show_feedback = False
                    st.rerun()

    if st.button("⬅️ Previous Article"):
        if st.session_state.current_article_index > 0:
            st.session_state.current_article_index -= 1
            st.session_state.summary_text = load_current_article()
            st.session_state.quiz = []
            st.session_state.quiz_started = False
            st.session_state.current_question = 0
            st.session_state.score = 0
            st.session_state.show_feedback = False
            st.session_state.selected_option = None
            st.rerun()

    if st.button("➡️ Next Article"):
        if st.session_state.current_article_index < total_articles - 1:
            st.session_state.current_article_index += 1
            st.session_state.summary_text = load_current_article()
            st.session_state.quiz = []
            st.session_state.quiz_started = False
            st.session_state.current_question = 0
            st.session_state.score = 0
            st.session_state.show_feedback = False
            st.session_state.selected_option = None
            st.rerun()

# === Right Column: Progress & History ===
with right_col:
    st.header("Progress")
    progress = (st.session_state.current_article_index + 1) / len(st.session_state.links)
    st.progress(progress)

    if st.button("🔄 Reset History"):
        if os.path.exists(PROGRESS_FILE):
            os.remove(PROGRESS_FILE)
        st.session_state.scores_per_article = {}
        st.session_state.current_article_index = 0
        st.session_state.summary_text = load_current_article()
        st.rerun()

    for idx, entry in st.session_state.scores_per_article.items():
        link = st.session_state.links[int(idx)]
        title = link.split("/wiki/")[-1].replace("_", " ")
        score = entry["score"]
        ts = entry["timestamp"]
        html_link = f'<a href="{link}" target="_blank"><b>{title}</b></a>: {score:.1f}%<br><small>🕓 {ts.split("T")[0]} {ts.split("T")[1][:5]}</small>'
        st.markdown(html_link, unsafe_allow_html=True)
