"""
Account Settings Component
Profile editing, password change, security questions update, and sign-out.

Developed by Epic Intentions for Brighter Investing
Georgia Institute of Technology — Spring 2026
"""

import time

import streamlit as st

from core.db_utils import (
    get_user_by_id,
    update_user,
    change_password,
    SECURITY_QUESTIONS,
    get_security_questions,
    save_security_questions,
    authenticate,
    clear_user_sessions,
)


# ──────────────────────────────────────────────
# Password-Strength Helpers
# ──────────────────────────────────────────────

_STRENGTH = [
    ("Weak", "#EF4444", "25%"),
    ("Fair", "#F59E0B", "50%"),
    ("Good", "#22C55E", "75%"),
    ("Strong", "#0D9488", "100%"),
]


def _pw_checklist(password):
    """Return (html, met_count) for password requirement checks."""
    checks = [
        (len(password) >= 8, "At least 8 characters"),
        (any(c.isupper() for c in password), "One uppercase letter"),
        (any(c.isdigit() for c in password), "One number"),
    ]
    met = sum(ok for ok, _ in checks)
    items = ""
    for ok, label in checks:
        color = "#22C55E" if ok else "#94A3B8"
        icon = "&#10003;" if ok else "&#10007;"
        items += (
            f'<div style="font-size:.68rem;color:{color};">'
            f'{icon} {label}</div>'
        )
    return items, met


def _pw_strength(met):
    """Return HTML for a password-strength bar."""
    label, color, width = _STRENGTH[met]  # met is 0-3
    return (
        f'<div style="height:4px;background:#E2E8F0;border-radius:2px;'
        f'margin:4px 0 2px;">'
        f'<div style="width:{width};height:100%;background:{color};'
        f'border-radius:2px;transition:width .2s;"></div></div>'
        f'<div style="font-size:.62rem;color:{color};font-weight:600;">'
        f'{label}</div>'
    )


def _pw_block(password):
    """Render password checklist + strength bar."""
    if not password:
        return
    checklist_html, met = _pw_checklist(password)
    strength_html = _pw_strength(met)
    st.markdown(checklist_html + strength_html, unsafe_allow_html=True)


# ──────────────────────────────────────────────
# Date Formatter
# ──────────────────────────────────────────────

def _fmt_date(ts):
    """Format a unix timestamp as 'Mar 3, 2026'."""
    if not ts:
        return "Unknown"
    return time.strftime("%b %-d, %Y", time.localtime(ts))


# ──────────────────────────────────────────────
# Main Render
# ──────────────────────────────────────────────

def render_account_settings():
    """Render account settings UI. Call inside a sidebar expander."""
    uid = st.session_state.get("auth_user_id")
    user = get_user_by_id(uid) if uid else None
    if user is None:
        return

    # ── Profile Section ──
    st.markdown(
        '<div style="font-size:0.65rem;font-weight:600;color:#94A3B8;'
        'letter-spacing:0.05em;text-transform:uppercase;margin:0 0 4px;">'
        'Profile</div>',
        unsafe_allow_html=True,
    )

    # Username (read-only)
    st.text_input("Username", value=user["username"], disabled=True,
                  key="acct_username")

    # Role badge
    role = user["role"] or "user"
    if role == "admin":
        badge = ('<span class="admin-badge role-admin" '
                 'style="font-size:.6rem;">Admin</span>')
    else:
        badge = ('<span class="admin-badge role-user" '
                 'style="font-size:.6rem;">Member</span>')
    st.markdown(
        f'<div style="font-size:0.72rem;color:#64748B;">'
        f'Role: {badge}</div>',
        unsafe_allow_html=True,
    )

    # Member since
    st.markdown(
        f'<div style="font-size:0.72rem;color:#64748B;margin-bottom:8px;">'
        f'Member since: {_fmt_date(user["created_at"])}</div>',
        unsafe_allow_html=True,
    )

    # Display name
    new_display = st.text_input(
        "Display name",
        value=user.get("display_name") or user["username"],
        key="acct_display_name",
    )
    if st.button("Update Name", key="acct_update_name",
                 use_container_width=True):
        if new_display and new_display.strip():
            if update_user(uid, display_name=new_display.strip()):
                st.session_state["auth_display_name"] = new_display.strip()
                st.success("Display name updated.")
                st.rerun()
            else:
                st.error("Failed to update display name.")
        else:
            st.error("Display name cannot be empty.")

    # Email
    new_email = st.text_input(
        "Email",
        value=user.get("email") or "",
        key="acct_email",
    )
    if st.button("Update Email", key="acct_update_email",
                 use_container_width=True):
        if update_user(uid, email=new_email.strip()):
            st.success("Email updated.")
            st.rerun()
        else:
            st.error("Invalid email format.")

    # ── Change Password ──
    with st.expander("Change Password"):
        cur_pw = st.text_input("Current password", type="password",
                               key="acct_cur_pw")
        new_pw = st.text_input("New password", type="password",
                               key="acct_new_pw")
        _pw_block(new_pw)
        confirm_pw = st.text_input("Confirm new password", type="password",
                                   key="acct_confirm_pw")

        if st.button("Change Password", key="acct_change_pw_btn",
                     use_container_width=True):
            if not cur_pw or not new_pw or not confirm_pw:
                st.error("All fields are required.")
            elif new_pw != confirm_pw:
                st.error("New passwords do not match.")
            else:
                result = change_password(uid, cur_pw, new_pw)
                if result["success"]:
                    st.success("Password changed successfully.")
                else:
                    st.error(result["error"])

    # ── Security Questions ──
    with st.expander("Security Questions"):
        sq_pw = st.text_input(
            "Current password (to verify identity)",
            type="password",
            key="acct_sq_pw",
        )

        verified = st.session_state.get("_acct_sq_verified", False)

        if not verified:
            if st.button("Verify", key="acct_sq_verify_btn",
                         use_container_width=True):
                if not sq_pw:
                    st.error("Enter your current password.")
                else:
                    result = authenticate(user["username"], sq_pw)
                    if result["success"]:
                        st.session_state["_acct_sq_verified"] = True
                        st.rerun()
                    else:
                        st.error("Incorrect password.")
        else:
            existing_qs = get_security_questions(uid)
            if existing_qs:
                st.caption(
                    f"You have {len(existing_qs)} security question(s) set. "
                    f"Update them below."
                )

            q1 = st.selectbox("Question 1", SECURITY_QUESTIONS,
                               key="acct_sq1")
            a1 = st.text_input("Answer 1", key="acct_sa1",
                                placeholder="Your answer")

            q2_options = [q for q in SECURITY_QUESTIONS if q != q1]
            q2 = st.selectbox("Question 2", q2_options, key="acct_sq2")
            a2 = st.text_input("Answer 2", key="acct_sa2",
                                placeholder="Your answer")

            if st.button("Update Questions", key="acct_sq_save_btn",
                         use_container_width=True):
                if not a1.strip() or not a2.strip():
                    st.error("Please answer both questions.")
                else:
                    ok = save_security_questions(uid, [(q1, a1), (q2, a2)])
                    if ok:
                        st.success("Security questions updated.")
                        st.session_state["_acct_sq_verified"] = False
                    else:
                        st.error("Failed to save security questions.")

    # ── Sign Out ──
    st.divider()
    if st.button("Sign Out", key="acct_sign_out",
                 use_container_width=True):
        clear_user_sessions(uid)
        st.session_state.clear()
        st.rerun()
