#!/usr/bin/env python3
"""Small SQLite-backed API and static server for freelance.community."""
from __future__ import annotations

import json
import mimetypes
import os
import secrets
import sqlite3
import urllib.parse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
DB_PATH = Path(os.environ.get("FC_DATABASE", Path(__file__).with_name("community.sqlite3")))
MAX_BODY = 2 * 1024 * 1024
COLLECTIONS = {"opportunities", "freelancers", "community_posts", "applications"}


def connect():
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    return db


def initialize():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("""CREATE TABLE IF NOT EXISTS records (
            id TEXT PRIMARY KEY,
            collection TEXT NOT NULL,
            email TEXT,
            data TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS records_collection ON records(collection, created_at DESC)")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS freelancer_email ON records(email) WHERE collection='freelancers' AND email IS NOT NULL")


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Handler(BaseHTTPRequestHandler):
    server_version = "FreelanceCommunity/0.1"

    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length > MAX_BODY:
            raise ValueError("Request body is too large (2 MB maximum).")
        raw = self.rfile.read(length)
        try:
            value = json.loads(raw or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError("Send valid JSON.") from exc
        if not isinstance(value, dict):
            raise ValueError("Send a JSON object.")
        return value

    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        if path == "/api/health":
            return self.send_json(200, {"ok": True, "service": "freelance.community"})
        api_name = path.removeprefix("/api/")
        collection = {"opportunities": "opportunities", "freelancers": "freelancers", "community/posts": "community_posts", "applications": "applications"}.get(api_name)
        if path.startswith("/api/"):
            if not collection:
                return self.send_json(404, {"error": "API route not found."})
            with connect() as db:
                rows = db.execute("SELECT data FROM records WHERE collection=? ORDER BY created_at DESC", (collection,)).fetchall()
            return self.send_json(200, [json.loads(row["data"]) for row in rows])
        return self.serve_frontend(path)

    def do_POST(self):
        path = urllib.parse.urlsplit(self.path).path
        collection = {"/api/opportunities": "opportunities", "/api/freelancers": "freelancers", "/api/community/posts": "community_posts", "/api/applications": "applications"}.get(path)
        if not collection:
            return self.send_json(404, {"error": "API route not found."})
        try:
            item = self.read_json()
            if collection == "opportunities":
                required = ("title", "company", "description")
            elif collection == "freelancers":
                required = ("name", "email")
            elif collection == "community_posts":
                required = ("name", "copy")
            else:
                required = ("jobTitle", "applicantName", "applicantEmail", "recruiterEmail")
            if any(not str(item.get(field, "")).strip() for field in required):
                return self.send_json(400, {"error": "Required fields are missing."})
            if collection == "freelancers":
                item["email"] = str(item["email"]).strip().lower()
                with connect() as db:
                    row = db.execute("SELECT id, created_at FROM records WHERE collection='freelancers' AND email=?", (item["email"],)).fetchone()
                    record_id = row["id"] if row else secrets.token_urlsafe(12)
                    created_at = row["created_at"] if row else now()
                    item.update(id=record_id, createdAt=created_at)
                    db.execute("INSERT INTO records(id,collection,email,data,created_at,updated_at) VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET email=excluded.email,data=excluded.data,updated_at=excluded.updated_at", (record_id, collection, item["email"], json.dumps(item, ensure_ascii=False), created_at, now()))
            else:
                record_id = secrets.token_urlsafe(12)
                item.update(id=record_id, createdAt=now())
                with connect() as db:
                    db.execute("INSERT INTO records(id,collection,email,data,created_at,updated_at) VALUES(?,?,?,?,?,?)", (record_id, collection, item.get("applicantEmail") if collection == "applications" else item.get("ownerEmail"), json.dumps(item, ensure_ascii=False), now(), now()))
            return self.send_json(201, item)
        except ValueError as exc:
            return self.send_json(400, {"error": str(exc)})
        except sqlite3.Error:
            return self.send_json(500, {"error": "The database could not save this record."})

    def serve_frontend(self, url_path):
        relative = "index.html" if url_path in ("", "/") else urllib.parse.unquote(url_path.lstrip("/"))
        target = (FRONTEND / relative).resolve()
        if not target.is_relative_to(FRONTEND.resolve()) or not target.is_file():
            return self.send_json(404, {"error": "Page not found."})
        content = target.read_bytes()
        kind = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if kind.startswith("text/") or kind in ("application/javascript", "application/json"):
            kind += "; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, fmt, *args):
        print(f"{self.log_date_time_string()} {self.address_string()} {fmt % args}")


if __name__ == "__main__":
    initialize()
    host = os.environ.get("FC_HOST", "127.0.0.1")
    port = int(os.environ.get("FC_PORT", "8000"))
    print(f"freelance.community server running at http://{host}:{port}")
    ThreadingHTTPServer((host, port), Handler).serve_forever()
