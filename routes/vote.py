from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from pymongo import MongoClient
from dotenv import load_dotenv
from bson import ObjectId
from datetime import datetime
import os

load_dotenv()

vote_bp = Blueprint("vote", __name__)

client = MongoClient(os.getenv("MONGO_URI"))
db = client["voting_system"]
elections_col = db["elections"]
votes_col = db["votes"]
users_col = db["users"]

# ── Voter Dashboard ───────────────────────────────────────
@vote_bp.route("/voter-dashboard")
def dashboard():
    if "user_id" not in session:
        flash("Please login first!", "danger")
        return redirect(url_for("auth.login"))

    now = datetime.utcnow()
    elections = list(elections_col.find({
        "status": "active",
        "start_time": {"$lte": now},
        "end_time": {"$gte": now}
    }))

    # Check which elections user already voted in
    voted_ids = []
    for e in elections:
        existing = votes_col.find_one({
            "election_id": str(e["_id"]),
            "voter_id": session["user_id"]
        })
        if existing:
            voted_ids.append(str(e["_id"]))

    return render_template("voter/dashboard.html",
                           elections=elections,
                           voted_ids=voted_ids)

# ── Vote Page ─────────────────────────────────────────────
@vote_bp.route("/vote/<election_id>", methods=["GET", "POST"])
def vote(election_id):
    if "user_id" not in session:
        flash("Please login first!", "danger")
        return redirect(url_for("auth.login"))

    election = elections_col.find_one({"_id": ObjectId(election_id)})
    if not election:
        flash("Election not found!", "danger")
        return redirect(url_for("vote.dashboard"))

    # Check already voted
    existing = votes_col.find_one({
        "election_id": election_id,
        "voter_id": session["user_id"]
    })
    if existing:
        flash("You have already voted in this election!", "warning")
        return redirect(url_for("vote.dashboard"))

    if request.method == "POST":
        candidate_name = request.form.get("candidate")
        if not candidate_name:
            flash("Please select a candidate!", "danger")
            return redirect(url_for("vote.vote", election_id=election_id))

        # Save vote
        votes_col.insert_one({
            "election_id": election_id,
            "voter_id": session["user_id"],
            "candidate_name": candidate_name,
            "voted_at": datetime.utcnow()
        })

        # Increment candidate vote count
        elections_col.update_one(
            {
                "_id": ObjectId(election_id),
                "candidates.name": candidate_name
            },
            {"$inc": {"candidates.$.votes": 1}}
        )

        flash("✅ Your vote has been cast successfully!", "success")
        return redirect(url_for("vote.results", election_id=election_id))

    return render_template("voter/vote.html", election=election)

# ── Results Page ──────────────────────────────────────────
@vote_bp.route("/results/<election_id>")
def results(election_id):
    if "user_id" not in session:
        flash("Please login first!", "danger")
        return redirect(url_for("auth.login"))

    election = elections_col.find_one({"_id": ObjectId(election_id)})
    if not election:
        flash("Election not found!", "danger")
        return redirect(url_for("vote.dashboard"))

    total_votes = sum(c["votes"] for c in election["candidates"])
    winner = max(election["candidates"], key=lambda x: x["votes"]) if total_votes > 0 else None

    return render_template("voter/results.html",
                           election=election,
                           total_votes=total_votes,
                           winner=winner)