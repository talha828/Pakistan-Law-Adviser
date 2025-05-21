from datetime import datetime
import os
import json
import time
import secrets
import requests
import gdown
from flask import Flask, jsonify, request, render_template, session, send_from_directory
from flask_session import Session
from dotenv import load_dotenv
from rag_helper import embed_query, load_faiss_index, search_index
from flask import send_file


# ========== Load Environment Variables ==========
load_dotenv()

# ========== Flask Config ==========
app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = './flask_sessions'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = False  # True in HTTPS
Session(app)

# ========== Download Model Files ==========
@app.route('/download-json')
def download_json():
    return send_file('/root/flask-Application/chat_history.json', as_attachment=True)

# ========== API Config ==========
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

# ========== Chat Log ==========
CHAT_LOG_FILE = "chat_history.json"

def load_chat_log():
    if os.path.exists(CHAT_LOG_FILE):
        with open(CHAT_LOG_FILE, "r") as file:
            return json.load(file)
    return []

def log_chat_message(role, content):
    history = load_chat_log()
    history.append({
        "timestamp": datetime.now().isoformat(),
        "role": role,
        "content": content
    })
    with open(CHAT_LOG_FILE, "w") as file:
        json.dump(history, file, indent=4)

# ========== Routes ==========
@app.route('/')
def home():
    if 'chat_history' not in session:
        session['chat_history'] = []
    return render_template("index.html", chat_history=session['chat_history'])

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='assets/favicon.icon')

@app.route('/test_chat', methods=['POST'])
def test_chat():
    user_message = request.form['message']
    if 'chat_history' not in session:
        session['chat_history'] = []

    session['chat_history'].append({'sender': 'user', 'text': user_message})
    log_chat_message('user', user_message)

    time.sleep(2)
    bot_response = f"Simulated answer for: {user_message}"
    session['chat_history'].append({'sender': 'bot', 'text': bot_response})
    log_chat_message('bot', bot_response)

    return render_template("index.html", chat_history=session['chat_history'])

@app.route('/chat', methods=['POST'])
def chat():
    query = request.form['message']

    if 'chat_history' not in session:
        session['chat_history'] = []

    session['chat_history'].append({'sender': 'user', 'text': query})
    log_chat_message('user', query)

    # Step 1: Clean or improve the user's question
    improve_prompt = f"""
    You are a smart assistant that improves unclear or messy questions.
    Convert the following question into a better, clearer, and more specific legal question related to Pakistani law:

    "{query}"

    Make sure the improved version is very clear, properly structured, and contextually correct.
    """
    
    try:
        improve_response = requests.post(
            GROQ_API_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {GROQ_API_KEY}"
            },
            json={
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": improve_prompt}]
            }
        )

        improved_question = improve_response.json()['choices'][0]['message']['content'].strip()
        log_chat_message('user', improve_prompt)
        # Step 2: Use improved question to search
        index, chunks = load_faiss_index()
        embedding = embed_query(improved_question)
        relevant_chunks = search_index(index, embedding, chunks)
        context = "\n".join(relevant_chunks)

        # Step 3: Build final response prompt
        final_prompt = f"""You are a friendly legal expert in Pakistani law. Use the context below to answer the question and make sure your answer is as simple as possible.
- Use simple and easy English, no legal jargon.
- Detail the answer in bullet points with clear explanation of laws and sections.
- Always use the latest law if present and rules.
- Mention any legal sections or articles if applicable.

Context:
{context}

Question:
{improved_question}
"""

        # Step 4: Get final answer
        response = requests.post(
            GROQ_API_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {GROQ_API_KEY}"
            },
            json={
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": final_prompt}]
            }
        )

        data = response.json()
        answer = data['choices'][0]['message']['content']

        session['chat_history'].append({'sender': 'bot', 'text': answer})
        log_chat_message('bot', answer)

        return render_template("index.html", chat_history=session['chat_history'])

    except Exception as e:
        error_msg = f"⚠️ Error: {str(e)}"
        session['chat_history'].append({'sender': 'bot', 'text': error_msg})
        log_chat_message('bot', error_msg)
        return jsonify({"response": error_msg})


# ========== Server Run ==========
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
