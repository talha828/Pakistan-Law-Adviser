# chat_used.py
from models import db, User
from datetime import datetime, timedelta

# Centralized constants for chat limits and subscription duration
FREE_TIER_CHAT_LIMIT = 10
PAID_TIER_CHAT_ALLOWANCE = 5000 # Default allowance for paid users
PAID_SUBSCRIPTION_DURATION_DAYS = 30 # Duration of a paid subscription in days

def check_and_update_user_status(user):
    """
    Ensures the user's paid status and chat limits are up-to-date
    based on their paid_until date. This function calls the User model's
    method and commits any changes to the database.
    It should be called at the start of any chat-related operation.
    """
    user.check_and_update_subscription_status()
    db.session.commit() # Commit changes if the user's status was updated

def is_chat_limit_reached(user):
    """
    Checks if the user has reached their current chat limit.
    This function delegates the actual check to the User model's method.
    """
    check_and_update_user_status(user) # Always update status first
    return user.is_chat_limit_reached()

def increment_chat_count(user):
    """
    Increases the chat usage for the current period for the given user.
    It first updates the user's status and then increments the count
    only if the user has not reached their limit.
    Returns True on successful increment, False otherwise.
    """
    check_and_update_user_status(user) # Always update status first

    # Only increment if the user has not yet reached their chat limit
    if not user.is_chat_limit_reached():
        user.chats_used += 1
        db.session.commit()
        print(f"User {user.id} chat count incremented to {user.chats_used}.")
        return True
    else:
        print(f"User {user.id} tried to chat but limit reached. Chat not incremented.")
        return False

def mark_user_as_paid(user, total_chats_allowed=PAID_TIER_CHAT_ALLOWANCE):
    """
    Marks a user as paid, sets their subscription expiry date, and assigns
    a specific number of chat allowances.
    This function should be called after a successful payment confirmation.
    'total_chats_allowed' can be overridden by the caller (e.g., admin UI).
    """
    now = datetime.utcnow()
    user.paid = True
    # Set the expiry date based on the defined duration
    user.paid_until = now + timedelta(days=PAID_SUBSCRIPTION_DURATION_DAYS)
    user.chats_used = 0 # Reset chats used for the new paid period
    user.last_reset = now # Mark the start of their new paid period
    # Assign the specified (or default) number of chats allowed
    user.total_chats_allowed = total_chats_allowed

    db.session.commit()
    print(f"User {user.id} marked as paid. Subscription valid until: {user.paid_until}. Chats allowed: {user.total_chats_allowed}")

