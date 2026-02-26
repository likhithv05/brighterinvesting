"""
Authentication & Login Page
Branded login UI with security questions, password reset,
remember-me functionality, and admin user management panel.

Developed by Epic Intentions for Brighter Investing
Georgia Institute of Technology — Spring 2026
"""

import streamlit as st
import sqlite3
import bcrypt
import os
import base64
import time

from db_utils import (
    DB_NAME,
    init_extended_db,
    get_user_id,
    get_all_users,
    update_user_role,
    toggle_user_active,
    admin_reset_password,
    update_last_login,
    delete_user,
    save_security_questions,
    get_security_questions_for_user,
    verify_security_answers,
    reset_password,
    create_remember_me_token,
    verify_remember_me_token,
    clear_remember_me_token,
    SECURITY_QUESTIONS,
)


# ----------------------------
# Password Helpers
# ----------------------------

def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt())


def verify_password(password, stored_hash):
    return bcrypt.checkpw(password.encode(), stored_hash)


# ----------------------------
# User Functions
# ----------------------------

def register_user(username, password):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        hashed = hash_password(password)
        c.execute(
            "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
            (username, hashed, int(time.time())),
        )
        conn.commit()
        user_id = c.lastrowid

        # If this is the first user, make them admin
        c.execute("SELECT COUNT(*) FROM users")
        count = c.fetchone()[0]
        if count == 1:
            c.execute("UPDATE users SET role = 'admin' WHERE id = ?", (user_id,))
            conn.commit()

        return True, "Account created successfully", user_id
    except sqlite3.IntegrityError:
        return False, "Username already exists", None
    finally:
        conn.close()


def login_user(username, password):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "SELECT id, password_hash, role, is_active FROM users WHERE username = ?",
        (username,),
    )
    result = c.fetchone()
    conn.close()

    if result:
        uid, stored_hash, role, is_active = result
        if not is_active:
            return False, None, None
        if verify_password(password, stored_hash):
            return True, role, uid

    return False, None, None


# ----------------------------
# CSS for Login Page
# ----------------------------

_LOGIN_CSS = """<style>
/* Login page scoped styles */
.login-wrap {
    max-width: 440px; margin: 40px auto; padding: 0 16px;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}
.login-card {
    background: #fff; border: 1px solid #E2E8F0;
    border-radius: 20px; overflow: hidden;
    box-shadow: 0 4px 24px rgba(0,0,0,.06);
}
.login-hdr {
    background: linear-gradient(135deg, #0D9488 0%, #059669 50%, #0284C7 100%);
    padding: 32px 32px 28px; text-align: center;
}
.login-hdr img { height: 48px; margin-bottom: 12px; }
.login-hdr .login-brand {
    font-size: .68rem; font-weight: 600; color: rgba(255,255,255,.85);
    text-transform: uppercase; letter-spacing: .08em;
}
.login-hdr h1 {
    font-family: 'Inter', sans-serif; font-size: 1.55rem;
    font-weight: 800; color: #fff; margin: 8px 0 0;
    letter-spacing: -.03em; line-height: 1.2;
}
.login-hdr p {
    font-size: .82rem; color: rgba(255,255,255,.7);
    margin: 6px 0 0; line-height: 1.5;
}
.login-body { padding: 28px 32px 32px; }
.login-ft {
    text-align: center; padding: 16px 32px 20px;
    border-top: 1px solid #F1F5F9;
    font-size: .68rem; color: #CBD5E1; line-height: 1.8;
}
.login-ft b { color: #94A3B8; font-weight: 600; }

/* Password strength meter */
.pw-meter { height: 4px; border-radius: 2px; margin: -8px 0 12px; background: #F1F5F9; }
.pw-meter .pw-fill { height: 100%; border-radius: 2px; transition: width .3s, background .3s; }
.pw-weak { width: 33%; background: #E11D48; }
.pw-medium { width: 66%; background: #D97706; }
.pw-strong { width: 100%; background: #059669; }

/* Admin panel */
.admin-card {
    background: #fff; border: 1px solid #E2E8F0; border-radius: 16px;
    padding: 20px 24px; margin-bottom: 12px;
    box-shadow: 0 1px 3px rgba(0,0,0,.04);
}
.admin-card .admin-user {
    font-size: .92rem; font-weight: 600; color: #0F172A;
}
.admin-card .admin-meta {
    font-size: .75rem; color: #64748B; margin-top: 4px; line-height: 1.6;
}
.admin-badge {
    display: inline-block; padding: 2px 10px; border-radius: 100px;
    font-size: .62rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: .04em;
}
.admin-badge.role-admin { background: #E8FAF0; color: #059669; }
.admin-badge.role-user { background: #F1F5F9; color: #64748B; }
.admin-badge.inactive { background: #FFECEB; color: #E11D48; }
</style>"""


# ----------------------------
# Login Page UI
# ----------------------------

def show_login_page():
    init_extended_db()

    # Load logo
    logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "logo.svg")
    logo_b64 = ""
    if os.path.isfile(logo_path):
        with open(logo_path, "rb") as f:
            logo_b64 = base64.b64encode(f.read()).decode()

    # Font + CSS
    st.markdown(
        '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">',
        unsafe_allow_html=True,
    )
    st.markdown(_LOGIN_CSS, unsafe_allow_html=True)

    # Check auto-login via remember-me
    if "remember_me_token" in st.session_state and st.session_state["remember_me_token"]:
        result = verify_remember_me_token(st.session_state["remember_me_token"])
        if result:
            uid, username, role = result
            st.session_state["authenticated"] = True
            st.session_state["username"] = username
            st.session_state["role"] = role
            st.session_state["user_id"] = uid
            update_last_login(uid)
            st.rerun()

    # Logo HTML
    logo_html = (
        f'<img src="data:image/svg+xml;base64,{logo_b64}" alt="Brighter Investing" />'
        if logo_b64
        else '<div style="font-size:1.6rem;font-weight:800;color:#fff;">Brighter</div>'
    )

    # Header card
    st.markdown(f"""
    <div class="login-wrap">
        <div class="login-card">
            <div class="login-hdr">
                {logo_html}
                <div class="login-brand">Form 990 Analyzer</div>
                <h1>Welcome Back</h1>
                <p>Sign in to analyze nonprofit financials</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Tabs
    tab1, tab2, tab3 = st.tabs(["Sign In", "Create Account", "Forgot Password"])

    # ── SIGN IN ──
    with tab1:
        username = st.text_input("Username", key="login_user", placeholder="Enter your username")
        password = st.text_input("Password", type="password", key="login_pass", placeholder="Enter your password")
        remember = st.checkbox("Remember me for 30 days", key="login_remember")

        if st.button("Sign In", type="primary", use_container_width=True):
            if not username or not password:
                st.error("Please enter both username and password.")
            else:
                success, role, uid = login_user(username, password)
                if success:
                    st.session_state["authenticated"] = True
                    st.session_state["username"] = username
                    st.session_state["role"] = role
                    st.session_state["user_id"] = uid
                    update_last_login(uid)
                    if remember:
                        token = create_remember_me_token(uid)
                        st.session_state["remember_me_token"] = token
                    st.rerun()
                else:
                    st.error("Invalid username or password, or account is deactivated.")

    # ── CREATE ACCOUNT ──
    with tab2:
        new_username = st.text_input("Choose Username", key="reg_user", placeholder="Pick a unique username")
        new_password = st.text_input("Choose Password", type="password", key="reg_pass", placeholder="Min. 6 characters")

        # Password strength indicator
        if new_password:
            strength = "pw-weak"
            strength_label = "Weak"
            if len(new_password) >= 10 and any(c.isdigit() for c in new_password) and any(c.isupper() for c in new_password):
                strength = "pw-strong"
                strength_label = "Strong"
            elif len(new_password) >= 8 and (any(c.isdigit() for c in new_password) or any(c.isupper() for c in new_password)):
                strength = "pw-medium"
                strength_label = "Medium"
            st.markdown(
                f'<div class="pw-meter"><div class="pw-fill {strength}"></div></div>'
                f'<p style="font-size:.7rem;color:#64748B;margin-top:-4px;">Strength: {strength_label}</p>',
                unsafe_allow_html=True,
            )

        confirm_password = st.text_input("Confirm Password", type="password", key="reg_confirm", placeholder="Re-enter password")

        st.markdown(
            '<p style="font-size:.78rem;color:#64748B;margin:12px 0 4px;font-weight:600;">'
            'Security Questions <span style="color:#94A3B8;font-weight:400;">(for password recovery)</span></p>',
            unsafe_allow_html=True,
        )
        sq1 = st.selectbox("Question 1", SECURITY_QUESTIONS, key="reg_sq1")
        sa1 = st.text_input("Answer 1", key="reg_sa1", placeholder="Your answer")
        sq2 = st.selectbox("Question 2", [q for q in SECURITY_QUESTIONS if q != sq1], key="reg_sq2")
        sa2 = st.text_input("Answer 2", key="reg_sa2", placeholder="Your answer")

        if st.button("Create Account", type="primary", use_container_width=True):
            if not new_username or not new_password:
                st.error("Username and password are required.")
            elif new_password != confirm_password:
                st.error("Passwords do not match.")
            elif len(new_password) < 6:
                st.error("Password must be at least 6 characters.")
            elif not sa1.strip() or not sa2.strip():
                st.error("Please answer both security questions.")
            else:
                success, message, user_id = register_user(new_username, new_password)
                if success:
                    save_security_questions(user_id, sq1, sa1, sq2, sa2)
                    st.success(f"{message} You can now sign in.")
                else:
                    st.error(message)

    # ── FORGOT PASSWORD ──
    with tab3:
        st.markdown(
            '<p style="font-size:.82rem;color:#64748B;margin-bottom:16px;">'
            "Enter your username and answer your security questions to reset your password.</p>",
            unsafe_allow_html=True,
        )
        reset_user = st.text_input("Username", key="reset_user", placeholder="Your username")

        if reset_user:
            questions = get_security_questions_for_user(reset_user)
            if questions:
                q1, q2 = questions
                ra1 = st.text_input(q1, key="reset_a1", placeholder="Your answer")
                ra2 = st.text_input(q2, key="reset_a2", placeholder="Your answer")

                new_pw = st.text_input("New Password", type="password", key="reset_new_pw", placeholder="Min. 6 characters")
                confirm_pw = st.text_input("Confirm New Password", type="password", key="reset_confirm_pw", placeholder="Re-enter password")

                if st.button("Reset Password", type="primary", use_container_width=True):
                    if not ra1.strip() or not ra2.strip():
                        st.error("Please answer both security questions.")
                    elif not new_pw or len(new_pw) < 6:
                        st.error("New password must be at least 6 characters.")
                    elif new_pw != confirm_pw:
                        st.error("Passwords do not match.")
                    elif verify_security_answers(reset_user, ra1, ra2):
                        reset_password(reset_user, new_pw)
                        st.success("Password reset successfully! You can now sign in with your new password.")
                    else:
                        st.error("Incorrect answers. Please try again.")
            else:
                st.warning("No security questions found for this account. Please contact an administrator.")

    # Footer
    st.markdown("""
    <div class="login-wrap">
        <div class="login-ft">
            Developed by <b>Epic Intentions</b> for Brighter Investing<br>
            Georgia Institute of Technology · Spring 2026
        </div>
    </div>
    """, unsafe_allow_html=True)


# ----------------------------
# Admin Panel (called from app.py)
# ----------------------------

def show_admin_panel():
    """Render the admin user management panel."""
    st.markdown(_LOGIN_CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="sec-t">User Management</div>'
        '<div class="sec-s">View, manage, and configure user accounts.</div>',
        unsafe_allow_html=True,
    )

    users = get_all_users()
    if not users:
        st.info("No users found.")
        return

    for user in users:
        uid = user["id"]
        uname = user["username"]
        role = user["role"] or "user"
        active = user.get("is_active", 1)
        last_login = user.get("last_login")
        created = user.get("created_at")

        # Format timestamps
        login_str = time.strftime("%b %d, %Y", time.localtime(last_login)) if last_login else "Never"
        created_str = time.strftime("%b %d, %Y", time.localtime(created)) if created else "Unknown"
        status_badge = f'<span class="admin-badge role-{role}">{role}</span>'
        if not active:
            status_badge += ' <span class="admin-badge inactive">Inactive</span>'

        st.markdown(f"""
        <div class="admin-card">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <div>
                    <div class="admin-user">{uname} {status_badge}</div>
                    <div class="admin-meta">Created: {created_str} · Last login: {login_str}</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Action buttons in columns (don't allow actions on yourself)
        if uname != st.session_state.get("username"):
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                new_role = "admin" if role == "user" else "user"
                if st.button(f"Make {new_role.title()}", key=f"role_{uid}"):
                    update_user_role(uid, new_role)
                    st.rerun()
            with c2:
                toggle_label = "Deactivate" if active else "Activate"
                if st.button(toggle_label, key=f"toggle_{uid}"):
                    toggle_user_active(uid)
                    st.rerun()
            with c3:
                if st.button("Reset Password", key=f"reset_{uid}"):
                    temp_pw = admin_reset_password(uid)
                    st.info(f"Temporary password for **{uname}**: `{temp_pw}`")
            with c4:
                if st.button("Delete", key=f"del_{uid}", type="secondary"):
                    if st.session_state.get(f"confirm_del_{uid}"):
                        delete_user(uid)
                        st.session_state.pop(f"confirm_del_{uid}", None)
                        st.rerun()
                    else:
                        st.session_state[f"confirm_del_{uid}"] = True
                        st.warning(f"Click Delete again to confirm removing **{uname}**.")
