from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime
import os

load_dotenv()

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

client = MongoClient(os.getenv("MONGO_URI"))
db = client["voting_system"]
users_col = db["users"]
elections_col = db["elections"]

# ── Admin check decorator ─────────────────────────────────
def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("user_role") != "admin":
            flash("Admin access only!", "danger")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated

# ── Admin Dashboard ───────────────────────────────────────
@admin_bp.route("/")
@admin_required
def dashboard():
    total_users = users_col.count_documents({"role": "voter"})
    total_elections = elections_col.count_documents({})
    active_elections = elections_col.count_documents({"status": "active"})
    return render_template("admin/dashboard.html",
                           total_users=total_users,
                           total_elections=total_elections,
                           active_elections=active_elections)

# ── Create Election ───────────────────────────────────────
@admin_bp.route("/create-election", methods=["GET", "POST"])
@admin_required
def create_election():
    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]
        start_time = request.form["start_time"]
        end_time = request.form["end_time"]

        candidates = []
        names = request.form.getlist("candidate_name")
        descriptions = request.form.getlist("candidate_desc")
        for name, desc in zip(names, descriptions):
            if name.strip():
                candidates.append({"name": name, "description": desc, "votes": 0})

        elections_col.insert_one({
            "title": title,
            "description": description,
            "start_time": datetime.fromisoformat(start_time),
            "end_time": datetime.fromisoformat(end_time),
            "candidates": candidates,
            "status": "active",
            "created_at": datetime.utcnow()
        })

        flash("Election created successfully!", "success")
        return redirect(url_for("admin.view_elections"))

    return render_template("admin/create_election.html")

# ── View All Elections ────────────────────────────────────
@admin_bp.route("/elections")
@admin_required
def view_elections():
    elections = list(elections_col.find().sort("created_at", -1))
    return render_template("admin/elections.html", elections=elections)

# ── View All Voters ───────────────────────────────────────
@admin_bp.route("/voters")
@admin_required
def view_voters():
    voters = list(users_col.find({"role": "voter"}).sort("created_at", -1))
    return render_template("admin/voters.html", voters=voters)


# ── Election Results (Admin View) ─────────────────────────
@admin_bp.route("/results/<election_id>")
@admin_required
def election_results(election_id):
    from bson import ObjectId
    election = elections_col.find_one({"_id": ObjectId(election_id)})
    if not election:
        flash("Election not found!", "danger")
        return redirect(url_for("admin.view_elections"))

    total_votes = sum(c["votes"] for c in election["candidates"])
    winner = max(election["candidates"], key=lambda x: x["votes"]) if total_votes > 0 else None

    return render_template("admin/results.html",
                           election=election,
                           total_votes=total_votes,
                           winner=winner)