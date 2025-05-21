
# 🧑‍⚖️ Pakistan Law Adviser

A simple, intelligent chatbot built with Flask that answers questions related to Pakistani law in easy-to-understand English. This chatbot uses Retrieval-Augmented Generation (RAG) with a local LLaMA model and FAISS vector store for efficient legal question answering.

## 🔍 Features

- ✅ Easy-to-use chat interface with smooth animations
- ✅ Summarized, beginner-friendly legal answers in English
- ✅ Retrieval of relevant legal data using FAISS
- ✅ Powered by locally hosted LLaMA 3.2 model
- ✅ Stateless, browser-memory-based chat history
- ✅ Auto-scroll and smooth transition effects
- ✅ Displays answers from bottom to top like modern chat apps

## 🧰 Technologies Used

- **Flask** – Python web framework
- **FAISS** – Vector similarity search
- **SentenceTransformers** – For embedding queries
- **Ollama / LLaMA 3.2** – Language model for generating responses
- **HTML/CSS + Bootstrap** – Frontend styling
- **Jinja2** – Templating engine
- **Python Pickle** – Metadata management

## 🖼️ UI Preview

![ss](https://github.com/user-attachments/assets/9029e2b8-d689-4dec-a8e5-3157f0ee4ea0)


## 📁 Project Structure

```bash
.
├── app.py                   # Main Flask app
├── rag_helper.py           # FAISS & embedding logic
├── templates/
│   └── index.html          # Chat interface
├── static/
│   └── style.css           # Custom styling
├── model/
│   ├── faiss_index.index   # FAISS vector index
│   └── metadata.pkl        # Corresponding metadata chunks
````

## 🚀 How to Run

1. **Install Dependencies**

```bash
pip install requriment.txt
```

2. **Go to groq website and get API key (it`s free)**

Make sure to check which model you are using 

```bash
https://console.groq.com/settings/billing/plans
```
3. **Download model from Google Drive**

```bash
https://drive.google.com/drive/folders/1bbHCXDFlgJydrqXsQ2tdNuDnMvx9T3Lf?usp=sharing
```

4. **Run Flask App**

```bash
python app.py
```

5. **Access App**

Visit: `http://localhost:5000` in your browser.

---

## 📝 Notes

* All answers are **simplified** for common users. Not intended for professional legal use.
* Chat history is temporarily stored and **cleared on page reload**.
* Backend runs inference locally using the LLaMA model hosted with [Ollama](https://ollama.com).

## 👨‍💻 Author

**Talha Iqbal**
[GitHub](https://github.com/talha828)

---

## 🛡️ Disclaimer

This chatbot is for **informational purposes only**. Always consult a professional for real legal advice.
