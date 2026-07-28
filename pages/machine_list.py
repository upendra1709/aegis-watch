import streamlit as st
import pandas as pd
from datetime import date

from utils.data_utils import (
    list_machines, get_latest_reading, get_machine_info,
    add_machine, update_machine, delete_machine,
)
from utils.db_utils import CATEGORY_ICONS, DEFAULT_READING_BY_TYPE
from utils.model_utils import predict_health
from components.widgets import machine_card


def render(go_to_detail):
    st.markdown("<div class='aw-title'>My Machines</div>", unsafe_allow_html=True)
    st.markdown("<div class='aw-sub'>All connected machines and their live health status</div>", unsafe_allow_html=True)

    if "show_add_form" not in st.session_state:
        st.session_state.show_add_form = False
    if "confirm_delete_id" not in st.session_state:
        st.session_state.confirm_delete_id = None

    # ---- Toolbar: search / filter / sort / add / export ----
    t1, t2, t3, t4 = st.columns([3, 1.4, 1.4, 1.2])
    with t1:
        search = st.text_input(" Search machines", placeholder="Search by machine name...", label_visibility="collapsed")
    with t2:
        status_filter = st.selectbox("Filter", ["All Statuses", "Healthy", "Warning", "Critical"], label_visibility="collapsed")
    with t3:
        sort_by = st.selectbox("Sort", ["Sort: Name (A-Z)", "Sort: Health Score (High-Low)", "Sort: Health Score (Low-High)"],
                                label_visibility="collapsed")
    with t4:
        with st.container():
            st.markdown("<div class='aw-secondary-btn'>", unsafe_allow_html=True)
            if st.button("➕ Add Machine", use_container_width=True):
                st.session_state.show_add_form = not st.session_state.show_add_form
            st.markdown("</div>", unsafe_allow_html=True)

    # ---- Add Machine form ----
    if st.session_state.show_add_form:
        with st.container(border=True):
            st.markdown("<div class='aw-card-title'>➕ Add a New Machine</div>", unsafe_allow_html=True)
            st.markdown(
                "<div class='aw-muted'>Only the basics are required — a person setting this up usually "
                "knows the name and category, not raw sensor numbers. Sensor baselines below are "
                "auto-filled for you and can be adjusted, or left as-is until a real reading comes in.</div>",
                unsafe_allow_html=True,
            )
            st.write("")
            with st.form("add_machine_form", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                with c1:
                    name = st.text_input("Machine Name *", placeholder="e.g. Packaging Robot #2")
                with c2:
                    category = st.selectbox("Category (icon)", list(CATEGORY_ICONS.keys()))
                with c3:
                    machine_type = st.selectbox(
                        "Machine Type *", ["L", "M", "H"],
                        help="Low / Medium / High duty-class — matches the L/M/H tier the AI model was trained on. "
                             "If unsure, choose 'M' (Medium) as a safe default.",
                    )

                last_maintenance = st.date_input("Last Maintenance Date", value=date.today())

                with st.expander("⚙️ Advanced: starting sensor baseline (optional — auto-filled)"):
                    defaults = DEFAULT_READING_BY_TYPE[machine_type]
                    s1, s2, s3, s4, s5 = st.columns(5)
                    air_temp = s1.number_input("Air Temp (K)", value=float(defaults["air_temp"]), step=0.1)
                    process_temp = s2.number_input("Process Temp (K)", value=float(defaults["process_temp"]), step=0.1)
                    rpm = s3.number_input("RPM", value=float(defaults["rpm"]), step=10.0)
                    torque = s4.number_input("Torque (Nm)", value=float(defaults["torque"]), step=0.5)
                    tool_wear = s5.number_input("Tool Wear (min)", value=float(defaults["tool_wear"]), step=1.0)

                submitted = st.form_submit_button("✅ Add Machine", use_container_width=True)
                if submitted:
                    if not name.strip():
                        st.error("Machine name is required.")
                    else:
                        new_id = add_machine(
                            name=name.strip(),
                            icon=CATEGORY_ICONS[category],
                            machine_type=machine_type,
                            last_maintenance=last_maintenance,
                            reading={
                                "air_temp": air_temp, "process_temp": process_temp,
                                "rpm": rpm, "torque": torque, "tool_wear": tool_wear,
                            },
                        )
                        st.session_state.show_add_form = False
                        st.success(f"✅ {name} added as {new_id} — it now appears below with a live AI health score.")
                        st.rerun()

    machines = list_machines()
    results = []
    for m in machines:
        latest = get_latest_reading(m["id"])
        health = predict_health(latest)
        results.append({"machine": m, "latest": latest, "health": health})

    # filter
    if search:
        results = [r for r in results if search.lower() in r["machine"]["name"].lower()]
    if status_filter != "All Statuses":
        results = [r for r in results if r["health"]["status"] == status_filter]

    # sort
    if sort_by == "Sort: Name (A-Z)":
        results.sort(key=lambda r: r["machine"]["name"])
    elif sort_by == "Sort: Health Score (High-Low)":
        results.sort(key=lambda r: r["health"]["score"], reverse=True)
    else:
        results.sort(key=lambda r: r["health"]["score"])

    # export current view
    export_col1, export_col2 = st.columns([5, 1.2])
    with export_col2:
        export_df = pd.DataFrame([{
            "Machine": r["machine"]["name"], "Status": r["health"]["status"], "Score": r["health"]["score"],
            "Air Temp (K)": r["latest"]["air_temp"], "Process Temp (K)": r["latest"]["process_temp"],
            "RPM": r["latest"]["rpm"], "Torque": r["latest"].get("torque"), "Tool Wear": r["latest"].get("tool_wear"),
        } for r in results])
        st.download_button("⬇ Export Report", export_df.to_csv(index=False),
                            file_name="machine_list_report.csv", mime="text/csv", use_container_width=True)

    st.caption(f"Showing {len(results)} of {len(machines)} machines")

    if not results:
        st.markdown("<span class='aw-muted'>No machines match your search/filter.</span>", unsafe_allow_html=True)
        return

    cols = st.columns(3)
    for i, r in enumerate(results):
        with cols[i % 3]:
            machine_card(r["machine"], r["latest"], r["health"], on_click=go_to_detail, key=r["machine"]["id"])

    with st.expander("⚙️ Manage machines (edit / delete)"):
        for r in results:
            mid = r["machine"]["id"]
            c1, c2, c3 = st.columns([3, 1, 1])
            c1.markdown(f"**{r['machine']['name']}**")
            if c2.button("✏️ Edit", key=f"edit_{mid}"):
                st.session_state[f"editing_{mid}"] = not st.session_state.get(f"editing_{mid}", False)
            if c3.button("🗑️ Delete", key=f"del_{mid}"):
                st.session_state.confirm_delete_id = mid

            # ---- Inline edit form ----
            if st.session_state.get(f"editing_{mid}", False):
                info = get_machine_info(mid)
                with st.form(f"edit_form_{mid}"):
                    ec1, ec2, ec3 = st.columns(3)
                    new_name = ec1.text_input("Name", value=info["name"])
                    icon_names = list(CATEGORY_ICONS.keys())
                    current_icon_name = next((k for k, v in CATEGORY_ICONS.items() if v == info["icon"]), "Other")
                    new_category = ec2.selectbox("Category (icon)", icon_names, index=icon_names.index(current_icon_name))
                    new_type = ec3.selectbox("Machine Type", ["L", "M", "H"],
                                              index=["L", "M", "H"].index(info["machine_type"]))
                    new_last_maint = st.date_input("Last Maintenance Date",
                                                    value=pd.to_datetime(info["last_maintenance"]).date())
                    save = st.form_submit_button("💾 Save Changes")
                    if save:
                        update_machine(mid, name=new_name.strip(), icon=CATEGORY_ICONS[new_category],
                                        machine_type=new_type, last_maintenance=new_last_maint)
                        st.session_state[f"editing_{mid}"] = False
                        st.success(f"Updated {new_name}.")
                        st.rerun()

            # ---- Delete confirmation ----
            if st.session_state.confirm_delete_id == mid:
                st.warning(f"Delete **{r['machine']['name']}** permanently? This removes its history too.")
                dc1, dc2 = st.columns(2)
                if dc1.button("✅ Yes, delete", key=f"confirm_del_{mid}", use_container_width=True):
                    delete_machine(mid)
                    st.session_state.confirm_delete_id = None
                    st.success(f"{r['machine']['name']} deleted.")
                    st.rerun()
                if dc2.button("Cancel", key=f"cancel_del_{mid}", use_container_width=True):
                    st.session_state.confirm_delete_id = None
                    st.rerun()
