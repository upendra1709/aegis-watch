import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from utils.data_utils import list_machines, get_machine_history
from utils.model_utils import (
    MODEL_METRICS, CONFUSION_MATRIX, FEATURE_IMPORTANCE, ROC_CURVE,
    MONTHLY_FAILURE_TREND, YEARLY_FAILURE_TREND, FAILURE_MODE_COUNTS, DATASET_INFO,
)
from components.widgets import kpi_card


def render():
    st.markdown("<div class='aw-title'>Analytics</div>", unsafe_allow_html=True)
    n_rows = DATASET_INFO.get("n_rows")
    subtitle = (f"AI model performance & sensor analytics — real evaluation results from the "
                f"XGBoost model trained on {n_rows:,} rows of ai4i2020_10k.csv" if n_rows else
                "AI model performance & sensor analytics")
    st.markdown(f"<div class='aw-sub'>{subtitle}</div>", unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    with c1: kpi_card("Accuracy", f"{MODEL_METRICS['accuracy']*100:.1f}%", "🎯", "#22c55e", key="ac")
    with c2: kpi_card("Precision", f"{MODEL_METRICS['precision']*100:.1f}%", "📐", "#3b82f6", key="pr")
    with c3: kpi_card("Recall", f"{MODEL_METRICS['recall']*100:.1f}%", "🔁", "#8b5cf6", key="re")
    with c4: kpi_card("F1 Score", f"{MODEL_METRICS['f1_score']*100:.1f}%", "⚖️", "#f59e0b", key="f1")

    st.write("")
    r1, r2 = st.columns(2)

    with r1:
        with st.container(border=True):
            st.markdown("<div class='aw-card-title'>Confusion Matrix</div>", unsafe_allow_html=True)
            cm = CONFUSION_MATRIX
            fig = go.Figure(data=go.Heatmap(
                z=cm["matrix"], x=cm["labels"], y=cm["labels"],
                colorscale="Blues", text=cm["matrix"], texttemplate="%{text}",
            ))
            fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10),
                               paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#cbd5e1"),
                               xaxis_title="Predicted", yaxis_title="Actual")
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with r2:
        with st.container(border=True):
            st.markdown("<div class='aw-card-title'>ROC Curve</div>", unsafe_allow_html=True)
            roc = ROC_CURVE
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=roc["fpr"], y=roc["tpr"], mode="lines", line=dict(color="#f97316", width=3),
                                      name=f"AUC = {roc['auc']}"))
            fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines", line=dict(color="#475569", width=1, dash="dot"),
                                      showlegend=False))
            fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10),
                               paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                               font=dict(color="#cbd5e1"), xaxis_title="False Positive Rate", yaxis_title="True Positive Rate",
                               xaxis=dict(gridcolor="rgba(255,255,255,0.06)"), yaxis=dict(gridcolor="rgba(255,255,255,0.06)"),
                               legend=dict(font=dict(color="#cbd5e1")))
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    r3, r4 = st.columns(2)
    with r3:
        with st.container(border=True):
            st.markdown("<div class='aw-card-title'>Feature Importance</div>", unsafe_allow_html=True)
            fi = FEATURE_IMPORTANCE
            fig = go.Figure(go.Bar(x=fi["importance"], y=fi["features"], orientation="h", marker_color="#3b82f6"))
            fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10),
                               paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                               font=dict(color="#cbd5e1"), xaxis=dict(gridcolor="rgba(255,255,255,0.06)"))
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with r4:
        with st.container(border=True):
            st.markdown("<div class='aw-card-title'>SHAP Feature Importance (Placeholder)</div>", unsafe_allow_html=True)
            st.caption("Swap this for real SHAP values once you compute them with `shap.Explainer`.")
            fi = FEATURE_IMPORTANCE
            fig = go.Figure(go.Bar(x=[v * 0.8 for v in fi["importance"]], y=fi["features"], orientation="h", marker_color="#8b5cf6"))
            fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10),
                               paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                               font=dict(color="#cbd5e1"), xaxis=dict(gridcolor="rgba(255,255,255,0.06)"))
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # ---- Sensor trends + feature correlation ----
    r5, r6 = st.columns(2)
    with r5:
        with st.container(border=True):
            st.markdown("<div class='aw-card-title'>Sensor Trends (all machines, process temperature)</div>", unsafe_allow_html=True)
            fig = go.Figure()
            for m in list_machines()[:5]:
                df = get_machine_history(m["id"])
                fig.add_trace(go.Scatter(x=df["timestamp"], y=df["process_temp"], mode="lines", name=m["name"]))
            fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10),
                               paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                               font=dict(color="#cbd5e1"), legend=dict(font=dict(color="#cbd5e1", size=10)),
                               xaxis=dict(gridcolor="rgba(255,255,255,0.06)"), yaxis=dict(gridcolor="rgba(255,255,255,0.06)"))
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with r6:
        with st.container(border=True):
            st.markdown("<div class='aw-card-title'>Feature Correlation</div>", unsafe_allow_html=True)
            all_df = pd.concat([get_machine_history(m["id"]) for m in list_machines()], ignore_index=True)
            corr = all_df[["air_temp", "process_temp", "rpm", "torque", "tool_wear"]].corr()
            fig = go.Figure(data=go.Heatmap(z=corr.values, x=corr.columns, y=corr.columns,
                                             colorscale="RdBu", zmid=0, text=corr.round(2).values, texttemplate="%{text}"))
            fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10),
                               paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#cbd5e1"))
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # ---- Failure distribution + monthly/yearly trend ----
    r7, r8, r9 = st.columns(3)
    with r7:
        with st.container(border=True):
            st.markdown("<div class='aw-card-title'>Failure Distribution (real counts, ai4i2020_10k.csv)</div>", unsafe_allow_html=True)
            mode_labels = {"TWF": "Tool Wear", "HDF": "Heat Dissipation", "PWF": "Power Failure",
                           "OSF": "Overstrain", "RNF": "Random Failure"}
            labels = [mode_labels[k] for k in FAILURE_MODE_COUNTS]
            values = list(FAILURE_MODE_COUNTS.values())
            fig = go.Figure(data=[go.Pie(labels=labels,
                                          values=values, hole=0.5,
                                          marker=dict(colors=["#ef4444", "#f59e0b", "#3b82f6", "#8b5cf6", "#64748b"]))])
            fig.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor="rgba(0,0,0,0)",
                               font=dict(color="#cbd5e1"))
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with r8:
        with st.container(border=True):
            st.markdown("<div class='aw-card-title'>Monthly Failure Trend</div>", unsafe_allow_html=True)
            st.caption("Illustrative — ai4i2020_10k.csv has no timestamps, so no real monthly trend can be derived from it.")
            mt = MONTHLY_FAILURE_TREND
            fig = go.Figure(go.Bar(x=mt["months"], y=mt["failures"], marker_color="#f97316"))
            fig.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10),
                               paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#cbd5e1"),
                               xaxis=dict(gridcolor="rgba(255,255,255,0.06)"), yaxis=dict(gridcolor="rgba(255,255,255,0.06)"))
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with r9:
        with st.container(border=True):
            st.markdown("<div class='aw-card-title'>Yearly Failure Trend</div>", unsafe_allow_html=True)
            st.caption("Illustrative — same reason as above.")
            yt = YEARLY_FAILURE_TREND
            fig = go.Figure(go.Scatter(x=yt["years"], y=yt["failures"], mode="lines+markers",
                                        line=dict(color="#22c55e", width=3)))
            fig.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10),
                               paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#cbd5e1"),
                               xaxis=dict(gridcolor="rgba(255,255,255,0.06)"), yaxis=dict(gridcolor="rgba(255,255,255,0.06)"))
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
