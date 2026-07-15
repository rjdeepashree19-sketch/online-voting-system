from datetime import datetime, timedelta
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from pymongo import MongoClient
from dotenv import load_dotenv
from flask_bcrypt import Bcrypt
import os, random, smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta

load_dotenv()

auth_bp = Blueprint("auth", __name__)
bcrypt = Bcrypt()

client = MongoClient(os.getenv("MONGO_URI"))
db = client["voting_system"]
users_col = db["users"]

# ── OTP Email Sender ──────────────────────────────────────
def send_otp_email(email, otp):
    try:
        import smtplib
        from email.mime.text import MIMEText
        msg = MIMEText(f"Your OTP is: {otp}\nValid for 5 minutes.")
        msg["Subject"] = "Your OTP - Online Voting System"
        msg["From"] = os.getenv("MAIL_EMAIL")
        msg["To"] = email
        with smtplib.SMTP("smtp-relay.brevo.com", 587, timeout=15) as server:
            server.starttls()
            server.login(os.getenv("BREVO_LOGIN"), os.getenv("BREVO_PASSWORD"))
            server.send_message(msg)
    except Exception as e:
        print(f"Email error: {e}")

# ── Register ──────────────────────────────────────────────
@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        # Check if email already exists
        if users_col.find_one({"email": email}):
            flash("Email already registered!", "danger")
            return redirect(url_for("auth.register"))

        # Generate OTP
        otp = str(random.randint(100000, 999999))
        expiry = datetime.utcnow() + timedelta(minutes=5)

        # Temporarily store user data in session
        session["temp_user"] = {
            "name": name,
            "email": email,
            "password": bcrypt.generate_password_hash(password).decode("utf-8"),
            "otp": otp,
            "expiry": expiry.isoformat()
        }

        def send_otp(email, otp):
            import threading
            thread = threading.Thread(target=send_otp_email, args=(email, otp))
            thread.daemon = True
            thread.start()
            return redirect(url_for("auth.verify_otp"))

# ── OTP Verification ──────────────────────────────────────
@auth_bp.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    if request.method == "POST":
        entered_otp = request.form["otp"]
        temp = session.get("temp_user")

        if not temp:
            flash("Session expired. Please register again.", "danger")
            return redirect(url_for("auth.register"))

        expiry = datetime.fromisoformat(temp["expiry"])
        if datetime.utcnow() > expiry:
            flash("OTP expired! Please register again.", "danger")
            return redirect(url_for("auth.register"))

        if entered_otp != temp["otp"]:
            flash("Wrong OTP! Try again.", "danger")
            return redirect(url_for("auth.verify_otp"))

        # Save user to DB
        users_col.insert_one({
            "name": temp["name"],
            "email": temp["email"],
            "password": temp["password"],
            "role": "voter",
            "created_at": datetime.utcnow()
        })

        session.pop("temp_user")
        flash("Registration successful! Please login.", "success")
        return redirect(url_for("auth.login"))

    return render_template("verify_otp.html")

# ── Login ─────────────────────────────────────────────────
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        user = users_col.find_one({"email": email})

        if not user or not bcrypt.check_password_hash(user["password"], password):
            flash("Invalid email or password!", "danger")
            return redirect(url_for("auth.login"))

        session["user_id"] = str(user["_id"])
        session["user_name"] = user["name"]
        session["user_role"] = user["role"]

        flash(f"Welcome, {user['name']}!", "success")
        return redirect(url_for("auth.dashboard"))

    return render_template("login.html")

# ── Dashboard ─────────────────────────────────────────────
@auth_bp.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        flash("Please login first!", "danger")
        return redirect(url_for("auth.login"))

    if session.get("user_role") == "admin":
        return redirect(url_for("admin.dashboard"))

    return redirect(url_for("vote.dashboard"))

# ── Logout ────────────────────────────────────────────────
@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully!", "info")
    return redirect(url_for("auth.login"))