import streamlit as st
import pandas as pd
import io

from utils.data_utils import list_machines, get_latest_reading, log_activity
from utils.model_utils import predict_health
from utils.pdf_utils import generate_pdf_report


def render():
    st.markdown("<div class='aw-title'>Reports</div>", unsafe_allow_html=True)
    st.markdown("<div class='aw-sub'>Generate and export machine health reports</div>", unsafe_allow_html=True)

    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            period = st.selectbox("Report Period", ["Daily", "Weekly", "Monthly", "Yearly"])
        with c2:
            group_by = st.selectbox("Group By", ["Machine-wise", "Department-wise"])
        with c3:
            export_format = st.selectbox("Export Format", ["CSV", "Excel"])

        machines = list_machines()
        rows = []
        for m in machines:
            latest = get_latest_reading(m["id"])
            health = predict_health(latest)
            rows.append({
                "Machine": m["name"],
                "Department": "Machining" if "CNC" in m["name"] or "Mill" in m["name"] else "Operations",
                "Status": health["status"],
                "Health Score": health["score"],
                "Air Temp (K)": latest["air_temp"],
                "Process Temp (K)": latest["process_temp"],
                "RPM": latest["rpm"],
                "Report Period": period,
            })
        df = pd.DataFrame(rows)
        if group_by == "Department-wise":
            df = df.sort_values("Department")

        st.dataframe(df, use_container_width=True, hide_index=True)

        dl1, dl2 = st.columns(2)
        with dl1:
            if export_format == "CSV":
                st.download_button("⬇ Download Report (CSV)", df.to_csv(index=False),
                                    file_name=f"aegis_watch_{period.lower()}_report.csv", mime="text/csv",
                                    use_container_width=True)
            else:
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                    df.to_excel(writer, index=False, sheet_name="Report")
                st.download_button("⬇ Download Report (Excel)", buf.getvalue(),
                                    file_name=f"aegis_watch_{period.lower()}_report.xlsx",
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                    use_container_width=True)
        with dl2:
            if st.button("📄 Generate PDF Report", use_container_width=True):
                pdf_bytes = generate_pdf_report(
                    df, title=f"{period} Report — {group_by}",
                    subtitle=f"{len(df)} machines included",
                )
                st.session_state["pdf_report_bytes"] = pdf_bytes
                st.session_state["pdf_report_name"] = f"aegis_watch_{period.lower()}_report.pdf"
                log_activity("PDF_REPORT", detail=f"{period} / {group_by} ({len(df)} machines)")
                st.success("✅ PDF generated — click below to download.")

            if st.session_state.get("pdf_report_bytes"):
                st.download_button(
                    "⬇ Download PDF Report", st.session_state["pdf_report_bytes"],
                    file_name=st.session_state["pdf_report_name"], mime="application/pdf",
                    use_container_width=True,
                )

    st.write("")
    st.markdown("<div class='aw-card-title'>Quick Machine Reports</div>", unsafe_allow_html=True)
    for m in machines:
        latest = get_latest_reading(m["id"])
        health = predict_health(latest)
        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 2, 1.2])
            c1.markdown(f"**{m['icon']} {m['name']}**")
            c2.markdown(f"Status: **{health['status']}** &nbsp;·&nbsp; Score: **{health['score']}/100**")
            single_df = pd.DataFrame([rows[machines.index(m)]])
            c3.download_button("⬇ CSV", single_df.to_csv(index=False), file_name=f"{m['id']}_report.csv",
                                mime="text/csv", key=f"rep_{m['id']}", use_container_width=True)
