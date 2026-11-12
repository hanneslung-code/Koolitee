from __future__ import annotations

import hashlib
import os
import re
import secrets
import smtplib
import sqlite3
import time
from datetime import timedelta
from zoneinfo import ZoneInfo
from email.message import EmailMessage
from functools import wraps
from pathlib import Path
from urllib.parse import urlparse

from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from config import MODES, REGIONS, SCHOOLS

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "data" / "koolitee.sqlite3"))
APP_ENV = os.getenv("APP_ENV", "development").lower()
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")

app = Flask(__name__)
_secret_key = os.getenv("SECRET_KEY")
if APP_ENV == "production" and (not _secret_key or len(_secret_key) < 32):
    raise RuntimeError("Production requires SECRET_KEY with at least 32 characters.")
app.secret_key = _secret_key or "local-development-key-change-before-deployment"
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=(APP_ENV == "production"),
    PERMANENT_SESSION_LIFETIME=timedelta(hours=10),
    MAX_CONTENT_LENGTH=64 * 1024,
)


def now_ts() -> int:
    return int(time.time())


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(DB_PATH, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 15000")
        g.db = connection
    return g.db


@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA journal_mode = WAL")
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE COLLATE NOCASE,
            child_name TEXT NOT NULL,
            guardian_email TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            school TEXT NOT NULL,
            region TEXT NOT NULL,
            area TEXT NOT NULL,
            mode TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 0,
            parent_consent_at INTEGER,
            created_at INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_users_school_region_area
          ON users(school, region, area, active);
        CREATE TABLE IF NOT EXISTS tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token_hash TEXT NOT NULL UNIQUE,
            purpose TEXT NOT NULL,
            expires_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS invitations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            recipient_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            status TEXT NOT NULL CHECK(status IN ('pending','accepted','declined','closed')),
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            CHECK(sender_id <> recipient_id)
        );
        CREATE INDEX IF NOT EXISTS idx_invites_recipient_status
          ON invitations(recipient_id, status);
        CREATE INDEX IF NOT EXISTS idx_invites_sender_status
          ON invitations(sender_id, status);
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invitation_id INTEGER NOT NULL REFERENCES invitations(id) ON DELETE CASCADE,
            sender_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            body TEXT NOT NULL,
            created_at INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_messages_invite_time
          ON messages(invitation_id, created_at);
        CREATE TABLE IF NOT EXISTS blocks (
            blocker_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            blocked_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at INTEGER NOT NULL,
            PRIMARY KEY(blocker_id, blocked_id),
            CHECK(blocker_id <> blocked_id)
        );
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reporter_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            reported_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            invitation_id INTEGER REFERENCES invitations(id) ON DELETE SET NULL,
            reason TEXT NOT NULL,
            created_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS login_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_address TEXT NOT NULL,
            created_at INTEGER NOT NULL
        );
        """
    )
    db.commit()
    db.close()


init_db()


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_token(db: sqlite3.Connection, user_id: int, purpose: str, ttl: int = 60 * 60 * 24) -> str:
    raw = secrets.token_urlsafe(32)
    db.execute(
        "INSERT INTO tokens(user_id, token_hash, purpose, expires_at) VALUES(?,?,?,?)",
        (user_id, token_digest(raw), purpose, now_ts() + ttl),
    )
    return raw


def send_email(recipient: str, subject: str, body: str) -> bool:
    """Send via configured SMTP. In Docker testing, Mailpit captures these messages."""
    host = os.getenv("SMTP_HOST")
    if not host:
        app.logger.error("SMTP_HOST is not configured; cannot send email to %s", recipient)
        return False
    message = EmailMessage()
    message["From"] = os.getenv("SMTP_FROM", "Koolitee kaaslane <no-reply@localhost>")
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)
    port = int(os.getenv("SMTP_PORT", "587"))
    try:
        with smtplib.SMTP(host, port, timeout=12) as smtp:
            if os.getenv("SMTP_STARTTLS", "true").lower() == "true":
                smtp.starttls()
            username = os.getenv("SMTP_USER")
            password = os.getenv("SMTP_PASSWORD")
            if username and password:
                smtp.login(username, password)
            smtp.send_message(message)
        return True
    except Exception:
        app.logger.exception("Email delivery failed")
        return False


def send_guardian_notice(user: sqlite3.Row | dict, subject: str, body: str) -> bool:
    return send_email(user["guardian_email"], subject, body)


def csrf_value() -> str:
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


@app.context_processor
def inject_globals():
    return {"csrf_token": csrf_value, "current_user": getattr(g, "user", None)}


@app.before_request
def load_user_and_check_csrf():
    g.user = None
    user_id = session.get("user_id")
    if user_id:
        user = get_db().execute("SELECT * FROM users WHERE id=? AND active=1", (user_id,)).fetchone()
        if user:
            g.user = dict(user)
        else:
            session.clear()
    if request.method == "POST":
        sent = request.form.get("csrf_token", "")
        saved = session.get("csrf_token", "")
        if not saved or not secrets.compare_digest(sent, saved):
            abort(400, description="Vormi turvakontroll ebaõnnestus. Laadi leht uuesti ja proovi uuesti.")


@app.after_request
def set_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
        "form-action 'self'; base-uri 'self'; frame-ancestors 'none'"
    )
    if APP_ENV == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not g.user:
            flash("Selle vaate kasutamiseks logi kõigepealt sisse.", "info")
            return redirect(url_for("index"))
        return view(*args, **kwargs)
    return wrapped


def is_blocked(db, first_id: int, second_id: int) -> bool:
    return db.execute(
        "SELECT 1 FROM blocks WHERE (blocker_id=? AND blocked_id=?) OR (blocker_id=? AND blocked_id=?) LIMIT 1",
        (first_id, second_id, second_id, first_id),
    ).fetchone() is not None


def same_local_area(first: dict, second: dict) -> bool:
    return first["region"] == second["region"] and first["school"] == second["school"]


def get_invitation_for_user(db, invitation_id: int, user_id: int):
    return db.execute(
        """SELECT i.*, s.id AS sender_user_id, s.child_name AS sender_name,
                  r.id AS recipient_user_id, r.child_name AS recipient_name
           FROM invitations i
           JOIN users s ON s.id=i.sender_id
           JOIN users r ON r.id=i.recipient_id
           WHERE i.id=? AND (i.sender_id=? OR i.recipient_id=?)""",
        (invitation_id, user_id, user_id),
    ).fetchone()


def format_time(timestamp: int) -> str:
    from datetime import datetime
    return datetime.fromtimestamp(timestamp, ZoneInfo("Europe/Tallinn")).strftime("%d.%m.%Y %H:%M")


app.jinja_env.filters["datetime"] = format_time


@app.route("/")
def index():
    if g.user:
        return redirect(url_for("dashboard"))
    return render_template("index.html", schools=SCHOOLS)


@app.route("/register", methods=["GET", "POST"])
def register():
    form_data = request.form if request.method == "POST" else {}
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        child_name = request.form.get("child_name", "").strip()
        guardian_email = request.form.get("guardian_email", "").strip().lower()
        password = request.form.get("password", "")
        school_choice = request.form.get("school", "")
        school = request.form.get("other_school", "").strip() if school_choice == "__other__" else school_choice
        region = request.form.get("region", "")
        area = request.form.get("area", "")
        mode = request.form.get("mode", "")
        username_ok = bool(re.fullmatch(r"[A-Za-z0-9._-]{3,24}", username))
        email_ok = bool(re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", guardian_email))
        errors = []
        if not username_ok:
            errors.append("Kasutajanimi peab olema 3–24 märki ja sisaldama ainult tähti, numbreid, punkti, alakriipsu või sidekriipsu.")
        if not child_name or len(child_name) > 40:
            errors.append("Sisesta lapse eesnimi (kuni 40 märki).")
        if not email_ok:
            errors.append("Sisesta korrektne lapsevanema või eestkostja e-posti aadress.")
        if len(password) < 10:
            errors.append("Salasõna peab olema vähemalt 10 märki pikk.")
        if school_choice == "__other__":
            if not school or len(school) > 100:
                errors.append("Sisesta kooli nimi (kuni 100 märki).")
        elif school not in SCHOOLS:
            errors.append("Vali kool nimekirjast.")
        if region not in REGIONS or area not in REGIONS.get(region, []):
            errors.append("Vali piirkond ja sellele vastav asum või asula.")
        if mode not in MODES:
            errors.append("Vali kooli liikumise viis.")
        if request.form.get("guardian_ack") != "yes":
            errors.append("Kinnita, et lapsevanem või eestkostja on konto loomisest teadlik.")
        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("register.html", schools=SCHOOLS, regions=REGIONS, form_data=form_data)
        db = get_db()
        try:
            cursor = db.execute(
                """INSERT INTO users(username, child_name, guardian_email, password_hash, school,
                   region, area, mode, active, created_at) VALUES(?,?,?,?,?,?,?,?,0,?)""",
                (username, child_name, guardian_email, generate_password_hash(password), school,
                 region, area, mode, now_ts()),
            )
            user_id = cursor.lastrowid
            raw_token = new_token(db, user_id, "parent_consent")
            db.commit()
        except sqlite3.IntegrityError:
            db.rollback()
            flash("See kasutajanimi on juba kasutusel. Vali teine kasutajanimi.", "error")
            return render_template("register.html", schools=SCHOOLS, regions=REGIONS, form_data=form_data)

        confirm_url = f"{BASE_URL}{url_for('confirm_parent', token=raw_token)}"
        sent = send_email(
            guardian_email,
            "Koolitee kaaslane – kinnita lapse konto",
            f"Tere!\n\nSelle e-posti aadressiga sooviti luua Koolitee kaaslase konto lapsele {child_name}.\n\n"
            "Konto aktiveerimiseks ja lapsevanema/eestkostja nõusoleku kinnitamiseks ava see link:\n"
            f"{confirm_url}\n\n"
            "Link kehtib 24 tundi. Kui sa ei ole seda kontot taotlenud, võid selle kirja tähelepanuta jätta.\n\n"
            "Koolitee kaaslane",
        )
        if sent:
            flash("Konto on loodud ootel olekus. Saatsime lapsevanema e-postile kinnituskirja. Ava kiri ja kinnita konto.", "success")
            return redirect(url_for("index"))
        flash("Konto jäi ootele, sest e-kirja saatmine ebaõnnestus. Kontrolli serveri SMTP-seadistust ja proovi uuesti.", "error")
        return redirect(url_for("index"))
    return render_template("register.html", schools=SCHOOLS, regions=REGIONS, form_data=form_data)


@app.route("/confirm/<token>", methods=["GET", "POST"])
def confirm_parent(token: str):
    db = get_db()
    token_row = db.execute(
        """SELECT t.*, u.child_name FROM tokens t JOIN users u ON u.id=t.user_id
           WHERE t.token_hash=? AND t.purpose='parent_consent' AND t.expires_at>?""",
        (token_digest(token), now_ts()),
    ).fetchone()
    if not token_row:
        return render_template("message.html", title="Kinnituslink ei kehti", message="Kinnituslink on aegunud või juba kasutatud. Võta ühendust keskkonna haldajaga või loo konto uuesti."), 400
    if request.method == "POST":
        db.execute("UPDATE users SET active=1, parent_consent_at=? WHERE id=?", (now_ts(), token_row["user_id"]))
        db.execute("DELETE FROM tokens WHERE id=?", (token_row["id"],))
        db.commit()
        user = db.execute("SELECT * FROM users WHERE id=?", (token_row["user_id"],)).fetchone()
        send_guardian_notice(user, "Koolitee kaaslase konto on kinnitatud", f"Lapse {user['child_name']} konto on aktiveeritud. Lapsevanema/eestkostja kinnitus on salvestatud.\n\nKoolitee kaaslane")
        return render_template("message.html", title="Konto on kinnitatud!", message=f"Aitäh. {token_row['child_name']} konto on nüüd aktiivne. Laps saab sisse logida valitud kasutajanime ja salasõnaga.", success=True)
    return render_template("confirm.html", child_name=token_row["child_name"])


@app.route("/resend-confirmation", methods=["POST"])
def resend_confirmation():
    username = request.form.get("username", "").strip()
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE username=? COLLATE NOCASE AND active=0", (username,)).fetchone()
    if user:
        db.execute("DELETE FROM tokens WHERE user_id=? AND purpose='parent_consent'", (user["id"],))
        raw_token = new_token(db, user["id"], "parent_consent")
        db.commit()
        confirm_url = f"{BASE_URL}{url_for('confirm_parent', token=raw_token)}"
        sent = send_email(
            user["guardian_email"],
            "Koolitee kaaslane – konto kinnitamine uuesti",
            f"Tere!\n\nKonto lapsele {user['child_name']} ootab endiselt lapsevanema/eestkostja kinnitust.\n\n"
            f"Kinnitamiseks ava link: {confirm_url}\n\nLink kehtib 24 tundi.\nKoolitee kaaslane",
        )
        if not sent:
            flash("Kinnituskirja uuesti saatmine ebaõnnestus. Kontrolli e-posti seadistust.", "error")
            return redirect(url_for("index"))
    flash("Kui selle kasutajanime konto ootab veel kinnitamist, saadeti lapsevanema e-postile uus kinnituslink.", "info")
    return redirect(url_for("index"))


@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    ip = request.remote_addr or "unknown"
    db = get_db()
    recent = db.execute("SELECT COUNT(*) AS n FROM login_attempts WHERE ip_address=? AND created_at>?", (ip, now_ts() - 900)).fetchone()["n"]
    if recent >= 10:
        flash("Liiga palju ebaõnnestunud katseid. Proovi 15 minuti pärast uuesti.", "error")
        return redirect(url_for("index"))
    user = db.execute("SELECT * FROM users WHERE username=? COLLATE NOCASE", (username,)).fetchone()
    if not user or not check_password_hash(user["password_hash"], password) or not user["active"]:
        db.execute("INSERT INTO login_attempts(ip_address, created_at) VALUES(?,?)", (ip, now_ts()))
        db.commit()
        flash("Sisselogimine ei õnnestunud. Kontrolli kasutajanime ja salasõna või veendu, et lapsevanem on konto kinnitanud.", "error")
        return redirect(url_for("index"))
    db.execute("DELETE FROM login_attempts WHERE ip_address=?", (ip,))
    db.commit()
    session.clear()
    session["user_id"] = user["id"]
    session.permanent = True
    return redirect(url_for("dashboard"))


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    session.clear()
    flash("Logisid välja.", "info")
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    user = g.user
    peer_rows = db.execute(
        """SELECT u.* FROM users u
           WHERE u.active=1 AND u.id<>? AND u.school=? AND u.region=?
             AND NOT EXISTS (SELECT 1 FROM blocks b WHERE
               (b.blocker_id=u.id AND b.blocked_id=?) OR (b.blocker_id=? AND b.blocked_id=u.id))
           ORDER BY CASE WHEN u.area=? THEN 0 ELSE 1 END, u.child_name COLLATE NOCASE""",
        (user["id"], user["school"], user["region"], user["id"], user["id"], user["area"]),
    ).fetchall()
    peers = []
    for row in peer_rows:
        item = dict(row)
        item["distance_label"] = "Sama asum / asula" if row["area"] == user["area"] else "Sama linnaosa / vald"
        peers.append(item)
    incoming = db.execute(
        """SELECT i.*, u.child_name AS peer_name, u.area AS peer_area, u.region AS peer_region,
                  (SELECT body FROM messages m WHERE m.invitation_id=i.id ORDER BY m.id LIMIT 1) AS intro
           FROM invitations i JOIN users u ON u.id=i.sender_id
           WHERE i.recipient_id=? AND i.status='pending' ORDER BY i.created_at DESC""",
        (user["id"],),
    ).fetchall()
    outgoing = db.execute(
        """SELECT i.*, u.child_name AS peer_name, u.area AS peer_area, u.region AS peer_region
           FROM invitations i JOIN users u ON u.id=i.recipient_id
           WHERE i.sender_id=? AND i.status='pending' ORDER BY i.created_at DESC""",
        (user["id"],),
    ).fetchall()
    conversations = db.execute(
        """SELECT i.*, CASE WHEN i.sender_id=? THEN r.child_name ELSE s.child_name END AS peer_name,
                  (SELECT body FROM messages m WHERE m.invitation_id=i.id ORDER BY m.id DESC LIMIT 1) AS last_message,
                  (SELECT created_at FROM messages m WHERE m.invitation_id=i.id ORDER BY m.id DESC LIMIT 1) AS last_message_at
           FROM invitations i JOIN users s ON s.id=i.sender_id JOIN users r ON r.id=i.recipient_id
           WHERE (i.sender_id=? OR i.recipient_id=?) AND i.status='accepted'
             AND NOT EXISTS (SELECT 1 FROM blocks b WHERE
               (b.blocker_id=i.sender_id AND b.blocked_id=i.recipient_id) OR (b.blocker_id=i.recipient_id AND b.blocked_id=i.sender_id))
           ORDER BY COALESCE(last_message_at, i.updated_at) DESC""",
        (user["id"], user["id"], user["id"]),
    ).fetchall()
    return render_template("dashboard.html", user=user, peers=peers, incoming=incoming, outgoing=outgoing, conversations=conversations)


@app.route("/invite/<int:peer_id>", methods=["POST"])
@login_required
def send_invitation(peer_id: int):
    db = get_db()
    peer = db.execute("SELECT * FROM users WHERE id=? AND active=1", (peer_id,)).fetchone()
    if not peer or peer["id"] == g.user["id"] or peer["school"] != g.user["school"] or peer["region"] != g.user["region"]:
        abort(404)
    if is_blocked(db, g.user["id"], peer_id):
        flash("Selle kasutajaga ei saa ühendust võtta.", "error")
        return redirect(url_for("dashboard"))
    existing = db.execute(
        """SELECT id, status FROM invitations WHERE
           (sender_id=? AND recipient_id=?) OR (sender_id=? AND recipient_id=?)
           ORDER BY id DESC LIMIT 1""",
        (g.user["id"], peer_id, peer_id, g.user["id"]),
    ).fetchone()
    if existing and existing["status"] in ("pending", "accepted"):
        flash("Selle koolikaaslasega on juba kutse või vestlus olemas.", "info")
        return redirect(url_for("dashboard"))
    intro = request.form.get("intro", "").strip()
    if not intro:
        intro = "Tere! Kas soovid arutada, kas saaksime vahel koos kooli minna?"
    if len(intro) > 400:
        flash("Kutse sõnum võib olla kuni 400 märki.", "error")
        return redirect(url_for("dashboard"))
    stamp = now_ts()
    cursor = db.execute(
        "INSERT INTO invitations(sender_id, recipient_id, status, created_at, updated_at) VALUES(?,?, 'pending', ?,?)",
        (g.user["id"], peer_id, stamp, stamp),
    )
    invitation_id = cursor.lastrowid
    db.execute("INSERT INTO messages(invitation_id, sender_id, body, created_at) VALUES(?,?,?,?)", (invitation_id, g.user["id"], intro, stamp))
    db.commit()
    sent = send_guardian_notice(
        peer,
        "Koolitee kaaslane – uus koolitee kutse",
        f"Tere!\n\n{g.user['child_name']} samast koolist soovib saata koolitee kokkuleppe kutse.\n"
        "Lapsevanem saab lapsega koos vaadata kutset Koolitee kaaslase keskkonnas.\n\n"
        f"Ava keskkond: {BASE_URL}\n\nTeise lapse e-posti aadressi ei avaldata.\nKoolitee kaaslane",
    )
    flash("Kutse saadetud. Teise lapse lapsevanemale saadeti e-kiri." if sent else "Kutse salvestati, kuid teavituse e-kiri ei läinud välja. Kontrolli e-posti seadistust.", "success" if sent else "error")
    return redirect(url_for("dashboard"))


@app.route("/invite/<int:invitation_id>/respond", methods=["POST"])
@login_required
def respond_invitation(invitation_id: int):
    db = get_db()
    invitation = get_invitation_for_user(db, invitation_id, g.user["id"])
    if not invitation or invitation["recipient_user_id"] != g.user["id"] or invitation["status"] != "pending":
        abort(404)
    action = request.form.get("action")
    if action not in ("accept", "decline"):
        abort(400)
    status = "accepted" if action == "accept" else "declined"
    db.execute("UPDATE invitations SET status=?, updated_at=? WHERE id=?", (status, now_ts(), invitation_id))
    db.commit()
    if status == "accepted":
        sender = db.execute("SELECT * FROM users WHERE id=?", (invitation["sender_user_id"],)).fetchone()
        send_guardian_notice(
            sender,
            "Koolitee kaaslane – kutse võeti vastu",
            f"Tere!\n\n{g.user['child_name']} võttis vastu {invitation['sender_name']} saadetud koolitee kutse.\n"
            f"Nad saavad nüüd keskkonnas omavahel sõnumeid vahetada.\n\nAva keskkond: {BASE_URL}\nKoolitee kaaslane",
        )
        flash("Kutse vastu võetud. Nüüd saate vestluses koolitee kokku leppida.", "success")
        return redirect(url_for("conversation", invitation_id=invitation_id))
    flash("Kutse lükati tagasi. Teisele kasutajale sinu kontaktandmeid ei avaldata.", "info")
    return redirect(url_for("dashboard"))


@app.route("/conversation/<int:invitation_id>")
@login_required
def conversation(invitation_id: int):
    db = get_db()
    invitation = get_invitation_for_user(db, invitation_id, g.user["id"])
    if not invitation or invitation["status"] != "accepted":
        abort(404)
    other_id = invitation["recipient_user_id"] if invitation["sender_user_id"] == g.user["id"] else invitation["sender_user_id"]
    if is_blocked(db, g.user["id"], other_id):
        abort(403)
    peer = db.execute("SELECT * FROM users WHERE id=?", (other_id,)).fetchone()
    messages = db.execute(
        "SELECT m.*, u.child_name AS sender_name FROM messages m JOIN users u ON u.id=m.sender_id WHERE m.invitation_id=? ORDER BY m.created_at, m.id",
        (invitation_id,),
    ).fetchall()
    return render_template("conversation.html", invitation=invitation, peer=peer, messages=messages)


CONTACT_PATTERN = re.compile(r"(?:[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})|(?:https?://|www\.)|(?:\+?\d[\d\s()\-]{6,}\d)", re.I)


@app.route("/conversation/<int:invitation_id>/message", methods=["POST"])
@login_required
def send_message(invitation_id: int):
    db = get_db()
    invitation = get_invitation_for_user(db, invitation_id, g.user["id"])
    if not invitation or invitation["status"] != "accepted":
        abort(404)
    other_id = invitation["recipient_user_id"] if invitation["sender_user_id"] == g.user["id"] else invitation["sender_user_id"]
    if is_blocked(db, g.user["id"], other_id):
        abort(403)
    body = request.form.get("body", "").strip()
    if not body or len(body) > 1000:
        flash("Sõnum peab olema 1–1000 märki pikk.", "error")
        return redirect(url_for("conversation", invitation_id=invitation_id))
    if CONTACT_PATTERN.search(body):
        flash("Turvalisuse huvides ei saa saata telefoninumbrit, e-posti aadressi ega veebiaadressi. Kasutage keskkonna vestlust.", "error")
        return redirect(url_for("conversation", invitation_id=invitation_id))
    stamp = now_ts()
    db.execute("INSERT INTO messages(invitation_id, sender_id, body, created_at) VALUES(?,?,?,?)", (invitation_id, g.user["id"], body, stamp))
    db.execute("UPDATE invitations SET updated_at=? WHERE id=?", (stamp, invitation_id))
    db.commit()
    recipient = db.execute("SELECT * FROM users WHERE id=?", (other_id,)).fetchone()
    sent = send_guardian_notice(
        recipient,
        "Koolitee kaaslane – uus sõnum",
        f"Tere!\n\n{g.user['child_name']} saatis sinu lapsele Koolitee kaaslase keskkonnas uue sõnumi.\n"
        "Sõnumi sisu e-kirjas ei kuvata. Logi koos lapsega keskkonda, et seda vaadata.\n\n"
        f"Ava keskkond: {BASE_URL}\nKoolitee kaaslane",
    )
    if not sent:
        flash("Sõnum saadeti, kuid e-posti teavituse saatmine ebaõnnestus.", "error")
    return redirect(url_for("conversation", invitation_id=invitation_id))


@app.route("/block/<int:peer_id>", methods=["POST"])
@login_required
def block_user(peer_id: int):
    if peer_id == g.user["id"]:
        abort(400)
    db = get_db()
    peer = db.execute("SELECT id FROM users WHERE id=?", (peer_id,)).fetchone()
    if not peer:
        abort(404)
    db.execute("INSERT OR IGNORE INTO blocks(blocker_id, blocked_id, created_at) VALUES(?,?,?)", (g.user["id"], peer_id, now_ts()))
    db.execute(
        """UPDATE invitations SET status='closed', updated_at=? WHERE
           ((sender_id=? AND recipient_id=?) OR (sender_id=? AND recipient_id=?))
           AND status IN ('pending','accepted')""",
        (now_ts(), g.user["id"], peer_id, peer_id, g.user["id"]),
    )
    db.commit()
    flash("Kasutaja on blokeeritud ja teie vestlused suletud.", "success")
    return redirect(url_for("dashboard"))


@app.route("/report/<int:peer_id>", methods=["POST"])
@login_required
def report_user(peer_id: int):
    if peer_id == g.user["id"]:
        abort(400)
    reason = request.form.get("reason", "").strip()
    if len(reason) < 5 or len(reason) > 600:
        flash("Kirjelda probleemi vähemalt 5 ja kuni 600 märgiga.", "error")
        return redirect(url_for("dashboard"))
    db = get_db()
    peer = db.execute("SELECT id FROM users WHERE id=?", (peer_id,)).fetchone()
    if not peer:
        abort(404)
    invitation_id = request.form.get("invitation_id", type=int)
    db.execute(
        "INSERT INTO reports(reporter_id, reported_user_id, invitation_id, reason, created_at) VALUES(?,?,?,?,?)",
        (g.user["id"], peer_id, invitation_id, reason, now_ts()),
    )
    db.commit()
    moderator = os.getenv("MODERATION_EMAIL")
    if moderator:
        reporter = db.execute("SELECT child_name FROM users WHERE id=?", (g.user["id"],)).fetchone()
        reported = db.execute("SELECT child_name FROM users WHERE id=?", (peer_id,)).fetchone()
        send_email(moderator, "Koolitee kaaslane – kasutajateade",
                   f"Teate esitaja: {reporter['child_name']} (konto #{g.user['id']})\n"
                   f"Teate sihtmärk: {reported['child_name']} (konto #{peer_id})\n\nPõhjus:\n{reason}\n")
    flash("Teade on salvestatud. Keskkonna haldaja peab selle üle vaatama.", "success")
    return redirect(url_for("dashboard"))


@app.route("/account/delete", methods=["POST"])
@login_required
def delete_account():
    db = get_db()
    user_id = g.user["id"]
    db.execute("DELETE FROM users WHERE id=?", (user_id,))
    db.commit()
    session.clear()
    flash("Konto ja sellega seotud andmed on kustutatud.", "success")
    return redirect(url_for("index"))


@app.errorhandler(400)
def bad_request(error):
    return render_template("message.html", title="Päringut ei saanud töödelda", message=getattr(error, "description", "Kontrolli vormi ja proovi uuesti.")), 400


@app.errorhandler(403)
def forbidden(_error):
    return render_template("message.html", title="Ligipääs puudub", message="Sul ei ole õigust seda lehte või vestlust vaadata."), 403


@app.errorhandler(404)
def not_found(_error):
    return render_template("message.html", title="Lehte ei leitud", message="Soovitud leht või kutse ei ole saadaval."), 404


@app.errorhandler(413)
def too_large(_error):
    return render_template("message.html", title="Vorm on liiga suur", message="Palun lühenda sisestatud teksti ja proovi uuesti."), 413


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")), debug=(APP_ENV == "development"))
