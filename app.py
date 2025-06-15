# app.py

# ==================== Imports ====================
# Standard Library Imports
import os
import json
import time
import secrets
from datetime import datetime, timedelta # Import timedelta for date calculations
from functools import wraps # Used for decorators
import uuid # Imported for dummy user creation in db_init
import openai
# Third-Party Imports
import requests
from flask import (
    Flask, flash, jsonify, request, render_template,
    session, send_file, send_from_directory, redirect, url_for
)
from flask_session import Session
from dotenv import load_dotenv

# Local Application Imports
from auth import auth_bp
from models import db, User
from openai import OpenAIError

from chat_used import (
    PAID_TIER_CHAT_ALLOWANCE, is_chat_limit_reached,
    increment_chat_count, check_and_update_user_status,
    FREE_TIER_CHAT_LIMIT, mark_user_as_paid
)

# Optional: RAG Helper Imports (uncomment if you have these files)
try:
    from rag_helper import embed_query, load_faiss_index, search_index
except ImportError:
    print("Warning: 'rag_helper' module not found. RAG functionality will use dummy context.")
    embed_query = None
    load_faiss_index = None
    search_index = None


# ==================== Load Environment Variables ====================
load_dotenv()


# ==================== Flask App Setup ====================
app = Flask(__name__)
app.secret_key = secrets.token_hex(16) # For signing session cookies

# Session Configuration
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = './flask_sessions' # Directory to store session files
app.config['SESSION_COOKIE_HTTPONLY'] = True # Prevent client-side JS access to cookie
app.config['TEMPLATES_AUTO_RELOAD'] = True # Reload templates automatically during development
app.config['SESSION_COOKIE_SECURE'] = False # Set to True in production with HTTPS!
Session(app)

# Register Blueprints
app.register_blueprint(auth_bp)


# ==================== Database Setup ====================
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db' # SQLite database file
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # Disable Flask-SQLAlchemy event system for performance
db.init_app(app)

# Database Initialization (Create tables and add dummy user if needed)
with app.app_context():
    db.create_all() # Create database tables based on models
    # Optional: Add a dummy user for testing if the DB is empty
    if User.query.count() == 0:
        print("Adding a dummy user for testing...")
        dummy_user = User(
            id=str(uuid.uuid4()), # Generate a unique ID for the dummy user
            email="testuser@example.com",
            name="Test User",
            profile_pic="https://placehold.co/100x100/000000/FFFFFF?text=TU"
        )
        db.session.add(dummy_user)
        db.session.commit()
        print(f"Dummy user '{dummy_user.email}' created.")


# ==================== Constants ====================
CHAT_LOG_FILE = "chat_history.json"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

# Admin Credentials (FOR DEMONSTRATION ONLY - USE ENV VARS IN PROD)
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "adminpass") # CHANGE THIS IN PRODUCTION!


# ==================== Helper Functions ====================
def load_chat_log():
    """Loads chat history from a JSON file."""
    if os.path.exists(CHAT_LOG_FILE):
        with open(CHAT_LOG_FILE, "r") as file:
            try:
                return json.load(file)
            except json.JSONDecodeError:
                # Handle empty or malformed JSON file gracefully
                return []
    return []

# MODIFIED: Now accepts user_id to log per-user messages
def log_chat_message(user_id, role, content):
    """Logs a chat message to the chat history JSON file, including user_id."""
    history = load_chat_log()
    history.append({
        "timestamp": datetime.now().isoformat(),
        "user_id": user_id, # Store user_id for filtering
        "role": role,
        "content": content
    })
    with open(CHAT_LOG_FILE, "w") as file:
        json.dump(history, file, indent=4)


# ==================== Decorators ====================
def admin_required(f):
    """
    Decorator to restrict access to admin routes.
    Checks if 'admin_logged_in' is True in the session.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Debug prints for admin access (can be removed in production)
        print(f"\n--- Admin Required Check for {request.path} ---")
        print(f"Session 'admin_logged_in': {session.get('admin_logged_in')}")
        if not session.get('admin_logged_in'):
            print("Redirecting to admin_login: User not logged in as admin")
            flash('Please log in as an administrator to access this page.', 'danger')
            return redirect(url_for('admin_login'))
        print("Access granted: User logged in as admin")
        return f(*args, **kwargs)
    return decorated_function


# ==================== Routes ====================

## --- Core User Application Routes ---
@app.route('/')
def home():
    """Handles the home route, redirects to chatscreen if logged in."""
    if 'chat_history' not in session:
        session['chat_history'] = []
    if 'user_id' in session:
        return redirect(url_for("chatscreen"))
    return render_template("login.html") # Your initial login/landing page

@app.route("/chatscreen")
def chatscreen():
    """
    Renders the chat screen for logged-in users.
    Updates user status and passes chat allowance info to the template.
    """
    if 'user_id' not in session:
        return redirect(url_for('home')) # Redirect to home/login if not logged in

    user = User.query.get(session['user_id'])
    if not user:
        # Handle case where user_id in session doesn't match a user in DB
        session.clear()
        flash('User not found. Please log in again.', 'danger')
        return redirect(url_for('home'))

    # Crucial: Always update user's subscription status before displaying info
    check_and_update_user_status(user)
    db.session.refresh(user) # Refresh user object to get latest data after commit

    # Ensure chat history is initialized in session for rendering
    if 'chat_history' not in session:
        session['chat_history'] = []

    return render_template(
        "index.html",
        chat_history=session['chat_history'],
        chats_used=user.chats_used,
        paid=user.paid,
        user_name=user.name,
        user_pic=user.profile_pic,
        remaining_chats=user.get_remaining_chats(), # Pass remaining chats
        total_chats_allowed=user.total_chats_allowed, # Pass total allowed
        is_active_subscription=user.has_active_subscription() # Pass active subscription status
    )

@app.route('/logout')
def logout():
    """Clears the user session and redirects to the login page."""
    session.pop('user_id', None) # Only pop user_id, keep admin_logged_in if it exists
    # Or session.clear() if you want to clear everything for the user
    flash('Logged out successfully.', 'info')
    return redirect(url_for('home')) # Redirect to the home/login page


## --- Chat API Routes ---
@app.route('/test_chat', methods=['POST'])
def test_chat():
    """Simulates a chat interaction without hitting external APIs."""
    user_id = session.get('user_id') # Get user_id for logging
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    user_message = request.form['message']
    if 'chat_history' not in session:
        session['chat_history'] = []

    session['chat_history'].append({'sender': 'user', 'text': user_message})
    log_chat_message(user_id, 'user', user_message) # Pass user_id

    # Simulated response
    time.sleep(1) # Shorter sleep for faster testing
    bot_response = f"Simulated answer for: {user_message}"
    session['chat_history'].append({'sender': 'bot', 'text': bot_response})
    log_chat_message(user_id, 'bot', bot_response) # Pass user_id

    # Re-render the chatscreen with updated chat history and user info
    user = User.query.get(user_id) # Use .get() for safety
    if not user:
        return jsonify({"error": "User session expired or invalid."}), 401 # Handle missing user

    check_and_update_user_status(user)
    db.session.refresh(user)
    return render_template(
        "index.html",
        chat_history=session['chat_history'],
        chats_used=user.chats_used,
        paid=user.paid,
        user_name=user.name,
        user_pic=user.profile_pic,
        remaining_chats=user.get_remaining_chats(),
        total_chats_allowed=user.total_chats_allowed,
        is_active_subscription=user.has_active_subscription()
    )
import openai

# Set your OpenAI API Key
openai.api_key = os.getenv("OPENAI_API_KEY")

@app.route('/chat', methods=['POST'])
def chat():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    user = User.query.get(user_id)
    if not user:
        session.clear()
        return jsonify({"error": "User not found. Please log in again."}), 404

    check_and_update_user_status(user)
    db.session.refresh(user)

    if is_chat_limit_reached(user):
        if user.has_active_subscription():
            return jsonify({
                "error": f"You have used all your {user.total_chats_allowed} chats for this month. Your subscription is active until {user.paid_until.strftime('%Y-%m-%d')}."
            }), 402
        else:
            return jsonify({
                "error": f"You have reached your free chat limit of {FREE_TIER_CHAT_LIMIT} chats. Please complete payment to unlock {PAID_TIER_CHAT_ALLOWANCE} more chats for 1 month!"
            }), 402

    increment_chat_count(user)
    db.session.refresh(user)

    query = request.form['message']
    if 'chat_history' not in session:
        session['chat_history'] = []

    session['chat_history'].append({'sender': 'user', 'text': query})
    log_chat_message(user_id, 'user', query)

    try:
        # Step 1: Improve the user question using ChatGPT
        improve_prompt = f"""
        You are a helpful and intelligent assistant that takes unclear, messy, or informal questions and rewrites them into clear, specific, and well-structured legal questions related to Pakistani law.

        Your task:
        - Rewrite the following user question in better English.
        - Make it more precise, legally relevant, and easy to understand.
        - If the question is written in Roman Urdu or Urdu, translate it into proper English first.
        - At the end, clearly mention whether the **final answer should be returned in Roman Urdu** — only if the original question was in Roman Urdu or Urdu.

        ---

        📝 Original Question:
        "{query}"

        🎯 Return only the improved legal question, followed by a note like:
        "🗣️ Answer should be in Urdu." or "🗣️ Answer should be in Roman Urdu." if applicable.
        """

        improve_response = openai.chat.completions.create(
            model="gpt-4.1-nano",
            messages=[{"role": "user", "content": improve_prompt}]
        )
        improved_question = improve_response.choices[0].message.content.strip()
        log_chat_message(user_id, 'user', improved_question)

        # Step 2: Get context from FAISS
        context = "No specific legal context available. Please consult a qualified legal professional for advice on Pakistani law."
        if embed_query and load_faiss_index and search_index:
            try:
                index, chunks = load_faiss_index()
                embedding = embed_query(improved_question)
                relevant_chunks = search_index(index, embedding, chunks)
                context = "\n".join(relevant_chunks)
            except Exception as rag_err:
                print(f"Error in RAG process: {rag_err}. Using dummy context.")
        else:
            print("Warning: RAG helper functions not available. Using dummy context.")

        # Step 3: Final prompt with context
        final_prompt = f"""
        You're a smart, trusted legal expert who knows Pakistani law inside and out. People come to you — lawyers, students, and everyday citizens — because your answers are clear, honest, and easy to understand.

        🧠 Here's how you should think when answering:

        - ✅ **Be Accurate:** Stick to the law. Be precise and current.
        - 🗣️ **Be Clear:** Talk like you're explaining it to a friend. Avoid complex terms unless you explain them briefly.
        - 🤝 **Be Ethical:** Never suggest illegal shortcuts. Focus on lawful, fair solutions.
        - ❤️ **Be Human:** Imagine you're talking to someone worried or confused. Be calm, respectful, and kind — not robotic.

        🎯 Adjust your tone depending on who's asking:
        - For **everyday people**: Be friendly and explain things simply.
        - For **students**: Be like a helpful teacher — clear, encouraging, and educational.
        - For **lawyers or researchers**: Go deeper. If useful, cite law sections, cases, or legal principles.

        📝 How to answer:
        - 👋 Start with something human — recognize the concern or show you're listening.
        - 🔍 Break the legal idea down in simple steps or short points.
        - ⚖️ Mention relevant laws (like PPC, Family Law, PECA) only when helpful — don’t overdo it.
        - ✅ Give practical next steps the user can take.
        - 🧭 If needed, explain *why* the law exists — give social or ethical background.
        - 📞 Always encourage users to talk to a lawyer for personal or complicated cases.

        Use only the context and question below when writing your reply.

        ---

        📚 **Context**:
        {context}

        ❓ **Question**:
        {improved_question}
        """


        # Step 4: Final answer using ChatGPT
        response = openai.chat.completions.create(
            model="gpt-4.1-nano",
            messages=[{"role": "user", "content": final_prompt}]
        )
        answer = response.choices[0].message.content
        session['chat_history'].append({'sender': 'bot', 'text': answer})
        log_chat_message(user_id, 'bot', answer)

        user = User.query.get(session.get("user_id"))
        check_and_update_user_status(user)
        db.session.refresh(user)

        return render_template(
            "index.html",
            chat_history=session['chat_history'],
            chats_used=user.chats_used,
            paid=user.paid,
            user_name=user.name,
            user_pic=user.profile_pic,
            remaining_chats=user.get_remaining_chats(),
            total_chats_allowed=user.total_chats_allowed,
            is_active_subscription=user.has_active_subscription()
        )

    except OpenAIError as req_err:
        error_msg = f"⚠️ API Error: Could not connect to ChatGPT. Details: {str(req_err)}"
        print(error_msg)
        session['chat_history'].append({'sender': 'bot', 'text': error_msg})
        log_chat_message(user_id, 'bot', error_msg)
        return jsonify({"response": error_msg}), 500



## --- Admin Panel Routes ---
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    """Handles administrator login."""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            flash('Logged in as administrator!', 'success')
            return redirect(url_for('admin_panel'))
        else:
            flash('Invalid administrator credentials.', 'danger')
    return render_template('admin_login.html') # You'll need to create this template

@app.route('/admin_logout')
@admin_required # It's good practice to protect the logout route too, though less critical
def admin_logout():
    """Handles administrator logout."""
    session.pop('admin_logged_in', None) # Removes 'admin_logged_in' from session
    flash('Logged out as administrator.', 'info')
    return redirect(url_for('admin_login')) # Redirect back to the login page

@app.route('/admin_panel')
@admin_required # Apply the decorator to protect this route
def admin_panel():
    """Renders the admin panel HTML page, only accessible to logged-in admins."""
    return render_template('admin_panel.html')


## --- Admin API Endpoints (Protected by @admin_required) ---
@app.route('/api/list_all_users', methods=['GET']) # NEW ENDPOINT
@admin_required
def list_all_users():
    """
    API endpoint to list all registered users.
    Returns a list of user dictionaries.
    """
    users = User.query.all()
    user_list = []
    for user in users:
        # Ensure status is up-to-date before sending to admin panel
        check_and_update_user_status(user)
        db.session.refresh(user) # Refresh to get latest DB state after status update
        user_list.append({
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "chats_used": user.chats_used,
            "total_chats_allowed": user.total_chats_allowed,
            "paid": user.paid,
            "paid_until": user.paid_until.isoformat() if user.paid_until else None,
            "has_active_subscription": user.has_active_subscription(),
            "remaining_chats": user.get_remaining_chats()
        })
    return jsonify(user_list), 200

@app.route('/api/get_user_chat_history', methods=['GET']) # NEW ENDPOINT
@admin_required
def get_user_chat_history():
    """
    API endpoint to retrieve chat history for a specific user.
    Filters chat_history.json by user_id.
    """
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"error": "User ID parameter is required"}), 400

    all_chat_history = load_chat_log()
    user_chat_history = [
        msg for msg in all_chat_history if msg.get('user_id') == user_id
    ]
    return jsonify(user_chat_history), 200


@app.route('/api/delete_user', methods=['POST']) # NEW ENDPOINT
@admin_required
def delete_user():
    """
    API endpoint to delete a user from the database and their chat history.
    Expects JSON payload with 'user_id'.
    """
    data = request.get_json()
    user_id = data.get('user_id')

    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    user_to_delete = User.query.get(user_id)
    if not user_to_delete:
        return jsonify({"error": "User not found"}), 404

    try:
        # 1. Delete user from database
        db.session.delete(user_to_delete)
        db.session.commit()

        # 2. Delete user's chat history from chat_history.json
        all_chat_history = load_chat_log()
        updated_chat_history = [
            msg for msg in all_chat_history if msg.get('user_id') != user_id
        ]
        with open(CHAT_LOG_FILE, "w") as file:
            json.dump(updated_chat_history, file, indent=4)

        return jsonify({"message": f"User {user_id} and their chat history deleted successfully."}), 200
    except Exception as e:
        db.session.rollback() # Rollback in case of error
        return jsonify({"error": f"Failed to delete user: {str(e)}"}), 500


@app.route('/api/search_user', methods=['GET'])
@admin_required
def search_user():
    """
    API endpoint to search for a user by email.
    Returns user details including chat usage and payment status.
    """
    email = request.args.get('email')
    if not email:
        return jsonify({"error": "Email parameter is required"}), 400

    user = User.query.filter_by(email=email).first()
    if user:
        return jsonify({
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "chats_used": user.chats_used,
            "total_chats_allowed": user.total_chats_allowed,
            "paid": user.paid,
            "paid_until": user.paid_until.isoformat() if user.paid_until else None,
            "has_active_subscription": user.has_active_subscription(),
            "remaining_chats": user.get_remaining_chats()
        }), 200
    else:
        return jsonify({"error": "User not found"}), 404

@app.route('/api/mark_user_paid', methods=['POST'])
@admin_required
def api_mark_user_paid():
    """
    API endpoint to mark a user as paid and assign a specific chat count.
    Expects JSON payload with 'email' and 'total_chats_allowed'.
    """
    data = request.get_json()
    email = data.get('email')
    total_chats_allowed = data.get('total_chats_allowed', PAID_TIER_CHAT_ALLOWANCE)

    try:
        total_chats_allowed = int(total_chats_allowed)
        if total_chats_allowed <= 0:
            raise ValueError("Chat allowance must be a positive integer.")
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid 'total_chats_allowed' provided. Must be a positive integer."}), 400

    if not email:
        return jsonify({"error": "Email is required"}), 400

    user = User.query.filter_by(email=email).first()
    if user:
        mark_user_as_paid(user, total_chats_allowed=total_chats_allowed)
        return jsonify({
            "message": f"User {email} marked as paid.",
            "paid_until": user.paid_until.isoformat(),
            "total_chats_allowed": user.total_chats_allowed
        }), 200
    else:
        return jsonify({"error": "User not found"}), 404

@app.route('/api/mark_user_unpaid', methods=['POST'])
@admin_required
def api_mark_user_unpaid():
    """
    API endpoint to mark a user as unpaid.
    Resets their paid status, paid_until, chats_used, and total_chats_allowed to free tier.
    Expects JSON payload with 'email'.
    """
    data = request.get_json()
    email = data.get('email')

    if not email:
        return jsonify({"error": "Email is required"}), 400

    user = User.query.filter_by(email=email).first()
    if user:
        user.paid = False
        user.paid_until = None
        user.chats_used = 0 # Reset chats for the new free period
        user.last_reset = datetime.utcnow() # Reset the last_reset timestamp
        user.total_chats_allowed = FREE_TIER_CHAT_LIMIT # Revert to free tier limit
        db.session.commit()
        return jsonify({
            "message": f"User {email} marked as unpaid. Chats reset to {user.chats_used}, allowance set to {user.total_chats_allowed}.",
            "paid": user.paid,
            "paid_until": user.paid_until,
            "chats_used": user.chats_used,
            "total_chats_allowed": user.total_chats_allowed
        }), 200
    else:
        return jsonify({"error": "User not found"}), 404


## --- Utility Routes ---
@app.route('/favicon.ico')
def favicon():
    """Serves the favicon."""
    return send_from_directory(
        os.path.join(app.root_path, 'static'),
        'favicon.ico',
        mimetype='image/vnd.microsoft.icon'
    )

@app.route('/download-json')
def download_json():
    """Allows downloading of the chat history log file."""
    # Ensure the path is secure and correct for your environment
    return send_file(CHAT_LOG_FILE, as_attachment=True)

# Example Route for User Interaction (to demonstrate chat limit logic, not a core UI route)
@app.route('/simulate_chat_use', methods=['POST'])
def simulate_chat_use():
    """
    Simulates a user sending a chat message to increment their count.
    This is typically for testing chat limit logic, not a user-facing route.
    """
    user_id = request.json.get('user_id')
    user = User.query.get(user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    check_and_update_user_status(user) # Ensure status is up-to-date

    if is_chat_limit_reached(user):
        return jsonify({
            "message": "Chat limit reached!",
            "remaining_chats": user.get_remaining_chats(),
            "is_paid": user.has_active_subscription()
        }), 403
    else:
        increment_chat_count(user)
        return jsonify({
            "message": "Chat used!",
            "chats_used": user.chats_used,
            "remaining_chats": user.get_remaining_chats(),
            "is_paid": user.has_active_subscription()
        }), 200


# ==================== Run App ====================
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    # debug=True automatically enables auto-reloader and debugger
    app.run(host='0.0.0.0', port=port, debug=True)

