"""
Authentication & Login Page
Centered login UI with sign-in, registration, and password reset.

Developed by Epic Intentions for Brighter Investing
Georgia Institute of Technology — Spring 2026
"""

import os
import re
import time
import base64

import streamlit as st

from core.db_utils import (
    init_db,
    create_user,
    authenticate,
    save_security_questions,
    get_security_questions,
    verify_security_answers,
    reset_password,
    create_session_token,
    validate_session_token,
    get_user_by_username,
)


# ──────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────

_QUESTIONS = [
    "What was the name of your first pet?",
    "What city were you born in?",
    "What was your childhood nickname?",
    "What is your mother's maiden name?",
    "What was the name of your first school?",
    "What is your favorite book?",
]

_USERNAME_RE = re.compile(r"^[a-z0-9_]{3,30}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# (label, color, bar-width) indexed by number of password requirements met
_STRENGTH = [
    ("Weak",   "#DC2626", "25%"),
    ("Fair",   "#D97706", "50%"),
    ("Good",   "#EAB308", "75%"),
    ("Strong", "#059669", "100%"),
]


# ──────────────────────────────────────────────
# Internal Helpers
# ──────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def _read_login_css():
    """Read main.css from disk (cached)."""
    css_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "styles", "main.css"
    )
    if os.path.isfile(css_path):
        with open(css_path) as f:
            return f.read()
    return ""


def _load_css():
    """Load main.css, Inter font, and login-page layout overrides."""
    # Font
    st.markdown(
        '<link href="https://fonts.googleapis.com/css2?'
        'family=Inter:wght@300;400;500;600;700;800;900&display=swap" '
        'rel="stylesheet">',
        unsafe_allow_html=True,
    )
    # Main CSS — must be its own st.markdown call so the parser
    # recognises the <style> block correctly.
    css_text = _read_login_css()
    if css_text:
        st.markdown(f"<style>\n{css_text}\n</style>", unsafe_allow_html=True)

    # Login-specific: center content, constrain width, hide sidebar
    st.markdown(
        "<style>\n"
        '[data-testid="stMainBlockContainer"] {\n'
        "  max-width: 480px; margin: 0 auto;\n"
        "}\n"
        '[data-testid="stSidebar"] { display: none; }\n'
        "</style>",
        unsafe_allow_html=True,
    )


@st.cache_data(show_spinner=False)
def _load_logo_b64():
    """Return base64-encoded logo, or empty string if not found."""
    logo_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "assets", "logo.svg"
    )
    if os.path.isfile(logo_path):
        with open(logo_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return ""


def _render_header(logo_b64):
    """Render centered header: optional logo, app title, tagline."""
    logo_html = ""
    if logo_b64:
        logo_html = (
            f'<img src="data:image/svg+xml;base64,{logo_b64}" '
            f'alt="Brighter Investing" '
            f'style="height:44px;margin-bottom:10px;display:block;'
            f'margin-left:auto;margin-right:auto;" />'
        )
    st.markdown(
        f'<div style="text-align:center;padding:40px 0 8px;">'
        f'{logo_html}'
        f'<div style="font-size:1.5rem;font-weight:700;color:#0F172A;'
        f'letter-spacing:-0.02em;line-height:1.3;">Form 990 Analyzer</div>'
        f'<div style="font-size:0.8rem;color:#64748B;margin-top:4px;">'
        f'Nonprofit Financial Intelligence by Brighter Investing</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _render_footer():
    """Render bottom-of-page credit line."""
    st.markdown(
        '<div style="text-align:center;font-size:0.7rem;color:#94A3B8;'
        'margin-top:48px;padding-bottom:24px;">'
        'Built by Epic Intentions &middot; Georgia Tech &middot; Spring 2026'
        '</div>',
        unsafe_allow_html=True,
    )


def _set_auth(user):
    """Write all authentication keys into session state."""
    st.session_state.update({
        "auth_authenticated": True,
        "auth_user_id": user["id"],
        "auth_username": user["username"],
        "auth_display_name": user["display_name"],
        "auth_role": user["role"],
    })


def _try_auto_login():
    """Check for a valid session token and auto-login if found.

    Returns True if auto-login succeeded, False otherwise.
    """
    token = st.session_state.get("session_token")
    if not token:
        token = st.query_params.get("token")
    if not token:
        return False

    user = validate_session_token(token)
    if user:
        _set_auth(user)
        st.session_state["session_token"] = token
        return True

    # Token expired or invalid — clean up
    st.session_state.pop("session_token", None)
    try:
        del st.query_params["token"]
    except (KeyError, Exception):
        pass
    return False


def _pw_checklist(password):
    """Return (html_string, requirements_met_count)."""
    checks = [
        (len(password) >= 8, "At least 8 characters"),
        (any(c.isupper() for c in password), "Contains an uppercase letter"),
        (any(c.isdigit() for c in password), "Contains a number"),
    ]
    met = 0
    lines = []
    for ok, label in checks:
        if ok:
            met += 1
            lines.append(
                f'<div style="font-size:0.78rem;color:#059669;margin:1px 0;">'
                f'\u2713 {label}</div>'
            )
        else:
            lines.append(
                f'<div style="font-size:0.78rem;color:#94A3B8;margin:1px 0;">'
                f'\u25a1 {label}</div>'
            )
    return "\n".join(lines), met


def _pw_strength(met):
    """Return HTML for the password strength bar + label."""
    label, color, width = _STRENGTH[met]
    return (
        f'<div style="height:4px;border-radius:2px;background:#F1F5F9;'
        f'margin:6px 0 2px;">'
        f'<div style="height:100%;border-radius:2px;width:{width};'
        f'background:{color};transition:width 0.25s ease;"></div></div>'
        f'<div style="font-size:0.7rem;color:{color};margin-bottom:4px;">'
        f'{label}</div>'
    )


def _pw_block(password):
    """Render the requirements checklist + strength meter for a password."""
    if not password:
        return
    html, met = _pw_checklist(password)
    html += _pw_strength(met)
    st.markdown(html, unsafe_allow_html=True)


# ──────────────────────────────────────────────
# Tab: Sign In
# ──────────────────────────────────────────────

def _tab_sign_in():
    """Render the Sign In form."""
    # Show force-logout reason if the user was kicked out
    logout_reason = st.session_state.pop("_logout_reason", None)
    if logout_reason:
        st.warning(logout_reason)

    # Show success messages from other tabs (account creation, password reset)
    msg = st.session_state.pop("_login_msg", None)
    if msg:
        st.success(msg)

    username = st.text_input(
        "Username", key="si_user", placeholder="Enter your username",
    )
    password = st.text_input(
        "Password", type="password", key="si_pass",
        placeholder="Enter your password",
    )
    remember = st.checkbox("Remember me for 30 days", key="si_remember")

    if st.button(
        "Sign In", type="primary", use_container_width=True, key="si_btn",
    ):
        if not username or not username.strip():
            st.error("Please enter your username.")
            return
        if not password:
            st.error("Please enter your password.")
            return

        result = authenticate(username.strip().lower(), password)

        if result["success"]:
            _set_auth(result["user"])
            if remember:
                token = create_session_token(result["user"]["id"])
                if token:
                    st.session_state["session_token"] = token
                    st.query_params["token"] = token
            st.rerun()
        else:
            st.error(result["error"])


# ──────────────────────────────────────────────
# Tab: Create Account
# ──────────────────────────────────────────────

def _tab_create_account():
    """Render the account creation form."""
    username = st.text_input(
        "Choose a username", key="ca_user",
        placeholder="3-30 characters, letters and numbers only",
    )

    # Real-time username format hint
    if username:
        if _USERNAME_RE.match(username.strip().lower()):
            st.markdown(
                '<div style="font-size:0.72rem;color:#059669;'
                'margin:-10px 0 8px;">\u2713 Valid username format</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div style="font-size:0.72rem;color:#DC2626;'
                'margin:-10px 0 8px;">'
                'Must be 3-30 characters: lowercase letters, numbers, '
                'underscores</div>',
                unsafe_allow_html=True,
            )

    display_name = st.text_input(
        "Your name", key="ca_name",
        placeholder="How you'd like to be addressed",
    )
    email = st.text_input(
        "Email (optional)", key="ca_email", placeholder="you@example.com",
    )

    password = st.text_input(
        "Create a password", type="password", key="ca_pass",
    )
    _pw_block(password)

    confirm = st.text_input(
        "Confirm password", type="password", key="ca_confirm",
    )

    # Security questions
    st.markdown(
        '<div style="font-size:0.82rem;font-weight:600;color:#334155;'
        'margin:16px 0 2px;">Security Questions</div>'
        '<div style="font-size:0.72rem;color:#94A3B8;margin-bottom:8px;">'
        'Used for password recovery.</div>',
        unsafe_allow_html=True,
    )

    sq1 = st.selectbox("Security Question 1", _QUESTIONS, key="ca_sq1")
    sa1 = st.text_input("Answer 1", key="ca_sa1", placeholder="Your answer")
    sq2_opts = [q for q in _QUESTIONS if q != sq1]
    sq2 = st.selectbox("Security Question 2", sq2_opts, key="ca_sq2")
    sa2 = st.text_input("Answer 2", key="ca_sa2", placeholder="Your answer")

    if st.button(
        "Create Account", type="primary", use_container_width=True,
        key="ca_btn",
    ):
        errors = _validate_create(
            username, display_name, email, password, confirm,
            sq1, sq2, sa1, sa2,
        )
        if errors:
            for e in errors:
                st.error(e)
            return

        uname = username.strip().lower()
        result = create_user(
            uname,
            display_name.strip(),
            password,
            email=email.strip() if email and email.strip() else None,
        )

        if not result["success"]:
            st.error(result["error"])
            return

        save_security_questions(
            result["user_id"], [(sq1, sa1), (sq2, sa2)],
        )

        # Check if first user (admin)
        user = get_user_by_username(uname)
        msg = "Account created! You can now sign in."
        if user and user["role"] == "admin":
            msg += (
                " As the first user, you've been granted "
                "administrator privileges."
            )
        st.session_state["_login_msg"] = msg
        st.success(msg)


def _validate_create(username, display_name, email, password, confirm,
                     sq1, sq2, sa1, sa2):
    """Validate all registration fields. Returns list of error strings."""
    errors = []
    uname = username.strip().lower() if username else ""

    if not uname:
        errors.append("Username is required.")
    elif not _USERNAME_RE.match(uname):
        errors.append(
            "Username must be 3-30 characters: "
            "lowercase letters, numbers, and underscores only."
        )

    if not display_name or not display_name.strip():
        errors.append("Display name is required.")

    if email and email.strip() and not _EMAIL_RE.match(email.strip()):
        errors.append("Invalid email format.")

    if not password:
        errors.append("Password is required.")
    else:
        if len(password) < 8:
            errors.append("Password must be at least 8 characters.")
        if not any(c.isupper() for c in password):
            errors.append("Password must contain an uppercase letter.")
        if not any(c.isdigit() for c in password):
            errors.append("Password must contain a number.")

    if password and confirm and password != confirm:
        errors.append("Passwords do not match.")
    elif password and not confirm:
        errors.append("Please confirm your password.")

    if sq1 == sq2:
        errors.append("Security questions must be different from each other.")
    if not sa1 or len(sa1.strip()) < 2:
        errors.append("Security answer 1 must be at least 2 characters.")
    if not sa2 or len(sa2.strip()) < 2:
        errors.append("Security answer 2 must be at least 2 characters.")

    return errors


# ──────────────────────────────────────────────
# Tab: Reset Password
# ──────────────────────────────────────────────

def _tab_reset_password():
    """Render the reset password flow (3 steps)."""
    step = st.session_state.get("_rp_step", 1)
    if step == 1:
        _rp_step1()
    elif step == 2:
        _rp_step2()
    elif step == 3:
        _rp_step3()


def _rp_step1():
    """Step 1: Enter username."""
    st.markdown(
        '<div style="font-size:0.82rem;color:#64748B;margin-bottom:12px;">'
        'Enter your username to begin the password reset process.</div>',
        unsafe_allow_html=True,
    )
    username = st.text_input(
        "Username", key="rp_user", placeholder="Enter your username",
    )
    if st.button(
        "Continue", type="primary", use_container_width=True, key="rp_go",
    ):
        if not username or not username.strip():
            st.error("Please enter your username.")
            return

        uname = username.strip().lower()
        user = get_user_by_username(uname)

        # Always transition to step 2 regardless of whether user exists
        # (anti-enumeration: same behavior, same timing, same message)
        st.session_state["_rp_step"] = 2
        st.session_state["_rp_attempts"] = 0

        if user:
            questions = get_security_questions(user["id"])
            if questions and len(questions) >= 2:
                st.session_state["_rp_uid"] = user["id"]
                st.session_state["_rp_qs"] = questions[:2]
            else:
                st.session_state["_rp_uid"] = None
                st.session_state["_rp_qs"] = []
        else:
            st.session_state["_rp_uid"] = None
            st.session_state["_rp_qs"] = []

        st.rerun()


def _rp_step2():
    """Step 2: Answer security questions (or show generic message)."""
    attempts = st.session_state.get("_rp_attempts", 0)
    questions = st.session_state.get("_rp_qs", [])
    uid = st.session_state.get("_rp_uid")

    st.info("If this account exists, security questions will be shown.")

    if attempts >= 3:
        st.error("Too many attempts. Please try again later.")
        if st.button("Start over", use_container_width=True, key="rp_over"):
            _rp_clear()
            st.rerun()
        return

    if not questions or not uid:
        # User not found or no questions — just the generic message
        if st.button("Start over", use_container_width=True, key="rp_back"):
            _rp_clear()
            st.rerun()
        return

    a1 = st.text_input(questions[0], key="rp_a1", placeholder="Your answer")
    a2 = st.text_input(questions[1], key="rp_a2", placeholder="Your answer")

    c1, c2 = st.columns(2)
    with c1:
        if st.button(
            "Verify", type="primary", use_container_width=True, key="rp_vfy",
        ):
            if not a1 or not a1.strip() or not a2 or not a2.strip():
                st.error("Please answer both questions.")
                return

            if verify_security_answers(uid, [a1, a2]):
                st.session_state["_rp_step"] = 3
                st.rerun()
            else:
                st.session_state["_rp_attempts"] = attempts + 1
                if attempts + 1 >= 3:
                    st.error("Too many attempts. Please try again later.")
                else:
                    st.error("One or more answers are incorrect.")
                st.rerun()
    with c2:
        if st.button("Cancel", use_container_width=True, key="rp_cancel2"):
            _rp_clear()
            st.rerun()


def _rp_step3():
    """Step 3: Set new password."""
    st.markdown(
        '<div style="font-size:0.82rem;color:#059669;margin-bottom:12px;">'
        '\u2713 Identity verified. Choose a new password.</div>',
        unsafe_allow_html=True,
    )

    new_pw = st.text_input(
        "New password", type="password", key="rp_npw",
    )
    _pw_block(new_pw)

    confirm = st.text_input(
        "Confirm new password", type="password", key="rp_cpw",
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button(
            "Reset Password", type="primary", use_container_width=True,
            key="rp_reset",
        ):
            errors = []
            if not new_pw:
                errors.append("Password is required.")
            else:
                if len(new_pw) < 8:
                    errors.append(
                        "Password must be at least 8 characters."
                    )
                if not any(c.isupper() for c in new_pw):
                    errors.append(
                        "Password must contain an uppercase letter."
                    )
                if not any(c.isdigit() for c in new_pw):
                    errors.append("Password must contain a number.")

            if new_pw and confirm and new_pw != confirm:
                errors.append("Passwords do not match.")
            elif new_pw and not confirm:
                errors.append("Please confirm your password.")

            if errors:
                for e in errors:
                    st.error(e)
                return

            uid = st.session_state.get("_rp_uid")
            result = reset_password(uid, new_pw)

            if result["success"]:
                _rp_clear()
                st.session_state["_login_msg"] = (
                    "Password reset successful! You can now sign in."
                )
                st.success(
                    "Password reset successful! You can now sign in."
                )
            else:
                st.error(result.get("error", "Failed to reset password."))
    with c2:
        if st.button("Cancel", use_container_width=True, key="rp_cancel3"):
            _rp_clear()
            st.rerun()


def _rp_clear():
    """Remove all reset-flow keys from session state."""
    for k in ("_rp_step", "_rp_uid", "_rp_qs", "_rp_attempts"):
        st.session_state.pop(k, None)


# ──────────────────────────────────────────────
# Public Interface
# ──────────────────────────────────────────────

def show_login_page():
    """Render the login page.

    Returns True if auto-login succeeded (session state already set,
    caller can proceed to load the app). Returns False if the login
    form was displayed (caller should st.stop()).
    """
    if not st.session_state.get("_db_initialized"):
        import sqlite3 as _sqlite3
        try:
            init_db()
            st.session_state["_db_initialized"] = True
        except _sqlite3.DatabaseError:
            st.error(
                "**Database error.** The database file may be corrupted. "
                "Delete `auth.db` and restart the app to create a fresh database."
            )
            st.stop()

    if _try_auto_login():
        return True

    _load_css()
    _render_header(_load_logo_b64())

    tab1, tab2, tab3 = st.tabs(
        ["Sign In", "Create Account", "Reset Password"],
    )

    with tab1:
        _tab_sign_in()
    with tab2:
        _tab_create_account()
    with tab3:
        _tab_reset_password()

    _render_footer()
    return False
