"""
Database Utilities
Handles schema extensions, data persistence, duplicate detection,
and session management for the Form 990 Financial Analyzer.

Developed by Epic Intentions for Brighter Investing
Georgia Institute of Technology — Spring 2026
"""

import sqlite3
import json
import hashlib
import secrets
import time
import bcrypt

DB_NAME = "auth.db"

# ──────────────────────────────────────────────
# Preset security questions
# ──────────────────────────────────────────────
SECURITY_QUESTIONS = [
    "What is your mother's maiden name?",
    "What was the name of your first pet?",
    "What city were you born in?",
    "What was the name of your elementary school?",
    "What is your favorite book?",
    "What was the make of your first car?",
]


# ──────────────────────────────────────────────
# Schema Initialization
# ──────────────────────────────────────────────

def init_extended_db():
    """Create all tables needed for the enhanced application."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Original users table (kept for backward compat)
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash BLOB NOT NULL,
            role TEXT DEFAULT 'user'
        )
    """)

    # Add new columns to users if they don't exist
    _add_column_if_missing(c, "users", "last_login", "INTEGER")
    _add_column_if_missing(c, "users", "created_at", "INTEGER DEFAULT 0")
    _add_column_if_missing(c, "users", "is_active", "INTEGER DEFAULT 1")

    # Security questions for password reset
    c.execute("""
        CREATE TABLE IF NOT EXISTS security_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            question_1 TEXT NOT NULL,
            answer_hash_1 BLOB NOT NULL,
            question_2 TEXT NOT NULL,
            answer_hash_2 BLOB NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    # Saved organizations (data persistence)
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

    # Remember-me tokens
    c.execute("""
        CREATE TABLE IF NOT EXISTS session_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            expires_at INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    # Tags / categories for grouping organizations
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

    # Many-to-many: organizations ↔ tags
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

    # Seed admin user if none exists
    c.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
    if c.fetchone()[0] == 0:
        c.execute("SELECT id FROM users ORDER BY id ASC LIMIT 1")
        first = c.fetchone()
        if first:
            c.execute("UPDATE users SET role = 'admin' WHERE id = ?", (first[0],))

    conn.commit()
    conn.close()


def _add_column_if_missing(cursor, table, column, col_type):
    """Safely add a column to an existing table."""
    cursor.execute(f"PRAGMA table_info({table})")
    existing = [row[1] for row in cursor.fetchall()]
    if column not in existing:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


# ──────────────────────────────────────────────
# User Management (Admin)
# ──────────────────────────────────────────────

def get_user_id(username):
    """Return user id for a username, or None."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def get_all_users():
    """Return list of user dicts for admin panel."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT id, username, role, last_login, created_at, is_active
        FROM users ORDER BY id
    """)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def update_user_role(user_id, new_role):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, user_id))
    conn.commit()
    conn.close()


def toggle_user_active(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE users SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


def admin_reset_password(user_id):
    """Generate a temporary password and set it for a user. Returns the temp pw."""
    temp_pw = secrets.token_urlsafe(10)
    hashed = bcrypt.hashpw(temp_pw.encode(), bcrypt.gensalt())
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hashed, user_id))
    conn.commit()
    conn.close()
    return temp_pw


def update_last_login(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE users SET last_login = ? WHERE id = ?", (int(time.time()), user_id))
    conn.commit()
    conn.close()


def delete_user(user_id):
    """Delete a user and all related data."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM security_questions WHERE user_id = ?", (user_id,))
    c.execute("DELETE FROM user_organizations WHERE user_id = ?", (user_id,))
    c.execute("DELETE FROM session_tokens WHERE user_id = ?", (user_id,))
    c.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


# ──────────────────────────────────────────────
# Security Questions & Password Reset
# ──────────────────────────────────────────────

def save_security_questions(user_id, q1, a1, q2, a2):
    """Store hashed security answers for a user."""
    h1 = bcrypt.hashpw(a1.strip().lower().encode(), bcrypt.gensalt())
    h2 = bcrypt.hashpw(a2.strip().lower().encode(), bcrypt.gensalt())
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO security_questions
        (user_id, question_1, answer_hash_1, question_2, answer_hash_2)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, q1, h1, q2, h2))
    conn.commit()
    conn.close()


def get_security_questions_for_user(username):
    """Return (q1, q2) for a user, or None if not set."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        SELECT sq.question_1, sq.question_2
        FROM security_questions sq
        JOIN users u ON u.id = sq.user_id
        WHERE u.username = ?
    """, (username,))
    row = c.fetchone()
    conn.close()
    return row if row else None


def verify_security_answers(username, a1, a2):
    """Verify security answers. Returns True if both match."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        SELECT sq.answer_hash_1, sq.answer_hash_2
        FROM security_questions sq
        JOIN users u ON u.id = sq.user_id
        WHERE u.username = ?
    """, (username,))
    row = c.fetchone()
    conn.close()
    if not row:
        return False
    h1, h2 = row
    return (
        bcrypt.checkpw(a1.strip().lower().encode(), h1)
        and bcrypt.checkpw(a2.strip().lower().encode(), h2)
    )


def reset_password(username, new_password):
    """Set a new password for a user."""
    hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt())
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE users SET password_hash = ? WHERE username = ?", (hashed, username))
    conn.commit()
    conn.close()


# ──────────────────────────────────────────────
# Remember Me Tokens
# ──────────────────────────────────────────────

def create_remember_me_token(user_id):
    """Generate and store a 30-day remember-me token."""
    token = secrets.token_urlsafe(32)
    expires = int(time.time()) + (30 * 24 * 3600)
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Clean old tokens for this user
    c.execute("DELETE FROM session_tokens WHERE user_id = ?", (user_id,))
    c.execute(
        "INSERT INTO session_tokens (user_id, token, expires_at) VALUES (?, ?, ?)",
        (user_id, token, expires),
    )
    conn.commit()
    conn.close()
    return token


def verify_remember_me_token(token):
    """Verify token validity. Returns (user_id, username, role) or None."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        SELECT u.id, u.username, u.role
        FROM session_tokens st
        JOIN users u ON u.id = st.user_id
        WHERE st.token = ? AND st.expires_at > ? AND u.is_active = 1
    """, (token, int(time.time())))
    row = c.fetchone()
    conn.close()
    return row if row else None


def clear_remember_me_token(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM session_tokens WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


# ──────────────────────────────────────────────
# Organization Persistence
# ──────────────────────────────────────────────

def save_organization(user_id, parsed_rows):
    """
    Group parsed rows by EIN and save to database.
    Merges new years with any existing saved data for the same org.
    """
    groups = {}
    for row in parsed_rows:
        ein = row.get("EIN", "")
        if not ein:
            continue
        if ein not in groups:
            groups[ein] = []
        groups[ein].append(row)

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    for ein, rows in groups.items():
        org_name = rows[0].get("OrganizationName", "Unknown")
        new_years = sorted(set(r.get("TaxYear", "") for r in rows))
        data_json = json.dumps(rows, default=str)
        data_hash = hashlib.sha256(data_json.encode()).hexdigest()

        # Check if org already saved
        c.execute(
            "SELECT id, tax_years, parsed_data_json FROM user_organizations WHERE user_id = ? AND ein = ?",
            (user_id, ein),
        )
        existing = c.fetchone()
        if existing:
            eid, old_years_json, old_data_json = existing
            old_years = json.loads(old_years_json) if old_years_json else []
            old_data = json.loads(old_data_json) if old_data_json else []
            # Merge: add new years that don't already exist
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
            """, (org_name, json.dumps(merged_years), json.dumps(old_data, default=str),
                  data_hash, int(time.time()), eid))
        else:
            c.execute("""
                INSERT INTO user_organizations
                (user_id, ein, organization_name, tax_years, parsed_data_json, data_hash, upload_timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (user_id, ein, org_name, json.dumps(new_years), data_json, data_hash, int(time.time())))

    conn.commit()
    conn.close()


def load_user_organizations(user_id):
    """
    Load all saved organizations for a user.
    Returns dict: { ein: { name, years, parsed_data } }
    """
    conn = sqlite3.connect(DB_NAME)
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


def delete_organization(user_id, ein):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "DELETE FROM user_organizations WHERE user_id = ? AND ein = ?",
        (user_id, ein),
    )
    conn.commit()
    conn.close()


# ──────────────────────────────────────────────
# Duplicate Detection
# ──────────────────────────────────────────────

def detect_duplicates(parsed_rows):
    """
    Detect EIN + TaxYear duplicates in a list of parsed rows.

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
                "files": [parsed_rows[i].get("SourceFile", "?") for i in indices],
            })
    return duplicates


# ──────────────────────────────────────────────
# Tags / Categories
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
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO org_tags (user_id, tag_name, tag_color, created_at) VALUES (?, ?, ?, ?)",
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
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        "SELECT id, tag_name, tag_color FROM org_tags WHERE user_id = ? ORDER BY tag_name",
        (user_id,),
    )
    tags = [dict(r) for r in c.fetchall()]
    conn.close()
    return tags


def delete_tag(user_id, tag_id):
    """Delete a tag and all its org associations."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM org_tag_map WHERE tag_id = ? AND user_id = ?", (tag_id, user_id))
    c.execute("DELETE FROM org_tags WHERE id = ? AND user_id = ?", (tag_id, user_id))
    conn.commit()
    conn.close()


def assign_tag(user_id, ein, tag_id):
    """Assign a tag to an organization (by EIN)."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute(
            "INSERT OR IGNORE INTO org_tag_map (user_id, ein, tag_id) VALUES (?, ?, ?)",
            (user_id, ein, tag_id),
        )
        conn.commit()
    finally:
        conn.close()


def remove_tag_from_org(user_id, ein, tag_id):
    """Remove a tag from an organization."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "DELETE FROM org_tag_map WHERE user_id = ? AND ein = ? AND tag_id = ?",
        (user_id, ein, tag_id),
    )
    conn.commit()
    conn.close()


def get_tags_for_org(user_id, ein):
    """Return list of tag dicts assigned to a specific org."""
    conn = sqlite3.connect(DB_NAME)
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


def get_orgs_by_tag(user_id, tag_id):
    """Return list of EINs for a given tag."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "SELECT ein FROM org_tag_map WHERE user_id = ? AND tag_id = ?",
        (user_id, tag_id),
    )
    eins = [r[0] for r in c.fetchall()]
    conn.close()
    return eins
