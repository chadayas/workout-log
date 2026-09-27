# Workout Log Status

Last updated: 2026-09-26

## Current state

The workout log is implemented, committed, pushed to GitHub, and deployed on the always-on `clearmind-server` laptop.

The production dashboard is available at:

- https://chadyap.com/workout/

The Custom GPT Actions schema is available at:

- https://chadyap.com/openapi.json

The Custom GPT itself has not been created or configured in ChatGPT yet. The server side is ready for it.

## Dashboard behavior

The Dashboard tab displays data for the selected date, including:

- Calories consumed versus the 2,600 kcal target
- Protein, carbohydrates, and fat
- Body weight
- Food entries
- Workout entries

Body weight appears in the **Body Weight** card near the top of the Dashboard when the selected date matches the weigh-in date. It also appears in Daily Stats.

A `202.6 lbs` body-weight entry currently exists for `2026-09-26`.

The dashboard previously calculated its default date in UTC, which could select the next day during the evening in US time zones. Commit `29862be` changed it to use the browser's local date.

## Implemented logging

### Nutrition

Each food entry stores:

- Food name
- Calories
- Protein in grams
- Carbohydrates in grams
- Fat in grams
- Date

The default daily calorie target is 2,600 kcal.

### Workouts

Each workout entry stores:

- Exercise name
- Weight in pounds
- Repetitions
- Sets
- Date

Matching entries for the same date, exercise, weight, and repetitions are combined. For example, logging `1 set bench press at 225 for 10` twice produces one `2 × 225 lbs × 10` row.

### Body weight

One body-weight value is stored per date. Logging another value for the same date replaces that date's prior value.

## GPT integrations

### Custom GPT Actions

The public OpenAPI schema exposes these authenticated operations:

- `logFood`
- `logExercise`
- `logBodyWeight`
- `getDailyDashboard`
- `getExercises`

Custom GPT Actions authenticate with the `X-API-Key` request header.

The API token is stored only on the server in:

- `/etc/workout-log.env`

Retrieve it without posting it publicly:

```bash
ssh root@clearmind-server
. /etc/workout-log.env
printf '%s\n' "$WORKOUT_LOG_API_TOKEN"
```

The copyable Custom GPT prompt is in:

- `CUSTOM_GPT_INSTRUCTIONS.txt`

The remaining user step is to create a Custom GPT, import `https://chadyap.com/openapi.json`, configure API-key authentication with the `X-API-Key` header, paste the token, and paste `CUSTOM_GPT_INSTRUCTIONS.txt` into the GPT Instructions field.

Once configured, the same Custom GPT will be available from the ChatGPT website and mobile app when signed into the same ChatGPT account.

### Removed interfaces

The dashboard's embedded GPT chat, microphone, and Send button were removed in favor of using Custom GPT from the ChatGPT mobile app or website. The Cutting tab was also removed. The dashboard, manual workout and daily-stat forms, weekly charts, and authenticated Custom GPT Actions remain available.

## Production architecture

```text
ChatGPT mobile/web or browser
              |
              | HTTPS
              v
      https://chadyap.com
              |
            Nginx
              |
       127.0.0.1:5000
              |
    Gunicorn + Flask app
              |
           SQLite
```

### Production paths

- Application checkout: `/opt/workout-log`
- Python virtual environment: `/opt/workout-log/.venv`
- SQLite database: `/var/lib/workout-log/workout_log.db`
- Environment and API token: `/etc/workout-log.env`
- Systemd service: `/etc/systemd/system/workout-log.service`
- Nginx configuration: `/etc/nginx/nginx.conf`
- Pre-deployment Nginx backup: `/etc/nginx/nginx.conf.pre-workout`

### Service behavior

`workout-log.service` is enabled at boot and configured with `Restart=always`. It runs Gunicorn as the restricted `workout-log` system user. Nginx is also enabled and active.

As long as `clearmind-server` is powered on, connected to the internet, and Nginx can serve `chadyap.com`, the API remains available to the configured Custom GPT.

Useful health checks:

```bash
ssh root@clearmind-server
systemctl is-enabled workout-log
systemctl is-active workout-log nginx
systemctl status workout-log
journalctl -u workout-log -n 100 --no-pager
```

## Security

All `/api/*` routes require the configured `X-API-Key`. An unauthenticated API request returns HTTP 401. The schema at `/openapi.json` is public so ChatGPT can import it, but the operations described by the schema require authentication.

The API token is not committed to Git and is not embedded in the web page. The dashboard stores a token entered through **API & Custom GPT Setup** in that browser's local storage.

The production service uses:

- A dedicated system user
- `NoNewPrivileges=true`
- A read-only system filesystem except for the database directory
- A root-only environment file with mode 600

## Deployment verification

The deployed setup was verified with:

- Public dashboard response: HTTP 200
- Public OpenAPI schema response: HTTP 200
- Unauthenticated API response: HTTP 401
- Authenticated public exercise write: successful
- Authenticated exercise read: successful
- Smoke-test record deletion: successful
- Nginx configuration validation: successful
- `workout-log.service`: enabled and active
- `nginx`: active

The automated application tests cover food totals, the 2,600 kcal target, body-weight logging, GPT action execution, matching workout-set aggregation, API authentication, schema publication, and transaction rollback.

## Updating production

After pushing a new application commit, deploy it with:

```bash
ssh root@clearmind-server
git -C /opt/workout-log pull --ff-only
systemctl restart workout-log
systemctl is-active workout-log
```

Nginx only needs to be reloaded when its configuration changes:

```bash
nginx -t && systemctl reload nginx
```

## Relevant commits

- `add78de` — add food and macro tracking
- `2a41727` — merge matching workout sets
- `32eb4c5` — add GPT fitness actions
- `6982200` — add GPT dashboard chat and voice input
- `278f1bd` — secure and publish Custom GPT actions
- `ec5e48f` — add Custom GPT setup controls
- `4ebba4d` — test GPT logging and authentication
- `f06d930` — add Custom GPT instruction template
- `29862be` — use local date on dashboard
