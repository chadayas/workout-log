import os
import sqlite3
from datetime import date, timedelta

from flask import Flask, g, jsonify, render_template, request

app = Flask(__name__)
DB_PATH = os.path.join(os.path.expanduser("~"), "workout_log.db")

EXERCISE_MUSCLES = {
    "bench press": ["chest", "arms"],
    "incline bench": ["chest", "arms"],
    "overhead press": ["shoulders", "arms"],
    "lateral raise": ["shoulders"],
    "face pulls": ["shoulders", "back"],
    "delt flys": ["shoulders"],
    "bicep curl": ["arms"],
    "barebell bicep": ["arms"],
    "tricep extension": ["arms"],
    "dips": ["chest", "arms"],
    "incline db press": ["chest", "arms"],
    "flat db press": ["chest", "arms"],
    "squat": ["quads","hamstrings","calves"],
    "leg press": ["quads"],
    "leg curl": ["hamstrings"],
    "romanian deadlift": ["hamstrings", "back"],
    "deadlift": ["back", "hamstrings"],
    "barbell row": ["back", "arms"],
    "cable rows": ["back", "arms"],
    "lat pulldown": ["back", "arms"],
    "pull up": ["back", "arms"],
    "weighted pull ups": ["back", "arms"],
    "weighted ab crunches": ["abs"],
    "ab crunch machine": ["abs"],
    "leg raise": ["abs"],
    "plank": ["abs"],
    "calf raises": ["calves"],
}
BODY_PARTS = ["chest", "back", "shoulders", "arms", "quads", "hamstrings", "abs", "calves"]


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
        g.db.execute("""
            CREATE TABLE IF NOT EXISTS exercises (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                exercise_name TEXT NOT NULL,
                weight_lbs REAL NOT NULL,
                reps INTEGER NOT NULL,
                sets INTEGER NOT NULL
            )
        """)
        g.db.execute("""
            CREATE TABLE IF NOT EXISTS daily_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL UNIQUE,
                calories INTEGER,
                body_weight_lbs REAL
            )
        """)
        g.db.commit()
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


# ---- Pages ----

@app.route("/")
def index():
    return render_template("index.html")


# ---- Exercise API ----

@app.route("/api/exercises")
def get_exercises():
    d = request.args.get("date", date.today().isoformat())
    db = get_db()
    rows = db.execute(
        "SELECT id, exercise_name, weight_lbs, reps, sets FROM exercises WHERE date=? ORDER BY id",
        (d,),
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/exercises", methods=["POST"])
def add_exercise():
    data = request.get_json()
    db = get_db()
    db.execute(
        "INSERT INTO exercises (date, exercise_name, weight_lbs, reps, sets) VALUES (?,?,?,?,?)",
        (data["date"], data["exercise_name"], data["weight_lbs"], data["reps"], data["sets"]),
    )
    db.commit()
    return jsonify({"ok": True}), 201


@app.route("/api/exercises/<int:eid>", methods=["DELETE"])
def delete_exercise(eid):
    db = get_db()
    db.execute("DELETE FROM exercises WHERE id=?", (eid,))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/exercise-names")
def exercise_names():
    return jsonify(sorted(k.title() for k in EXERCISE_MUSCLES))


# ---- Daily Stats API ----

@app.route("/api/daily")
def get_daily():
    d = request.args.get("date", date.today().isoformat())
    db = get_db()
    row = db.execute("SELECT calories, body_weight_lbs FROM daily_log WHERE date=?", (d,)).fetchone()
    if row:
        return jsonify({"calories": row["calories"], "body_weight_lbs": row["body_weight_lbs"]})
    return jsonify({"calories": None, "body_weight_lbs": None})


@app.route("/api/daily/weight", methods=["POST"])
def save_weight():
    data = request.get_json()
    db = get_db()
    db.execute(
        """INSERT INTO daily_log (date, body_weight_lbs)
           VALUES (?, ?)
           ON CONFLICT(date) DO UPDATE SET body_weight_lbs=excluded.body_weight_lbs""",
        (data["date"], data["body_weight_lbs"]),
    )
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/daily/calories", methods=["POST"])
def save_calories():
    data = request.get_json()
    db = get_db()
    db.execute(
        """INSERT INTO daily_log (date, calories)
           VALUES (?, ?)
           ON CONFLICT(date) DO UPDATE SET calories=excluded.calories""",
        (data["date"], data["calories"]),
    )
    db.commit()
    return jsonify({"ok": True})


# ---- Weekly Summary API ----

@app.route("/api/weekly")
def get_weekly():
    start_str = request.args.get("start")
    if start_str:
        ws = date.fromisoformat(start_str)
    else:
        today = date.today()
        ws = today - timedelta(days=today.weekday())

    days = [(ws + timedelta(days=i)).isoformat() for i in range(7)]

    db = get_db()

    # daily logs for the week
    daily_rows = db.execute(
        "SELECT date, calories, body_weight_lbs FROM daily_log WHERE date BETWEEN ? AND ? ORDER BY date",
        (days[0], days[-1]),
    ).fetchall()
    daily_map = {r["date"]: dict(r) for r in daily_rows}

    daily = []
    for d in days:
        if d in daily_map:
            daily.append(daily_map[d])
        else:
            daily.append({"date": d, "calories": None, "body_weight_lbs": None})

    # per-exercise rows for the week
    ex_rows = db.execute(
        "SELECT exercise_name, weight_lbs, reps, sets FROM exercises WHERE date BETWEEN ? AND ?",
        (days[0], days[-1]),
    ).fetchall()

    # aggregate volume and sets per body part
    body_volume = {bp: 0 for bp in BODY_PARTS}
    muscle_sets = {bp: 0 for bp in BODY_PARTS}
    total_sets = 0
    for r in ex_rows:
        total_sets += r["sets"]
        parts = EXERCISE_MUSCLES.get(r["exercise_name"].lower(), [])
        vol = r["weight_lbs"] * r["reps"] * r["sets"]
        for bp in parts:
            body_volume[bp] += vol
            muscle_sets[bp] += r["sets"]

    # average body weight for this week and previous week
    avg_row = db.execute(
        "SELECT AVG(body_weight_lbs) as avg FROM daily_log WHERE date BETWEEN ? AND ? AND body_weight_lbs IS NOT NULL",
        (days[0], days[-1]),
    ).fetchone()
    avg_weight = round(avg_row["avg"], 1) if avg_row["avg"] else None

    prev_start = (ws - timedelta(days=7)).isoformat()
    prev_end = (ws - timedelta(days=1)).isoformat()
    prev_row = db.execute(
        "SELECT AVG(body_weight_lbs) as avg FROM daily_log WHERE date BETWEEN ? AND ? AND body_weight_lbs IS NOT NULL",
        (prev_start, prev_end),
    ).fetchone()
    prev_avg_weight = round(prev_row["avg"], 1) if prev_row["avg"] else None

    return jsonify({
        "week_start": days[0],
        "week_end": days[-1],
        "days": days,
        "daily": daily,
        "body_volume": body_volume,
        "muscle_sets": muscle_sets,
        "total_sets": total_sets,
        "avg_weight": avg_weight,
        "prev_avg_weight": prev_avg_weight,
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
