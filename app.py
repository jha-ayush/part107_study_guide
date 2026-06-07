"""Part 107 Ground School - a server-rendered Python (Flask) web app.

All application logic lives in Python. Pages are rendered with Jinja templates;
there is no client-side application JavaScript. The 400-question bank is in
questions.json. Progress is stored on the server, keyed to a per-browser cookie.
"""
import json
import os
import random
import re
import secrets
import threading
import time
from pathlib import Path
from uuid import uuid4

from flask import (Flask, g, jsonify, redirect, render_template, request,
                   session, url_for, Response)
from markupsafe import Markup
from werkzeug.security import check_password_hash, generate_password_hash

ROOT = Path(__file__).resolve().parent
app = Flask(__name__)


def _secret_key():
    env = os.environ.get("FLASK_SECRET_KEY")
    if env:
        return env
    path = ROOT / ".flask_secret"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    key = secrets.token_hex(32)
    try:
        path.write_text(key, encoding="utf-8")
    except OSError:
        pass
    return key


app.secret_key = _secret_key()

# ---- Data -------------------------------------------------------------------
with open(ROOT / "questions.json", encoding="utf-8") as fh:
    QUESTIONS = json.load(fh)
for i, q in enumerate(QUESTIONS):
    q["id"] = i

BUCKETS = ["Regulations", "Airspace", "Charts", "Weather", "Operations", "Loading"]
LETTERS = "ABCD"
EXAM_N = min(60, len(QUESTIONS))
EXAM_PASS = 70
EXAM_MIN = 120
CODE_SUBTOPICS = {"METAR", "TAF", "Winds Aloft"}

# ---- Per-browser progress store (file-based) --------------------------------
STORE_FILE = ROOT / "progress_store.json"
_lock = threading.Lock()
COOKIE = "p107_uid"
_UID_RE = re.compile(r"^[a-f0-9]{32}$")


def _fresh():
    return {"lifetime": {}, "missed": {}, "sessions": [],
            "prefs": {"dark": False}, "exam": None}


def _read_all():
    if STORE_FILE.exists():
        try:
            return json.loads(STORE_FILE.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return {}
    return {}


def _write_all(data):
    STORE_FILE.write_text(json.dumps(data), encoding="utf-8")


def get_record(uid):
    rec = _read_all().get(uid)
    if not isinstance(rec, dict):
        return _fresh()
    base = _fresh()
    base.update(rec)
    base["prefs"] = {**{"dark": False}, **(rec.get("prefs") or {})}
    return base


def save_record(uid, rec):
    with _lock:
        data = _read_all()
        data[uid] = rec
        _write_all(data)


# ---- User accounts (file-based) ---------------------------------------------
USERS_FILE = ROOT / "users.json"
_users_lock = threading.Lock()
_UNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,24}$")


def read_users():
    if USERS_FILE.exists():
        try:
            return json.loads(USERS_FILE.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return {}
    return {}


def write_users(users):
    with _users_lock:
        USERS_FILE.write_text(json.dumps(users), encoding="utf-8")


def validate_credentials(username, password):
    if not _UNAME_RE.match(username or ""):
        return "Username must be 3 to 24 letters, numbers, or underscores."
    if len(password or "") < 6:
        return "Password must be at least 6 characters."
    return None


def migrate_device_to_user(user_id):
    """When an account has no progress yet, adopt this browser's anonymous progress."""
    urec = get_record("u:" + user_id)
    drec = get_record("d:" + g.uid)
    user_empty = not (urec["lifetime"] or urec["missed"] or urec["sessions"])
    device_has = drec["lifetime"] or drec["missed"] or drec["sessions"]
    if user_empty and device_has:
        for k in ("lifetime", "missed", "sessions", "prefs"):
            urec[k] = drec[k]
        save_record("u:" + user_id, urec)


# ---- Helpers ----------------------------------------------------------------
def q_html(q):
    t = q["q"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    if q.get("s") in CODE_SUBTOPICS:
        t = re.sub(r"'([^']+)'", r'<span class="code">\1</span>', t)
    return Markup(t)


def shuffled(order, q):
    return [{"idx": oi, "letter": LETTERS[i], "text": q["c"][oi]}
            for i, oi in enumerate(order)]


def color_for(pct):
    if pct is None:
        return "var(--line)"
    return "var(--green)" if pct >= 70 else ("var(--amber)" if pct >= 50 else "var(--red)")


def bucket_pct(rec, name):
    v = rec["lifetime"].get(name)
    if not v or not v.get("n"):
        return None
    return round(v["c"] / v["n"] * 100)


def mmss(seconds):
    seconds = max(0, int(seconds))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def record_answer(rec, q, correct):
    b = q["b"]
    lt = rec["lifetime"].setdefault(b, {"c": 0, "n": 0})
    lt["n"] += 1
    if correct:
        lt["c"] += 1
        rec["missed"].pop(str(q["id"]), None)
    else:
        rec["missed"][str(q["id"])] = rec["missed"].get(str(q["id"]), 0) + 1


def grouped_missed(rec, only_bucket=None):
    groups = []
    for b in BUCKETS:
        if only_bucket and b != only_bucket:
            continue
        items = []
        for qid_str, misses in rec["missed"].items():
            q = QUESTIONS[int(qid_str)]
            if q["b"] != b:
                continue
            items.append({"q_html": q_html(q), "letter": LETTERS[q["a"]],
                          "answer": q["c"][q["a"]], "e": q["e"], "misses": misses})
        if items:
            items.sort(key=lambda x: -x["misses"])
            groups.append({"name": b, "qs": items})
    return groups


# ---- Request lifecycle ------------------------------------------------------
@app.before_request
def _load_state():
    uid = request.cookies.get(COOKIE, "")
    if not _UID_RE.match(uid):
        uid = uuid4().hex
    g.uid = uid
    uname = session.get("user")
    g.user = read_users().get(uname) if uname else None
    g.owner = ("u:" + g.user["id"]) if g.user else ("d:" + uid)
    g.record = get_record(g.owner)


@app.after_request
def _persist_cookie(resp):
    try:
        resp.set_cookie(COOKIE, g.uid, max_age=60 * 60 * 24 * 365, samesite="Lax")
    except Exception:
        pass
    return resp


@app.context_processor
def _inject():
    return {"dark": g.record["prefs"].get("dark", False), "user": g.user}


# ---- Routes -----------------------------------------------------------------
@app.route("/")
def home():
    rec = g.record
    tot_c = sum(v["c"] for v in rec["lifetime"].values())
    tot_n = sum(v["n"] for v in rec["lifetime"].values())
    buckets = []
    for b in BUCKETS:
        pct = bucket_pct(rec, b)
        buckets.append({"name": b, "count": sum(1 for q in QUESTIONS if q["b"] == b),
                        "pct": pct, "color": color_for(pct)})
    return render_template("home.html",
                           lifetime_pct=(round(tot_c / tot_n * 100) if tot_n else None),
                           total_answered=tot_n, to_review=len(rec["missed"]),
                           buckets=buckets, exam_n=EXAM_N, exam_min=EXAM_MIN,
                           exam_pass=EXAM_PASS)


@app.route("/practice")
def practice():
    bucket = request.args.get("bucket", "All")
    pool = QUESTIONS if bucket == "All" else [q for q in QUESTIONS if q["b"] == bucket]
    if not pool:
        return redirect(url_for("home"))
    q = random.choice(pool)
    order = list(range(len(q["c"])))
    random.shuffle(order)
    return render_template("practice.html", answered=False, q={**q, "q_html": q_html(q)},
                           choices=shuffled(order, q), bucket=bucket)


@app.route("/practice/answer", methods=["POST"])
def practice_answer():
    qid = int(request.form.get("qid", -1))
    bucket = request.form.get("bucket", "All")
    chosen = int(request.form.get("choice", -1))
    if not (0 <= qid < len(QUESTIONS)):
        return redirect(url_for("home"))
    q = QUESTIONS[qid]
    correct = chosen == q["a"]
    record_answer(g.record, q, correct)
    save_record(g.owner, g.record)
    choices = [{"idx": i, "letter": LETTERS[i], "text": q["c"][i]} for i in range(len(q["c"]))]
    return render_template("practice.html", answered=True, q={**q, "q_html": q_html(q)},
                           choices=choices, chosen=chosen, correct=correct, bucket=bucket)


@app.route("/exam/start")
def exam_start():
    qids = random.sample(range(len(QUESTIONS)), EXAM_N)
    order = {}
    for qid in qids:
        o = list(range(len(QUESTIONS[qid]["c"])))
        random.shuffle(o)
        order[str(qid)] = o
    g.record["exam"] = {"qids": qids, "order": order, "answers": {}, "start": time.time()}
    save_record(g.owner, g.record)
    return redirect(url_for("exam_q", n=0))


@app.route("/exam/q/<int:n>")
def exam_q(n):
    exam = g.record.get("exam")
    if not exam:
        return redirect(url_for("exam_start"))
    remaining = EXAM_MIN * 60 - (time.time() - exam["start"])
    if remaining <= 0:
        return redirect(url_for("exam_submit"))
    total = len(exam["qids"])
    n = max(0, min(n, total - 1))
    qid = exam["qids"][n]
    q = QUESTIONS[qid]
    saved = exam["answers"].get(str(qid))
    answered_set = {i for i, qd in enumerate(exam["qids"]) if str(qd) in exam["answers"]}
    return render_template("exam.html", n=n, total=total, q={**q, "q_html": q_html(q)},
                           choices=shuffled(exam["order"][str(qid)], q),
                           saved=(int(saved) if saved is not None else -1),
                           answered_set=answered_set, remaining=int(remaining),
                           remaining_mmss=mmss(remaining))


@app.route("/exam/nav", methods=["POST"])
def exam_nav():
    exam = g.record.get("exam")
    if not exam:
        return redirect(url_for("home"))
    n = int(request.form.get("n", 0))
    choice = request.form.get("choice")
    if choice is not None and 0 <= n < len(exam["qids"]):
        exam["answers"][str(exam["qids"][n])] = int(choice)
    save_record(g.owner, g.record)
    if request.form.get("finish"):
        return redirect(url_for("exam_submit"))
    goto = int(request.form.get("goto", n))
    return redirect(url_for("exam_q", n=goto))


@app.route("/exam/submit")
def exam_submit():
    exam = g.record.get("exam")
    if not exam:
        return redirect(url_for("home"))
    qids = exam["qids"]
    answers = exam["answers"]
    correct = 0
    per = {}
    missed_now = []
    for qid in qids:
        q = QUESTIONS[qid]
        ok = answers.get(str(qid)) == q["a"]
        p = per.setdefault(q["b"], {"c": 0, "n": 0})
        p["n"] += 1
        if ok:
            p["c"] += 1
            correct += 1
        else:
            missed_now.append(q)
        record_answer(g.record, q, ok)
    total = len(qids)
    pct = round(correct / total * 100) if total else 0
    passed = pct >= EXAM_PASS
    elapsed = time.time() - exam["start"]
    g.record["sessions"].append({"date": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                 "mode": "exam", "pct": pct, "correct": correct,
                                 "total": total, "passed": passed})
    g.record["sessions"] = g.record["sessions"][-50:]
    g.record["exam"] = None
    save_record(g.owner, g.record)

    by_bucket = []
    for b in BUCKETS:
        if b in per:
            p = per[b]
            pp = round(p["c"] / p["n"] * 100)
            by_bucket.append({"name": b, "c": p["c"], "n": p["n"], "pct": pp,
                              "color": color_for(pp)})
    missed = []
    for b in BUCKETS:
        items = [{"q_html": q_html(q), "letter": LETTERS[q["a"]],
                  "answer": q["c"][q["a"]], "e": q["e"]}
                 for q in missed_now if q["b"] == b]
        if items:
            missed.append({"name": b, "qs": items})
    return render_template("exam_result.html", pct=pct, passed=passed, correct=correct,
                           total=total, time_used=mmss(elapsed), exam_pass=EXAM_PASS,
                           pass_color=color_for(pct), by_bucket=by_bucket, missed=missed)


@app.route("/review")
def review():
    rec = g.record
    active = request.args.get("bucket")
    if active not in BUCKETS:
        active = None
    lifetime = []
    for b in BUCKETS:
        v = rec["lifetime"].get(b)
        if v and v.get("n"):
            pp = round(v["c"] / v["n"] * 100)
            lifetime.append({"name": b, "c": v["c"], "n": v["n"], "pct": pp,
                             "color": color_for(pp)})
    return render_template("review.html", lifetime=lifetime,
                           missed=grouped_missed(rec, active),
                           bucket_names=BUCKETS, active_bucket=active)


@app.route("/theme/toggle")
def toggle_theme():
    g.record["prefs"]["dark"] = not g.record["prefs"].get("dark", False)
    save_record(g.owner, g.record)
    return redirect(request.referrer or url_for("home"))


@app.route("/progress/reset", methods=["POST"])
def reset_progress():
    g.record = _fresh()
    save_record(g.owner, g.record)
    return redirect(url_for("home"))


@app.route("/progress/export")
def export_progress():
    payload = json.dumps({k: g.record[k] for k in ("lifetime", "missed", "sessions", "prefs")},
                         indent=2)
    return Response(payload, mimetype="application/json",
                    headers={"Content-Disposition": "attachment; filename=part107-progress.json"})


@app.route("/api/health")
def api_health():
    return jsonify(status="ok", questions=len(QUESTIONS))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        err = validate_credentials(username, password)
        users = read_users()
        if not err and username.lower() in users:
            err = "That username is already taken."
        if err:
            return render_template("register.html", error=err, username=username)
        user_id = uuid4().hex
        users[username.lower()] = {"id": user_id, "username": username,
                                   "pw_hash": generate_password_hash(password),
                                   "created": time.strftime("%Y-%m-%dT%H:%M:%S")}
        write_users(users)
        session["user"] = username.lower()
        migrate_device_to_user(user_id)
        return redirect(url_for("home"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        user = read_users().get(username)
        if not user or not check_password_hash(user["pw_hash"], password):
            return render_template("login.html", error="Wrong username or password.",
                                   username=request.form.get("username", ""))
        session["user"] = username
        migrate_device_to_user(user["id"])
        return redirect(url_for("home"))
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.pop("user", None)
    return redirect(url_for("home"))


if __name__ == "__main__":
    print("Part 107 Ground School running at http://127.0.0.1:8000")
    app.run(host="127.0.0.1", port=8000, debug=True)
