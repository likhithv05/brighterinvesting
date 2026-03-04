"""
Admin Panel Component
User management UI rendered inside a sidebar expander.
Only accessible to users with role='admin'.

Developed by Epic Intentions for Brighter Investing
Georgia Institute of Technology — Spring 2026
"""

import time

import streamlit as st

from core.db_utils import (
    get_all_users,
    get_user_by_id,
    admin_set_role,
    admin_set_active,
    admin_unlock,
    admin_delete,
    admin_reset_pw,
    admin_create,
)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _relative_time(ts):
    """Format a unix timestamp as a human-readable relative string."""
    if not ts:
        return "Never"
    diff = int(time.time()) - ts
    if diff < 60:
        return "Just now"
    if diff < 3600:
        m = diff // 60
        return f"{m} min ago" if m > 1 else "1 min ago"
    if diff < 86400:
        h = diff // 3600
        return f"{h} hr ago" if h > 1 else "1 hr ago"
    d = diff // 86400
    if d < 30:
        return f"{d} day{'s' if d > 1 else ''} ago"
    if d < 365:
        mo = d // 30
        return f"{mo} mo ago" if mo > 1 else "1 mo ago"
    y = d // 365
    return f"{y} yr ago" if y > 1 else "1 yr ago"


def _fmt_date(ts):
    """Format a unix timestamp as 'Mar 1, 2026'."""
    if not ts:
        return "Unknown"
    return time.strftime("%b %-d, %Y", time.localtime(ts))


def _role_badge(role):
    """Return HTML for a role pill badge."""
    if role == "admin":
        return (
            '<span class="admin-badge role-admin" '
            'style="font-size:.6rem;">Admin</span>'
        )
    return (
        '<span class="admin-badge role-user" '
        'style="font-size:.6rem;">Member</span>'
    )


def _status_badge(is_active, is_locked):
    """Return HTML for a status pill badge."""
    if is_locked:
        return (
            '<span class="admin-badge" style="font-size:.6rem;'
            'background:#FEF3C7;color:#D97706;">Locked</span>'
        )
    if not is_active:
        return (
            '<span class="admin-badge inactive" '
            'style="font-size:.6rem;">Inactive</span>'
        )
    return (
        '<span class="admin-badge" style="font-size:.6rem;'
        'background:#ECFDF5;color:#059669;">Active</span>'
    )


# ──────────────────────────────────────────────
# User Actions
# ──────────────────────────────────────────────

def _render_actions(admin_id, user, is_locked):
    """Render action buttons for a single user row."""
    uid = user["id"]
    uname = user["username"]
    display = user.get("display_name") or uname
    role = user["role"] or "user"
    is_active = user.get("is_active", 1)

    # ── Role toggle ──
    new_role = "admin" if role == "user" else "user"
    new_label = "Make Admin" if role == "user" else "Make Member"
    if st.button(new_label, key=f"ap_role_{uid}", use_container_width=True):
        admin_set_role(admin_id, uid, new_role)
        st.rerun()

    # ── Active / Inactive toggle ──
    if is_active:
        if st.button("Deactivate", key=f"ap_deact_{uid}",
                      use_container_width=True):
            admin_set_active(admin_id, uid, False)
            st.rerun()
    else:
        if st.button("Activate", key=f"ap_act_{uid}",
                      use_container_width=True):
            admin_set_active(admin_id, uid, True)
            st.rerun()

    # ── Unlock (only when locked) ──
    if is_locked:
        if st.button("Unlock Account", key=f"ap_unlock_{uid}",
                      use_container_width=True):
            admin_unlock(admin_id, uid)
            st.rerun()

    # ── Reset Password ──
    if st.button("Reset Password", key=f"ap_rpw_{uid}",
                  use_container_width=True):
        temp_pw = admin_reset_pw(admin_id, uid)
        if temp_pw:
            st.session_state[f"_ap_temp_pw_{uid}"] = temp_pw
            st.rerun()

    # Show temp password if it was just generated
    temp = st.session_state.pop(f"_ap_temp_pw_{uid}", None)
    if temp:
        st.markdown(
            '<div style="font-size:0.72rem;color:#64748B;margin-bottom:4px;">'
            'Temporary password (copy this now &mdash; it won\'t be '
            'shown again):</div>',
            unsafe_allow_html=True,
        )
        st.code(temp, language=None)
        st.caption("The user should change their password after logging in.")

    # ── Delete Account (two-click confirmation) ──
    confirm_key = f"_ap_confirm_del_{uid}"
    if st.session_state.get(confirm_key):
        st.warning(
            f"This will permanently delete **{display}**'s account "
            f"and all their saved data. This cannot be undone."
        )
        c1, c2 = st.columns(2)
        with c1:
            if st.button(
                "Yes, delete permanently",
                key=f"ap_del_yes_{uid}",
                use_container_width=True,
            ):
                admin_delete(admin_id, uid)
                st.session_state.pop(confirm_key, None)
                st.rerun()
        with c2:
            if st.button("Cancel", key=f"ap_del_no_{uid}",
                          use_container_width=True):
                st.session_state.pop(confirm_key, None)
                st.rerun()
    else:
        if st.button("Delete Account", key=f"ap_del_{uid}",
                      use_container_width=True):
            st.session_state[confirm_key] = True
            st.rerun()


# ──────────────────────────────────────────────
# Create User
# ──────────────────────────────────────────────

def _render_create_user(admin_id):
    """Render the admin-only create-user form."""
    username = st.text_input(
        "Username", key="ap_cu_user",
        placeholder="3-30 chars, lowercase",
    )
    display_name = st.text_input(
        "Display name", key="ap_cu_name",
        placeholder="Full name",
    )
    temp_pw = st.text_input(
        "Temporary password", key="ap_cu_pw",
        placeholder="Min 8 chars, 1 upper, 1 digit",
    )
    role = st.selectbox(
        "Role", ["user", "admin"], key="ap_cu_role",
    )

    if st.button("Create Account", key="ap_cu_btn", type="primary",
                  use_container_width=True):
        if not username or not username.strip():
            st.error("Username is required.")
            return
        if not display_name or not display_name.strip():
            st.error("Display name is required.")
            return
        if not temp_pw:
            st.error("Password is required.")
            return

        result = admin_create(
            admin_id,
            username.strip().lower(),
            display_name.strip(),
            temp_pw,
            role=role,
        )

        if result["success"]:
            st.success(f"Account **{username.strip().lower()}** created.")
            st.rerun()
        else:
            st.error(result["error"])


# ──────────────────────────────────────────────
# Public Interface
# ──────────────────────────────────────────────

def render_admin_panel():
    """Render the admin panel. Call this inside a sidebar expander.

    Exits silently if the current user is not an admin.
    """
    if st.session_state.get("auth_role") != "admin":
        return  # silently don't render

    admin_id = st.session_state.get("auth_user_id")
    if not admin_id:
        return

    # Double-check against the database (defense in depth)
    admin_user = get_user_by_id(admin_id)
    if not admin_user or admin_user["role"] != "admin":
        return

    users = get_all_users()
    now = int(time.time())
    my_username = st.session_state.get("auth_username")

    # ── Stats header ──
    total = len(users)
    n_active = sum(1 for u in users if u.get("is_active", 1))
    n_locked = sum(
        1 for u in users if (u.get("locked_until") or 0) > now
    )

    st.markdown(
        f'<div style="font-size:0.78rem;font-weight:600;color:#0F172A;">'
        f'Administration</div>'
        f'<div style="font-size:0.68rem;color:#64748B;margin-bottom:8px;">'
        f'{total} total &middot; {n_active} active'
        f'{f" &middot; {n_locked} locked" if n_locked else ""}'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Per-user expanders ──
    for user in users:
        uid = user["id"]
        uname = user["username"]
        display = user.get("display_name") or uname
        role = user["role"] or "user"
        is_active = user.get("is_active", 1)
        is_locked = (user.get("locked_until") or 0) > now
        is_self = (uname == my_username)

        label = f"{display} (@{uname})"

        with st.expander(label):
            # Badges + metadata
            st.markdown(
                f'{_role_badge(role)} {_status_badge(is_active, is_locked)}'
                f'<br>'
                f'<span style="font-size:0.68rem;color:#64748B;">'
                f'Last login: {_relative_time(user.get("last_login"))}'
                f'</span><br>'
                f'<span style="font-size:0.68rem;color:#64748B;">'
                f'Member since: {_fmt_date(user.get("created_at"))}'
                f'</span>',
                unsafe_allow_html=True,
            )

            if is_self:
                st.caption(
                    "You cannot modify your own admin account."
                )
            else:
                st.markdown("---")
                _render_actions(admin_id, user, is_locked)

    # ── Create User ──
    st.markdown("---")
    with st.expander("Create User Account"):
        _render_create_user(admin_id)
