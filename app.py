import os
from flask import Flask, jsonify, request, render_template, session
import requests
from rag_helper import embed_query, load_faiss_index, search_index
import time
import secrets
from dotenv import load_dotenv
from flask import Flask, send_from_directory


load_dotenv()  # Load environment variables from .env

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)  # Needed for session

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

@app.route('/')
def home():
    chat_history = session.get('chat_history', [])
    return render_template("index.html", chat_history=chat_history)


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='assets/favicon.icon')

@app.route('/test_chat', methods=['POST'])
def test_chat():
    user_message = request.form['message']

    chat_history = session.get('chat_history', [])
    chat_history.append({'sender': 'user', 'text': user_message})

    time.sleep(2)

    bot_response = f"Simulated answer for: {user_message}"
    chat_history.append({'sender': 'bot', 'text': bot_response})
    
    session['chat_history'] = chat_history
    return render_template("index.html", chat_history=chat_history)

@app.route('/chat', methods=['POST'])
def chat():
    query = request.form['message']
    chat_history = session.get('chat_history', [])
    chat_history.append({'sender': 'user', 'text': query})

    index, chunks = load_faiss_index()
    embedding = embed_query(query)
    relevant_chunks = search_index(index, embedding, chunks)
    context = "\n".join(relevant_chunks)

    prompt = f"""You are a friendly legal expert in Pakistani law. Use the context below to answer the question and make sure your answer is as simple as possible.
- Use simple and easy English, no legal jargon.
- Summarize the answer in bullet points.
- Always use latest law and rules.
- Mention any legal sections or articles if applicable.

Context:
{context}

Question:
{query}
"""

    try:
        response = requests.post(
            GROQ_API_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {GROQ_API_KEY}"
            },
            json={
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }
        )

        data = response.json()
        answer = data['choices'][0]['message']['content']

        chat_history.append({'sender': 'bot', 'text': answer})
        session['chat_history'] = chat_history

        return render_template("index.html", chat_history=chat_history)

    except Exception as e:
        return jsonify({"response": f"⚠️ Error: {str(e)}"})


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
