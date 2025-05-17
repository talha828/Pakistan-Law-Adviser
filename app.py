from flask import Flask, jsonify, request, render_template, session
import requests
from rag_helper import embed_query, load_faiss_index, search_index
import time

app = Flask(__name__)
app.secret_key = 'my_temp_secret_123'  # Needed for session

@app.route('/')
def home():
    chat_history = session.get('chat_history', [])
    return render_template("index.html", chat_history=chat_history)

@app.route('/test_chat', methods=['POST'])
def test_chat():
    user_message = request.form['message']

    # Get or create chat history
    chat_history = session.get('chat_history', [])

    # Add user message
    chat_history.append({'sender': 'user', 'text': user_message})

    # Simulate processing delay
    time.sleep(2)

    # Simulate a bot response
    bot_response = f"Simulated answer for: {user_message}"
    chat_history.append({'sender': 'bot', 'text': bot_response})
    
    # Save back to session
    session['chat_history'] = chat_history

    return render_template("index.html", chat_history=chat_history)

@app.route('/chat', methods=['POST'])
def chat():
    query = request.form['message']
    
        # Get or create chat history
    chat_history = session.get('chat_history', [])

    # Add user message
    chat_history.append({'sender': 'user', 'text': query})
    index, chunks = load_faiss_index()
    embedding = embed_query(query)
    relevant_chunks = search_index(index, embedding, chunks)
    context = "\n".join(relevant_chunks)

    prompt = f"""You are a legal expert in Pakistani law. Use the context below to answer the question and make sure your answer is as simple as possible.
- Use simple and easy English , no legal jargon.
- Summarize the answer in bullet points.
- Mention any legal sections or articles if applicable.

Context:
{context}

Question:
{query}
"""

    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "llama3.2", "prompt": prompt, "stream": False}
        )
        result = response.json()

        chat_history.append({'sender': 'bot', 'text': result['response']})

        # Save back to session
        session['chat_history'] = chat_history
       
        return render_template("index.html", chat_history=chat_history)
    except Exception as e:
        return jsonify({"response": f"⚠️ Error: {str(e)}"})

if __name__ == '__main__':
    app.run(debug=True)
