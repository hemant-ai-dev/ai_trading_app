"""Admin user management UI — no password hashes, no recoverable passwords."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from admin.user_management import delete_user, get_user, list_users, pending_resets, set_active, set_role
from auth.users import admin_reset_password


def render_user_management(actor: dict) -> None:
    if str(actor.get("role") or "") != "Admin":
        st.error("Only administrators can open User Management.")
        return

    st.markdown('<div class="terminal-title">User Management</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="terminal-sub">Excel user workbook · passwords are hashed and never displayed</div>',
        unsafe_allow_html=True,
    )

    pending = pending_resets()
    if pending:
        st.warning(f"{len(pending)} password-reset request(s) waiting.")

    f1, f2, f3 = st.columns([2, 1, 1])
    search = f1.text_input("Search username or email", placeholder="Type to filter")
    role = f2.selectbox("Role", ["All", "Admin", "User"])
    status = f3.selectbox("Status", ["All", "Active", "Inactive"])

    rows = list_users(
        search=search,
        role="" if role == "All" else role,
        status="" if status == "All" else status,
    )
    display = []
    for r in rows:
        display.append(
            {
                "User ID": r["UserId"],
                "Username": r["Username"],
                "Email": r["Email"],
                "Role": r["Role"],
                "Status": "Active" if r["IsActive"] else "Inactive",
                "Created Date": r["CreatedAt"],
                "Updated Date": r["UpdatedAt"],
                "Last Login": r["LastLoginAt"] or "—",
            }
        )
    st.dataframe(pd.DataFrame(display), use_container_width=True, hide_index=True)
    st.caption(f"{len(rows)} user(s). Original passwords cannot be shown — use Reset Password.")

    ids = [int(r["UserId"]) for r in rows]
    if not ids:
        return

    selected = st.selectbox("View user details", ids, format_func=lambda i: _label(i, rows))
    detail = get_user(int(selected))
    if not detail:
        return

    st.markdown("##### Account")
    c1, c2, c3 = st.columns(3)
    c1.write(f"**ID:** {detail['UserId']}")
    c2.write(f"**Username:** {detail['Username']}")
    c3.write(f"**Email:** {detail['Email']}")
    d1, d2, d3 = st.columns(3)
    d1.write(f"**Role:** {detail['Role']}")
    d2.write(f"**Status:** {'Active' if detail['IsActive'] else 'Inactive'}")
    d3.write(f"**Must change password:** {'Yes' if detail['MustChangePassword'] else 'No'}")
    st.caption(f"Created {detail['CreatedAt']} · Updated {detail['UpdatedAt']} · Last login {detail['LastLoginAt'] or '—'}")

    a1, a2, a3, a4 = st.columns(4)
    if detail["IsActive"]:
        if a1.button("Deactivate", use_container_width=True):
            if int(detail["UserId"]) == int(actor["user_id"]):
                st.error("You cannot deactivate your own session here.")
            else:
                set_active(int(detail["UserId"]), False)
                st.rerun()
    else:
        if a1.button("Activate", use_container_width=True, type="primary"):
            set_active(int(detail["UserId"]), True)
            st.rerun()

    new_role = "User" if detail["Role"] == "Admin" else "Admin"
    if a2.button(f"Make {new_role}", use_container_width=True):
        err = set_role(int(detail["UserId"]), new_role)
        if err:
            st.error(err)
        else:
            st.rerun()

    if a3.button("Reset password", use_container_width=True):
        temp, err = admin_reset_password(int(detail["UserId"]))
        if err:
            st.error(err)
        else:
            st.session_state["admin_temp_pw"] = {
                "user_id": detail["UserId"],
                "username": detail["Username"],
                "temp": temp,
            }
            st.rerun()

    confirm = a4.checkbox("Confirm delete")
    if st.button("Delete user", disabled=not confirm):
        err = delete_user(int(detail["UserId"]), actor_id=int(actor["user_id"]))
        if err:
            st.error(err)
        else:
            st.success("User deleted.")
            st.rerun()

    shown = st.session_state.get("admin_temp_pw")
    if shown and int(shown.get("user_id") or 0) == int(detail["UserId"]):
        st.success(
            f"Temporary password for `{shown['username']}` (share out of band, shown once): `{shown['temp']}`"
        )
        st.caption("The user should change this password after signing in. It cannot be retrieved later.")
        if st.button("Hide temporary password"):
            st.session_state.pop("admin_temp_pw", None)
            st.rerun()


def _label(user_id: int, rows: list[dict]) -> str:
    for r in rows:
        if int(r["UserId"]) == int(user_id):
            return f"{r['Username']} ({r['Email']})"
    return str(user_id)
