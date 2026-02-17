# Workout Log

A personal workout tracking web app for logging exercises, body weight, and daily calorie intake. Built with Flask and SQLite, designed to be accessed from your phone at the gym. Personal productivity app for me.

## Features

- **Log Workouts** -- Record exercises with weight (lbs), reps, and sets. Exercise names autocomplete from past entries.
- **Daily Body Weight** -- Log your morning fasted weigh-in independently from calories.
- **Daily Calories** -- Log your total calorie intake at the end of the day without overwriting your weight.
- **Weekly Summary** -- Interactive charts showing body weight trend, training volume per exercise, and daily calorie intake. Navigate between weeks. Includes a text summary with total sets, average calories, and weight change.

## Requirements

- Python 3.10+
- Flask

## Setup

```bash
pip install flask
```

## Usage

```bash
python3 app.py
```

The server starts on `http://0.0.0.0:5000`.

- **Local**: Open `http://localhost:5000` in your browser.
- **Phone (same WiFi)**: Open `http://<your-machine-ip>:5000` on your phone. Find your machine's IP with `hostname -I` on Linux or `ifconfig` on macOS.
- **Phone (anywhere)**: Use [Tailscale](https://tailscale.com/) to create a private mesh VPN between your machine and phone. Install Tailscale on both devices, then access the server at `http://<tailscale-ip>:5000` from anywhere.

## Project Structure

```
workout_log/
├── app.py              # Flask server and REST API
├── templates/
│   └── index.html      # Single-page frontend (HTML/CSS/JS)
├── workout_log.db      # SQLite database (created on first run)
└── README.md
```

## Database Schema

**exercises** -- One row per exercise entry.

| Column        | Type    | Description          |
|---------------|---------|----------------------|
| id            | INTEGER | Primary key          |
| date          | TEXT    | Date (YYYY-MM-DD)    |
| exercise_name | TEXT    | Name of the exercise |
| weight_lbs    | REAL    | Weight in pounds     |
| reps          | INTEGER | Repetitions          |
| sets          | INTEGER | Sets                 |

**daily_log** -- One row per day. Weight and calories are saved independently.

| Column          | Type    | Description            |
|-----------------|---------|------------------------|
| id              | INTEGER | Primary key            |
| date            | TEXT    | Date (YYYY-MM-DD), unique |
| calories        | INTEGER | Total daily calories   |
| body_weight_lbs | REAL    | Morning body weight    |

## API Endpoints

| Method | Endpoint                 | Description                        |
|--------|--------------------------|------------------------------------|
| GET    | `/`                      | Serve the web app                  |
| GET    | `/api/exercises?date=`   | Get exercises for a date           |
| POST   | `/api/exercises`         | Add an exercise                    |
| DELETE | `/api/exercises/<id>`    | Delete an exercise                 |
| GET    | `/api/exercise-names`    | Get distinct exercise names        |
| GET    | `/api/daily?date=`       | Get daily weight and calories      |
| POST   | `/api/daily/weight`      | Save body weight (won't touch calories) |
| POST   | `/api/daily/calories`    | Save calories (won't touch weight) |
| GET    | `/api/weekly?start=`     | Get weekly summary data            |

## Remote Access with Tailscale

1. Install Tailscale on your machine: https://tailscale.com/download
2. Install Tailscale on your phone (App Store / Google Play)
3. Sign into the same Tailscale account on both devices
4. Run `tailscale ip` on your machine to get its Tailscale IP (e.g. `100.x.x.x`)
5. Start the server: `python3 app.py`
6. On your phone, open `http://100.x.x.x:5000`

Tailscale is free for personal use. The connection is encrypted end-to-end and works over any network (WiFi, cellular, etc).

## Backup

Your data lives in `workout_log.db`. To back it up, just copy the file:

```bash
cp workout_log.db workout_log_backup.db
```
