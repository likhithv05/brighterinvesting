"""
Database Utilities
Schema management, authentication, data persistence, duplicate detection,
and session management for the Form 990 Financial Analyzer.

Developed by Epic Intentions for Brighter Investing
Georgia Institute of Technology — Spring 2026
"""

import re
import sqlite3
import json
import hashlib
import secrets
import time

import bcrypt


# ──────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────

DB_PATH = "auth.db"

# Backward-compat alias used by legacy callers
DB_NAME = DB_PATH

SECURITY_QUESTIONS = [
    "What is your mother's maiden name?",
    "What was the name of your first pet?",
    "What city were you born in?",
    "What was the name of your elementary school?",
    "What is your favorite book?",
    "What was the make of your first car?",
]

_USERNAME_RE = re.compile(r"^[a-z0-9_]{3,30}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_LOCK_DURATION = 15 * 60  # 15 minutes in seconds
_MAX_FAILED_ATTEMPTS = 5


# ──────────────────────────────────────────────
# Internal Helpers
# ──────────────────────────────────────────────

def _connect():
    """Return a connection with foreign keys enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def _add_column_if_missing(cursor, table, column, col_type):
    """Safely add a column to an existing table.

    Note: table/column names use string formatting because SQLite
    does not support parameterized DDL. These values are hardcoded
    constants, never user input.
    """
    cursor.execute(f"PRAGMA table_info({table})")
    existing = [row[1] for row in cursor.fetchall()]
    if column not in existing:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


def _validate_username(username):
    """Validate username format. Returns error string or None."""
    if not username:
        return "Username is required."
    if not _USERNAME_RE.match(username):
        return ("Username must be 3-30 characters, "
                "lowercase letters, numbers, and underscores only.")
    return None


def _validate_password(password):
    """Validate password strength. Returns error string or None."""
    if not password or len(password) < 8:
        return "Password must be at least 8 characters."
    if not any(c.isupper() for c in password):
        return "Password must contain at least one uppercase letter."
    if not any(c.isdigit() for c in password):
        return "Password must contain at least one number."
    return None


def _validate_email(email):
    """Validate email format if provided. Returns error string or None."""
    if email and not _EMAIL_RE.match(email):
        return "Invalid email format."
    return None


def _hash(value):
    """Hash a string with bcrypt."""
    return bcrypt.hashpw(value.encode("utf-8"), bcrypt.gensalt())


def _verify(value, hashed):
    """Verify a string against a bcrypt hash."""
    try:
        return bcrypt.checkpw(value.encode("utf-8"), hashed)
    except Exception:
        return False


def _user_dict(row):
    """Convert a sqlite3.Row to a plain dict for a user record."""
    if row is None:
        return None
    return {
        "id": row["id"],
        "username": row["username"],
        "display_name": row["display_name"],
        "email": row["email"],
        "role": row["role"],
        "is_active": row["is_active"],
        "created_at": row["created_at"],
        "last_login": row["last_login"],
        "failed_attempts": row["failed_attempts"],
        "locked_until": row["locked_until"],
    }


# ──────────────────────────────────────────────
# Schema Initialization
# ──────────────────────────────────────────────

def init_db():
    """Create all tables if they don't exist and run migrations.

    Raises sqlite3.DatabaseError if the database file is corrupted
    (caller should catch and show a friendly message).
    """
    with _connect() as conn:
        c = conn.cursor()

        # ── Users ──
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                display_name TEXT NOT NULL DEFAULT '',
                email TEXT,
                password_hash BLOB NOT NULL,
                role TEXT DEFAULT 'user',
                is_active INTEGER DEFAULT 1,
                created_at INTEGER NOT NULL DEFAULT 0,
                last_login INTEGER,
                failed_attempts INTEGER DEFAULT 0,
                locked_until INTEGER DEFAULT 0
            )
        """)
        # Migration: add columns that may be missing from old schema
        _add_column_if_missing(c, "users", "display_name", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(c, "users", "email", "TEXT")
        _add_column_if_missing(c, "users", "failed_attempts", "INTEGER DEFAULT 0")
        _add_column_if_missing(c, "users", "locked_until", "INTEGER DEFAULT 0")
        _add_column_if_missing(c, "users", "is_active", "INTEGER DEFAULT 1")
        _add_column_if_missing(c, "users", "created_at", "INTEGER NOT NULL DEFAULT 0")
        _add_column_if_missing(c, "users", "last_login", "INTEGER")

        # Backfill display_name from username for existing rows
        c.execute("""
            UPDATE users SET display_name = username
            WHERE display_name = '' OR display_name IS NULL
        """)

        # ── Security Questions (new schema: one row per question) ──
        # Check if old schema exists (has question_1 column)
        c.execute("PRAGMA table_info(security_questions)")
        sq_cols = [row[1] for row in c.fetchall()]
        if "question_1" in sq_cols:
            # Old schema — drop and recreate
            c.execute("DROP TABLE security_questions")

        c.execute("""
            CREATE TABLE IF NOT EXISTS security_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                question TEXT NOT NULL,
                answer_hash BLOB NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # ── Session Tokens ──
        c.execute("""
            CREATE TABLE IF NOT EXISTS session_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token TEXT UNIQUE NOT NULL,
                created_at INTEGER NOT NULL DEFAULT 0,
                expires_at INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        _add_column_if_missing(c, "session_tokens", "created_at",
                               "INTEGER NOT NULL DEFAULT 0")

        # ── Organization Persistence (unchanged) ──
        c.execute("""
            CREATE TABLE IF NOT EXISTS user_organizations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                ein TEXT NOT NULL,
                organization_name TEXT NOT NULL,
                tax_years TEXT DEFAULT '[]',
                parsed_data_json TEXT DEFAULT '[]',
                data_hash TEXT DEFAULT '',
                upload_timestamp INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                UNIQUE (user_id, ein),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # ── Tags (unchanged) ──
        c.execute("""
            CREATE TABLE IF NOT EXISTS org_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                tag_name TEXT NOT NULL,
                tag_color TEXT DEFAULT '#0D9488',
                created_at INTEGER DEFAULT 0,
                UNIQUE (user_id, tag_name),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS org_tag_map (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                ein TEXT NOT NULL,
                tag_id INTEGER NOT NULL,
                UNIQUE (user_id, ein, tag_id),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES org_tags(id) ON DELETE CASCADE
            )
        """)

        # ── Admin Audit Log ──
        c.execute("""
            CREATE TABLE IF NOT EXISTS admin_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                target_user_id INTEGER,
                details TEXT,
                timestamp INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (admin_user_id) REFERENCES users(id)
            )
        """)

        # ── Seed admin if no admins exist ──
        c.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
        if c.fetchone()[0] == 0:
            c.execute("SELECT id FROM users ORDER BY id ASC LIMIT 1")
            first = c.fetchone()
            if first:
                c.execute("UPDATE users SET role = 'admin' WHERE id = ?",
                          (first[0],))

        conn.commit()


# Backward-compat alias
init_extended_db = init_db


# ──────────────────────────────────────────────
# User CRUD
# ──────────────────────────────────────────────

def create_user(username, display_name, password, email=None, role="user"):
    """Create a new user account.

    Returns {'success': True, 'user_id': id}
    or      {'success': False, 'error': 'message'}
    """
    # Guard against None inputs
    if not username or not display_name or not password:
        return {"success": False, "error": "Username, display name, and password are required."}

    # Normalize
    username = username.strip().lower()
    display_name = display_name.strip()

    # Validate
    err = _validate_username(username)
    if err:
        return {"success": False, "error": err}
    if not display_name or len(display_name) > 50:
        return {"success": False, "error": "Display name must be 1-50 characters."}
    err = _validate_password(password)
    if err:
        return {"success": False, "error": err}
    err = _validate_email(email)
    if err:
        return {"success": False, "error": err}
    if role not in ("admin", "user"):
        return {"success": False, "error": "Role must be 'admin' or 'user'."}

    pw_hash = _hash(password)
    now = int(time.time())

    try:
        with _connect() as conn:
            c = conn.cursor()

            # First user becomes admin
            c.execute("SELECT COUNT(*) FROM users")
            if c.fetchone()[0] == 0:
                role = "admin"

            c.execute("""
                INSERT INTO users
                (username, display_name, email, password_hash, role, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (username, display_name, email, pw_hash, role, now))
            conn.commit()
            return {"success": True, "user_id": c.lastrowid}
    except sqlite3.IntegrityError:
        return {"success": False, "error": "Username already exists."}
    except Exception as e:
        return {"success": False, "error": f"Database error: {e}"}


def get_user_by_id(user_id):
    """Return a user dict by ID, or None."""
    with _connect() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        return _user_dict(c.fetchone())


def get_user_by_username(username):
    """Return a user dict by username (case-insensitive), or None."""
    with _connect() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ?",
                  (username.strip().lower(),))
        return _user_dict(c.fetchone())


def get_all_users():
    """Return a list of user dicts for the admin panel."""
    with _connect() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT id, username, display_name, email, role,
                   is_active, created_at, last_login,
                   failed_attempts, locked_until
            FROM users ORDER BY id
        """)
        return [_user_dict(r) for r in c.fetchall()]


def update_user(user_id, **kwargs):
    """Update user fields. Supported: display_name, email, role, is_active.

    Returns True on success, False on failure.
    """
    allowed = {"display_name", "email", "role", "is_active"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return False

    if "role" in updates and updates["role"] not in ("admin", "user"):
        return False
    if "email" in updates and updates["email"]:
        if _validate_email(updates["email"]):
            return False
    if "display_name" in updates:
        dn = updates["display_name"]
        if not dn or len(dn) > 50:
            return False

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [user_id]

    try:
        with _connect() as conn:
            conn.execute(
                f"UPDATE users SET {set_clause} WHERE id = ?", values
            )
            conn.commit()
            return True
    except Exception:
        return False


def delete_user(user_id):
    """Delete a user and all related data. Returns True on success."""
    try:
        with _connect() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM org_tag_map WHERE user_id = ?", (user_id,))
            c.execute("DELETE FROM org_tags WHERE user_id = ?", (user_id,))
            c.execute("DELETE FROM security_questions WHERE user_id = ?",
                      (user_id,))
            c.execute("DELETE FROM user_organizations WHERE user_id = ?",
                      (user_id,))
            c.execute("DELETE FROM session_tokens WHERE user_id = ?",
                      (user_id,))
            c.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
            return True
    except Exception:
        return False


def unlock_user(user_id):
    """Reset failed attempts and lock status. Returns True on success."""
    try:
        with _connect() as conn:
            conn.execute("""
                UPDATE users SET failed_attempts = 0, locked_until = 0
                WHERE id = ?
            """, (user_id,))
            conn.commit()
            return True
    except Exception:
        return False


# ──────────────────────────────────────────────
# Authentication
# ──────────────────────────────────────────────

def authenticate(username, password):
    """Authenticate a user by username and password.

    Returns:
        {'success': True, 'user': {id, username, display_name, role}}
    or  {'success': False, 'error': 'message'}
    """
    if not username or not password:
        return {"success": False, "error": "Username and password are required."}
    username = username.strip().lower()
    now = int(time.time())

    with _connect() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = c.fetchone()

        if row is None:
            return {"success": False, "error": "Invalid username or password."}

        user = _user_dict(row)

        # Check active
        if not user["is_active"]:
            return {"success": False, "error": "Account is deactivated."}

        # Check lock
        if user["locked_until"] and user["locked_until"] > now:
            remaining = (user["locked_until"] - now + 59) // 60  # ceil minutes
            return {
                "success": False,
                "error": f"Account locked. Try again in {remaining} minute{'s' if remaining != 1 else ''}.",
            }

        # Verify password
        if not _verify(password, row["password_hash"]):
            # Increment failed attempts
            new_attempts = user["failed_attempts"] + 1
            lock_time = 0
            if new_attempts >= _MAX_FAILED_ATTEMPTS:
                lock_time = now + _LOCK_DURATION
            conn.execute("""
                UPDATE users SET failed_attempts = ?, locked_until = ?
                WHERE id = ?
            """, (new_attempts, lock_time, user["id"]))
            conn.commit()
            return {"success": False, "error": "Invalid username or password."}

        # Success — reset counters and update last_login
        conn.execute("""
            UPDATE users SET failed_attempts = 0, locked_until = 0,
                             last_login = ?
            WHERE id = ?
        """, (now, user["id"]))
        conn.commit()

        # Housekeeping: clean up expired tokens on successful login
        cleanup_expired_tokens()

        return {
            "success": True,
            "user": {
                "id": user["id"],
                "username": user["username"],
                "display_name": user["display_name"],
                "role": user["role"],
            },
        }


# ──────────────────────────────────────────────
# Security Questions
# ──────────────────────────────────────────────

def save_security_questions(user_id, questions_and_answers):
    """Save security questions and hashed answers for a user.

    Args:
        user_id: integer user ID
        questions_and_answers: list of (question_text, answer_text) tuples

    Returns True on success, False on failure.
    """
    if not questions_and_answers:
        return False

    try:
        with _connect() as conn:
            c = conn.cursor()
            # Remove existing questions
            c.execute("DELETE FROM security_questions WHERE user_id = ?",
                      (user_id,))
            for question, answer in questions_and_answers:
                normalized = answer.strip().lower()
                if not normalized:
                    return False
                c.execute("""
                    INSERT INTO security_questions (user_id, question, answer_hash)
                    VALUES (?, ?, ?)
                """, (user_id, question.strip(), _hash(normalized)))
            conn.commit()
            return True
    except Exception:
        return False


def get_security_questions(user_id):
    """Return list of question strings for a user, or empty list."""
    with _connect() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT question FROM security_questions
            WHERE user_id = ? ORDER BY id
        """, (user_id,))
        return [row["question"] for row in c.fetchall()]


def verify_security_answers(user_id, answers):
    """Verify security answers for a user.

    Args:
        user_id: integer user ID
        answers: list of answer strings (same order as get_security_questions)

    Returns True only if ALL answers match.
    """
    with _connect() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT answer_hash FROM security_questions
            WHERE user_id = ? ORDER BY id
        """, (user_id,))
        hashes = [row["answer_hash"] for row in c.fetchall()]

    if not hashes or len(hashes) != len(answers):
        return False

    return all(
        _verify(a.strip().lower(), h)
        for a, h in zip(answers, hashes)
    )


# ──────────────────────────────────────────────
# Password Reset
# ──────────────────────────────────────────────

def reset_password(user_id, new_password):
    """Set a new password for a user.

    Returns {'success': True} or {'success': False, 'error': 'message'}
    """
    err = _validate_password(new_password)
    if err:
        return {"success": False, "error": err}

    try:
        with _connect() as conn:
            conn.execute("""
                UPDATE users SET password_hash = ?,
                                 failed_attempts = 0, locked_until = 0
                WHERE id = ?
            """, (_hash(new_password), user_id))
            conn.commit()
            return {"success": True}
    except Exception as e:
        return {"success": False, "error": f"Database error: {e}"}


def change_password(user_id, current_password, new_password):
    """Change password after verifying the current one.

    Returns {'success': True} or {'success': False, 'error': '...'}
    """
    with _connect() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = c.fetchone()

    if row is None:
        return {"success": False, "error": "User not found."}

    if not _verify(current_password, row["password_hash"]):
        return {"success": False, "error": "Current password is incorrect."}

    err = _validate_password(new_password)
    if err:
        return {"success": False, "error": err}

    try:
        with _connect() as conn:
            conn.execute("""
                UPDATE users SET password_hash = ?,
                                 failed_attempts = 0, locked_until = 0
                WHERE id = ?
            """, (_hash(new_password), user_id))
            conn.commit()
            return {"success": True}
    except Exception as e:
        return {"success": False, "error": f"Database error: {e}"}


def admin_reset_password(user_id):
    """Generate a temporary password for admin reset. Returns the temp pw."""
    temp_pw = secrets.token_urlsafe(10)
    # Temp passwords bypass normal strength validation
    try:
        with _connect() as conn:
            conn.execute("""
                UPDATE users SET password_hash = ?,
                                 failed_attempts = 0, locked_until = 0
                WHERE id = ?
            """, (_hash(temp_pw), user_id))
            conn.commit()
            return temp_pw
    except Exception:
        return None


# ──────────────────────────────────────────────
# Session Tokens
# ──────────────────────────────────────────────

def create_session_token(user_id, days_valid=30):
    """Generate and store a session token. Returns the token string."""
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    expires = now + (days_valid * 24 * 3600)

    try:
        with _connect() as conn:
            c = conn.cursor()
            # Remove old tokens for this user
            c.execute("DELETE FROM session_tokens WHERE user_id = ?",
                      (user_id,))
            c.execute("""
                INSERT INTO session_tokens (user_id, token, created_at, expires_at)
                VALUES (?, ?, ?, ?)
            """, (user_id, token, now, expires))
            conn.commit()
            return token
    except Exception:
        return None


def validate_session_token(token):
    """Validate a session token.

    Returns user dict {id, username, display_name, role} if valid, None if not.
    """
    now = int(time.time())
    with _connect() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT u.id, u.username, u.display_name, u.role
            FROM session_tokens st
            JOIN users u ON u.id = st.user_id
            WHERE st.token = ? AND st.expires_at > ? AND u.is_active = 1
        """, (token, now))
        row = c.fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "username": row["username"],
            "display_name": row["display_name"],
            "role": row["role"],
        }


def delete_session_token(token):
    """Remove a specific session token."""
    try:
        with _connect() as conn:
            conn.execute("DELETE FROM session_tokens WHERE token = ?",
                         (token,))
            conn.commit()
    except Exception:
        pass


def clear_user_sessions(user_id):
    """Remove all session tokens for a user."""
    try:
        with _connect() as conn:
            conn.execute("DELETE FROM session_tokens WHERE user_id = ?",
                         (user_id,))
            conn.commit()
    except Exception:
        pass


# Backward-compat aliases for sidebar.py
clear_remember_me_token = clear_user_sessions
create_remember_me_token = create_session_token


def verify_remember_me_token(token):
    """Backward-compat wrapper. Returns (user_id, username, role) or None."""
    result = validate_session_token(token)
    if result is None:
        return None
    return (result["id"], result["username"], result["role"])


def cleanup_expired_tokens():
    """Delete all expired session tokens. Returns count deleted."""
    try:
        with _connect() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM session_tokens WHERE expires_at < ?",
                      (int(time.time()),))
            conn.commit()
            return c.rowcount
    except Exception:
        return 0


# ──────────────────────────────────────────────
# Backward-Compat Helpers (used by login.py)
# ──────────────────────────────────────────────

def get_user_id(username):
    """Return user id for a username, or None."""
    user = get_user_by_username(username)
    return user["id"] if user else None


def update_user_role(user_id, new_role):
    """Update a user's role."""
    update_user(user_id, role=new_role)


def toggle_user_active(user_id):
    """Toggle a user's active status."""
    user = get_user_by_id(user_id)
    if user:
        update_user(user_id, is_active=0 if user["is_active"] else 1)


def update_last_login(user_id):
    """Update last_login timestamp."""
    try:
        with _connect() as conn:
            conn.execute("UPDATE users SET last_login = ? WHERE id = ?",
                         (int(time.time()), user_id))
            conn.commit()
    except Exception:
        pass


def get_security_questions_for_user(username):
    """Backward-compat: return (q1, q2) tuple or None."""
    user = get_user_by_username(username)
    if not user:
        return None
    questions = get_security_questions(user["id"])
    if len(questions) >= 2:
        return (questions[0], questions[1])
    return None


# ──────────────────────────────────────────────
# Admin-Verified Actions (defense in depth)
# ──────────────────────────────────────────────

def _is_admin(user_id):
    """Check if a user has the admin role."""
    user = get_user_by_id(user_id)
    return user is not None and user["role"] == "admin"


def log_admin_action(admin_user_id, action, target_user_id=None, details=None):
    """Write an entry to the admin audit log."""
    try:
        with _connect() as conn:
            conn.execute("""
                INSERT INTO admin_log
                (admin_user_id, action, target_user_id, details, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (admin_user_id, action, target_user_id, details,
                  int(time.time())))
            conn.commit()
    except Exception:
        pass


def get_admin_log(limit=50):
    """Return recent admin log entries as a list of dicts."""
    with _connect() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT al.id, al.action, al.target_user_id, al.details,
                   al.timestamp,
                   au.username AS admin_username,
                   tu.username AS target_username
            FROM admin_log al
            LEFT JOIN users au ON au.id = al.admin_user_id
            LEFT JOIN users tu ON tu.id = al.target_user_id
            ORDER BY al.timestamp DESC
            LIMIT ?
        """, (limit,))
        return [dict(r) for r in c.fetchall()]


def admin_set_role(admin_id, target_id, new_role):
    """Change a user's role. Verifies caller is admin and logs the action."""
    if not _is_admin(admin_id):
        return False
    result = update_user(target_id, role=new_role)
    if result:
        log_admin_action(admin_id, f"set_role:{new_role}", target_id)
    return result


def admin_set_active(admin_id, target_id, active):
    """Set a user's active status. Admin-verified with audit logging."""
    if not _is_admin(admin_id):
        return False
    result = update_user(target_id, is_active=1 if active else 0)
    if result:
        log_admin_action(
            admin_id, "activate" if active else "deactivate", target_id,
        )
    return result


def admin_unlock(admin_id, target_id):
    """Unlock a user account. Admin-verified with audit logging."""
    if not _is_admin(admin_id):
        return False
    result = unlock_user(target_id)
    if result:
        log_admin_action(admin_id, "unlock", target_id)
    return result


def admin_delete(admin_id, target_id):
    """Delete a user. Admin-verified with audit logging."""
    if not _is_admin(admin_id):
        return False
    target = get_user_by_id(target_id)
    target_name = target["username"] if target else "unknown"
    result = delete_user(target_id)
    if result:
        log_admin_action(admin_id, "delete_user", target_id,
                         details=target_name)
    return result


def admin_reset_pw(admin_id, target_id):
    """Reset a user's password to a random 12-char string.

    Admin-verified with audit logging.
    Returns the temporary password, or None on failure.
    """
    if not _is_admin(admin_id):
        return None
    alphabet = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    temp_pw = "".join(secrets.choice(alphabet) for _ in range(12))
    try:
        with _connect() as conn:
            conn.execute("""
                UPDATE users SET password_hash = ?,
                                 failed_attempts = 0, locked_until = 0
                WHERE id = ?
            """, (_hash(temp_pw), target_id))
            conn.commit()
            log_admin_action(admin_id, "reset_password", target_id)
            return temp_pw
    except Exception:
        return None


def admin_create(admin_id, username, display_name, password,
                 email=None, role="user"):
    """Create a user account as admin. Admin-verified with audit logging."""
    if not _is_admin(admin_id):
        return {"success": False, "error": "Unauthorized."}
    result = create_user(username, display_name, password,
                         email=email, role=role)
    if result["success"]:
        log_admin_action(admin_id, f"create_user:{role}",
                         result["user_id"], details=username)
    return result


def admin_delete_organization(admin_id, target_user_id, ein):
    """Delete any user's saved organization. Admin-only with audit logging.

    Returns True on success, False on failure or unauthorized.
    """
    if not _is_admin(admin_id):
        return False
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "DELETE FROM user_organizations WHERE user_id = ? AND ein = ?",
            (target_user_id, ein),
        )
        conn.commit()
        conn.close()
        log_admin_action(admin_id, "delete_organization", target_user_id,
                         details=ein)
        return True
    except Exception:
        return False


# ──────────────────────────────────────────────
# Session Verification
# ──────────────────────────────────────────────

def verify_session(user_id):
    """Verify a logged-in user's session is still valid.

    Checks:
      1. User exists in the database
      2. User's is_active is 1
      3. User is not locked

    Returns:
        {'valid': True, 'user': user_dict}
    or  {'valid': False, 'reason': 'message'}
    """
    if not user_id:
        return {"valid": False, "reason": "No active session."}

    user = get_user_by_id(user_id)

    if user is None:
        return {"valid": False,
                "reason": "Your account no longer exists."}

    if not user["is_active"]:
        return {"valid": False,
                "reason": "Your account has been deactivated. "
                          "Contact an administrator."}

    now = int(time.time())
    if user.get("locked_until") and user["locked_until"] > now:
        return {"valid": False,
                "reason": "Your account has been temporarily locked."}

    return {"valid": True, "user": user}


# ──────────────────────────────────────────────
# System Stats (admin only)
# ──────────────────────────────────────────────

def get_system_stats():
    """Return aggregate stats for the admin sidebar info line.

    Returns dict with 'total_users' and 'total_saved_orgs'.
    """
    try:
        with _connect() as conn:
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM users")
            total_users = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM user_organizations WHERE is_active = 1")
            total_orgs = c.fetchone()[0]
        return {"total_users": total_users, "total_saved_orgs": total_orgs}
    except sqlite3.DatabaseError:
        return {"total_users": 0, "total_saved_orgs": 0}


# ──────────────────────────────────────────────
# Organization Persistence (unchanged)
# ──────────────────────────────────────────────

def save_organization(user_id, parsed_rows):
    """Group parsed rows by EIN and save to database.
    Merges new years with any existing saved data for the same org.
    """
    if not user_id or not parsed_rows:
        return
    groups = {}
    for row in parsed_rows:
        ein = row.get("EIN", "")
        if not ein:
            continue
        if ein not in groups:
            groups[ein] = []
        groups[ein].append(row)

    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        for ein, rows in groups.items():
            org_name = rows[0].get("OrganizationName", "Unknown")
            new_years = sorted(set(r.get("TaxYear", "") for r in rows))
            data_json = json.dumps(rows, default=str)
            data_hash = hashlib.sha256(data_json.encode()).hexdigest()

            c.execute(
                "SELECT id, tax_years, parsed_data_json FROM user_organizations "
                "WHERE user_id = ? AND ein = ?",
                (user_id, ein),
            )
            existing = c.fetchone()
            if existing:
                eid, old_years_json, old_data_json = existing
                old_years = json.loads(old_years_json) if old_years_json else []
                old_data = json.loads(old_data_json) if old_data_json else []
                existing_year_set = {r.get("TaxYear") for r in old_data}
                for r in rows:
                    if r.get("TaxYear") not in existing_year_set:
                        old_data.append(r)
                merged_years = sorted(set(old_years + new_years))
                c.execute("""
                    UPDATE user_organizations
                    SET organization_name = ?, tax_years = ?, parsed_data_json = ?,
                        data_hash = ?, upload_timestamp = ?, is_active = 1
                    WHERE id = ?
                """, (org_name, json.dumps(merged_years),
                      json.dumps(old_data, default=str),
                      data_hash, int(time.time()), eid))
            else:
                c.execute("""
                    INSERT INTO user_organizations
                    (user_id, ein, organization_name, tax_years, parsed_data_json,
                     data_hash, upload_timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (user_id, ein, org_name, json.dumps(new_years),
                      data_json, data_hash, int(time.time())))

        conn.commit()
        conn.close()
    except sqlite3.DatabaseError:
        pass  # Silently fail on save — data is still in memory


def load_user_organizations(user_id):
    """Load all saved organizations for a user.
    Returns dict: { ein: { name, years, parsed_data } }
    """
    if not user_id:
        return {}
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            SELECT ein, organization_name, tax_years, parsed_data_json
            FROM user_organizations
            WHERE user_id = ? AND is_active = 1
            ORDER BY organization_name
        """, (user_id,))
        rows = c.fetchall()
        conn.close()

        orgs = {}
        for ein, name, years_json, data_json in rows:
            orgs[ein] = {
                "name": name,
                "years": json.loads(years_json) if years_json else [],
                "parsed_data": json.loads(data_json) if data_json else [],
            }
        return orgs
    except (sqlite3.DatabaseError, json.JSONDecodeError):
        return {}


def delete_organization(user_id, ein):
    """Delete a saved organization."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "DELETE FROM user_organizations WHERE user_id = ? AND ein = ?",
            (user_id, ein),
        )
        conn.commit()
        conn.close()
    except sqlite3.DatabaseError:
        pass


# ──────────────────────────────────────────────
# Duplicate Detection (unchanged)
# ──────────────────────────────────────────────

def detect_duplicates(parsed_rows):
    """Detect EIN + TaxYear duplicates in a list of parsed rows.

    Returns list of dicts:
      [{ "ein": ..., "year": ..., "indices": [i, j, ...], "files": [...] }]
    """
    seen = {}
    for i, row in enumerate(parsed_rows):
        key = (row.get("EIN", ""), row.get("TaxYear", ""))
        if key[0] == "" and key[1] == "":
            continue
        if key not in seen:
            seen[key] = []
        seen[key].append(i)

    duplicates = []
    for (ein, year), indices in seen.items():
        if len(indices) > 1:
            duplicates.append({
                "ein": ein,
                "year": year,
                "indices": indices,
                "files": [parsed_rows[i].get("SourceFile", "?")
                          for i in indices],
            })
    return duplicates


# ──────────────────────────────────────────────
# Tags / Categories (unchanged)
# ──────────────────────────────────────────────

TAG_COLORS = [
    ("#0D9488", "Teal"),
    ("#0284C7", "Sky"),
    ("#7C3AED", "Purple"),
    ("#D97706", "Amber"),
    ("#E11D48", "Rose"),
    ("#059669", "Emerald"),
    ("#0891B2", "Cyan"),
    ("#DC2626", "Red"),
    ("#4F46E5", "Indigo"),
    ("#CA8A04", "Yellow"),
]


def create_tag(user_id, tag_name, tag_color="#0D9488"):
    """Create a new tag/category for grouping organizations."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO org_tags (user_id, tag_name, tag_color, created_at) "
            "VALUES (?, ?, ?, ?)",
            (user_id, tag_name.strip(), tag_color, int(time.time())),
        )
        conn.commit()
        tag_id = c.lastrowid
        return tag_id
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def get_user_tags(user_id):
    """Return list of tag dicts for a user."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute(
            "SELECT id, tag_name, tag_color FROM org_tags "
            "WHERE user_id = ? ORDER BY tag_name",
            (user_id,),
        )
        tags = [dict(r) for r in c.fetchall()]
        conn.close()
        return tags
    except sqlite3.DatabaseError:
        return []


def delete_tag(user_id, tag_id):
    """Delete a tag and all its org associations."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM org_tag_map WHERE tag_id = ? AND user_id = ?",
                  (tag_id, user_id))
        c.execute("DELETE FROM org_tags WHERE id = ? AND user_id = ?",
                  (tag_id, user_id))
        conn.commit()
        conn.close()
    except sqlite3.DatabaseError:
        pass


def assign_tag(user_id, ein, tag_id):
    """Assign a tag to an organization (by EIN)."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute(
            "INSERT OR IGNORE INTO org_tag_map (user_id, ein, tag_id) "
            "VALUES (?, ?, ?)",
            (user_id, ein, tag_id),
        )
        conn.commit()
    finally:
        conn.close()


def remove_tag_from_org(user_id, ein, tag_id):
    """Remove a tag from an organization."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "DELETE FROM org_tag_map WHERE user_id = ? AND ein = ? AND tag_id = ?",
            (user_id, ein, tag_id),
        )
        conn.commit()
        conn.close()
    except sqlite3.DatabaseError:
        pass


def get_tags_for_org(user_id, ein):
    """Return list of tag dicts assigned to a specific org."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("""
            SELECT t.id, t.tag_name, t.tag_color
            FROM org_tags t
            JOIN org_tag_map m ON m.tag_id = t.id
            WHERE m.user_id = ? AND m.ein = ?
            ORDER BY t.tag_name
        """, (user_id, ein))
        tags = [dict(r) for r in c.fetchall()]
        conn.close()
        return tags
    except sqlite3.DatabaseError:
        return []


def get_orgs_by_tag(user_id, tag_id):
    """Return list of EINs for a given tag."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "SELECT ein FROM org_tag_map WHERE user_id = ? AND tag_id = ?",
            (user_id, tag_id),
        )
        eins = [r[0] for r in c.fetchall()]
        conn.close()
        return eins
    except sqlite3.DatabaseError:
        return []
