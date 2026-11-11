# freelance.community backend

A dependency-free Python API with a SQLite database. It serves the current frontend and stores opportunities, freelancer profiles, and community posts persistently.

## Run locally

From the repository root:

```sh
python3 backend/server.py
```

Open <http://127.0.0.1:8000>. The database is created at `backend/community.sqlite3` on first run. Set `FC_PORT`, `FC_HOST`, or `FC_DATABASE` to override the defaults.

## API

- `GET /api/health`
- `GET|POST /api/opportunities`
- `GET|POST /api/freelancers` (profile submissions are upserted by email)
- `GET|POST /api/community/posts`

Responses use JSON. POST requests accept a JSON object and return the saved record. The current preview sign-in remains browser-only; secure accounts, authorization, and protected admin writes are not part of this first backend slice.
