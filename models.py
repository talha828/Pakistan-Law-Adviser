# models.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta

db = SQLAlchemy()

class User(db.Model):
    """
    User model to store user information, chat usage, and payment status.
    """
    id = db.Column(db.String(128), primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    name = db.Column(db.String(150))
    profile_pic = db.Column(db.String(200))
    chats_used = db.Column(db.Integer, default=0)
    last_reset = db.Column(db.DateTime, default=datetime.utcnow) # Tracks when free/paid period started

    # Payment Status Fields
    paid = db.Column(db.Boolean, default=False)
    paid_until = db.Column(db.DateTime, nullable=True) # Date/time when paid subscription expires
    total_chats_allowed = db.Column(db.Integer, default=10) # Chats allowed for current period (free or paid)

    def has_active_subscription(self):
        """
        Checks if the user currently has a valid and active paid subscription.
        A subscription is active if 'paid' is True and 'paid_until' is a future datetime.
        """
        # Ensure paid_until is not None before comparing to avoid errors
        return self.paid and self.paid_until and self.paid_until > datetime.utcnow()

    def get_remaining_chats(self):
        """
        Calculates and returns the number of chats remaining for the user
        based on their current subscription status (paid or free).
        """
        # Define the free tier limit. This should match the constant in chat_used.py
        free_tier_limit = 10
        if self.has_active_subscription():
            # For paid users, remaining chats are based on their total_chats_allowed
            return self.total_chats_allowed - self.chats_used
        else:
            # For free users, remaining chats are based on the free tier limit
            return free_tier_limit - self.chats_used

    def is_chat_limit_reached(self):
        """
        Determines if the user has reached their current chat limit.
        This method first updates the subscription status if it has expired.
        """
        # Always check and update subscription status before evaluating limits
        self.check_and_update_subscription_status()

        if self.has_active_subscription():
            # If paid, check against the total_chats_allowed for the paid tier
            return self.chats_used >= self.total_chats_allowed
        else:
            # If free, check against the free tier limit
            free_tier_limit = 10 # Ensure this matches the constant in chat_used.py
            return self.chats_used >= free_tier_limit

    def check_and_update_subscription_status(self):
        """
        Automatically updates a user's subscription status if their 'paid_until'
        date has passed (for paid users) or resets free user chats monthly.
        This method should be called periodically or before any chat-related checks.
        """
        now = datetime.utcnow()

        # Logic for PAID user subscription expiration
        if self.paid and self.paid_until: # Check if user is marked paid and has a paid_until date
            if now > self.paid_until:
                # Subscription has expired, revert to free user status
                self.paid = False
                self.paid_until = None
                self.chats_used = 0 # Reset chats used for the new free period
                self.last_reset = now # Mark the start of their new free period
                self.total_chats_allowed = 10 # Revert to the default free tier chat limit
                print(f"User {self.id}'s paid subscription expired. Reverted to free tier. Chats used: {self.chats_used}.")
        elif not self.paid: # Logic for FREE user monthly reset
            # If user is not paid AND 30 days have passed since their last reset
            # Ensure last_reset is not None, though it defaults to utcnow()
            if self.last_reset is None or (now - self.last_reset) > timedelta(days=30):
                self.chats_used = 0 # Reset chats used for the new free month
                self.last_reset = now # Mark the start of this new free month
                self.total_chats_allowed = 10 # Ensure free tier limit is set
                print(f"User {self.id}'s free chat period reset. Chats used: {self.chats_used}.")
