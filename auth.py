# routes.py or auth.py
import os
from flask import Blueprint, request, jsonify, session
import google.auth.transport.requests
import google.oauth2.id_token
from models import db, User

auth_bp = Blueprint('auth', __name__)

@auth_bp.route("/login", methods=["POST"])
def login():
    try:
        data = request.get_json()
        token = data.get("credential")

        request_obj = google.auth.transport.requests.Request()
        id_info = google.oauth2.id_token.verify_oauth2_token(
            token, request_obj, audience=os.getenv("GOOGLE_CLIENT_ID")
        )

        if not id_info:
            return jsonify(success=False, message="Token verification failed"), 401

        user = User.query.get(id_info["sub"])
        if not user:
            user = User(
                id=id_info["sub"],
                email=id_info["email"],
                name=id_info.get("name", ""),
                profile_pic=id_info.get("picture", "")
            )
            db.session.add(user)

        session["user_id"] = id_info["sub"]
        db.session.commit()
        return jsonify(success=True)

    except Exception as e:
        return jsonify(success=False, message=str(e)), 500
