import sqlite3
from datetime import date, timedelta

from flask import Flask, g, jsonify, render_template, request

app = Flask(__name__)
DB_PATH = "workout_log.db"


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
    db = get_db()
    rows = db.execute("SELECT DISTINCT exercise_name FROM exercises ORDER BY exercise_name").fetchall()
    return jsonify([r["exercise_name"] for r in rows])


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

    we = ws + timedelta(days=6)
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

    # volume per exercise
    vol_rows = db.execute(
        """SELECT exercise_name, SUM(weight_lbs * reps * sets) as volume
           FROM exercises WHERE date BETWEEN ? AND ?
           GROUP BY exercise_name ORDER BY volume DESC""",
        (days[0], days[-1]),
    ).fetchall()
    volumes = [dict(r) for r in vol_rows]

    # totals
    total_sets = db.execute(
        "SELECT COALESCE(SUM(sets),0) as total FROM exercises WHERE date BETWEEN ? AND ?",
        (days[0], days[-1]),
    ).fetchone()["total"]

    return jsonify({
        "week_start": days[0],
        "week_end": days[-1],
        "days": days,
        "daily": daily,
        "volumes": volumes,
        "total_sets": total_sets,
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
