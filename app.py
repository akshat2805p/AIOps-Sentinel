import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
from pathlib import Path

st.set_page_config(
    page_title="AIOps Sentinel",
    page_icon="🛡️",
    layout="wide",
)

st.title("🛡️ AIOps Sentinel")
st.caption("Autonomous Server Anomaly Detection & Incident-Risk Analysis Platform")

project_summary = """AIOps Sentinel is a production-grade server telemetry and anomaly detection platform designed to solve these challenges.
It ingests high-frequency system telemetry, transforms raw metrics into 54 temporal rolling features,
detects abnormal multivariate behavior using an unsupervised Isolation Forest model trained from scratch."""

st.markdown(project_summary)

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Telemetry Features", "54")
with col2:
    st.metric("Detection Model", "Isolation Forest")
with col3:
    st.metric("Alert Engine", "Cooldown + N=2")
with col4:
    st.metric("Deployment", "Streamlit Ready")

sidebar = st.sidebar
sidebar.title("Navigation")
page = sidebar.radio(
    "Choose a section",
    ["Overview", "Architecture", "ML Pipeline", "Sample Dashboard", "Deployment"],
    index=0,
)

if page == "Overview":
    st.subheader("Project Overview")
    st.markdown(
        """
        - Ingests system telemetry from Linux hosts, synthetic clusters, or collectors.
        - Converts raw values into temporal rolling statistics and lag-based feature windows.
        - Detects subtle multivariate anomalies before they become outages.
        - Stores and exposes monitoring results through a structured backend API.
        - Provides a high-contrast operational dashboard with alert, host, and incident views.
        """
    )

    repo_root = Path('.')
    entries = [p.name for p in repo_root.iterdir() if not p.name.startswith('.')][:20]
    with st.expander("Repository structure"):
        st.code("\n".join(sorted(entries)))

    st.subheader("Key highlights")
    st.markdown(
        """
        - 54 temporal rolling features and rate-of-change lags
        - Unsupervised anomaly detection using Isolation Forest
        - PostgreSQL + SQLite failover database architecture
        - HTTP security validation middleware
        - Risk-based alerting and operational simulation
        """
    )

elif page == "Architecture":
    st.subheader("System Architecture")
    st.markdown(
        """
        Data sources feed telemetry into validation and ingestion layers, where metrics are transformed and passed
        through a feature engine and anomaly model. The final outputs flow into the database, alert pipeline, and UI.
        """
    )

    architecture = {
        "Telemetry Sources": ["Linux / psutil collectors", "Synthetic anomaly generators", "Cluster simulation"],
        "Ingestion + Security": ["Metric validation", "HTTP security headers", "CORS and sanitization"],
        "Core ML Engine": ["54 rolling features", "Isolation Forest detection", "Risk predictor"],
        "Storage + API": ["PostgreSQL / SQLite", "FastAPI REST endpoints", "Alert history"],
        "Frontend": ["Web dashboard", "Operational HUD", "Monitoring UI"],
    }

    for section, items in architecture.items():
        with st.container():
            st.markdown(f"### {section}")
            st.write("• " + "\n• ".join(items))

elif page == "ML Pipeline":
    st.subheader("ML Pipeline")
    st.markdown(
        """
        The ML pipeline is designed to learn normal operational baselines and identify deviations in a way that reduces false alarms.
        """
    )

    st.markdown("### Feature engineering")
    st.write(
        "Raw telemetry is converted into temporal rolling means, variances, lag-based diffs, and behavior indicators across multiple windows."
    )

    st.markdown("### Model training")
    st.write(
        "An Isolation Forest model is trained on chronologically split data to avoid leakage and overfitting. The system then scores incoming telemetry and triggers alerts when thresholds and suppression rules are satisfied."
    )

    st.markdown("### Resulting behavior")
    st.write(
        "This yields a better balance of sensitivity and operational stability than static z-score thresholding alone."
    )

elif page == "Sample Dashboard":
    st.subheader("Sample Telemetry Dashboard")

    def make_sample_data():
        rng = np.random.default_rng(42)
        minutes = pd.date_range("2026-01-01", periods=120, freq="min")
        cpu = np.linspace(35, 72, 120) + rng.normal(0, 7, 120)
        cpu[-15:] += 25
        memory = np.linspace(50, 74, 120) + rng.normal(0, 5, 120)
        memory[-20:] += 20
        latency = np.linspace(120, 180, 120) + rng.normal(0, 18, 120)
        latency[-10:] += 100
        error_rate = np.linspace(0.01, 0.08, 120) + rng.normal(0, 0.01, 120)
        error_rate = np.clip(error_rate, 0, 0.25)
        df = pd.DataFrame(
            {
                "timestamp": minutes,
                "cpu_percent": np.clip(cpu, 0, 100),
                "memory_percent": np.clip(memory, 0, 100),
                "request_latency_ms": np.clip(latency, 0, None),
                "error_rate": np.clip(error_rate, 0, 1),
            }
        )
        df["anomaly_flag"] = False
        df.loc[df.index[-15:], "anomaly_flag"] = True
        return df

    telemetry = make_sample_data()

    st.dataframe(telemetry.head(10), use_container_width=True)

    fig, ax = plt.subplots(2, 1, figsize=(12, 6), sharex=True)
    ax[0].plot(telemetry["timestamp"], telemetry["cpu_percent"], label="CPU %", color="#4f46e5")
    ax[0].plot(telemetry["timestamp"], telemetry["memory_percent"], label="Memory %", color="#f59e0b")
    ax[0].axvspan(telemetry["timestamp"].iloc[-15], telemetry["timestamp"].iloc[-1], color="red", alpha=0.15)
    ax[0].legend()
    ax[0].set_title("CPU and Memory Trends")

    ax[1].plot(telemetry["timestamp"], telemetry["request_latency_ms"], label="Latency (ms)", color="#10b981")
    ax[1].plot(telemetry["timestamp"], telemetry["error_rate"] * 300, label="Error Rate x300", color="#ef4444", linestyle="--")
    ax[1].axvspan(telemetry["timestamp"].iloc[-15], telemetry["timestamp"].iloc[-1], color="red", alpha=0.15)
    ax[1].legend()
    ax[1].set_title("Latency and Error Signal")

    fig.autofmt_xdate()
    st.pyplot(fig)

    alert_summary = pd.DataFrame(
        {
            "Host": ["server-01", "server-02", "server-03"],
            "Severity": ["Critical", "Warning", "Normal"],
            "Status": ["Triggered", "Monitoring", "Healthy"],
        }
    )
    st.table(alert_summary)

else:
    st.subheader("Deployment Instructions")
    st.markdown(
        """
        This repository is prepared so it can be deployed on Streamlit.

        1. Install Python dependencies.
        2. Run the app locally with `streamlit run app.py`.
        3. On Streamlit Cloud, connect the GitHub repo and use `app.py` as the app entry point.
        """
    )

    st.code("""
    pip install -r requirements.txt
    streamlit run app.py
    """)

    st.markdown("### Recommended hosting setup")
    st.write(
        "Set the app entry file to `app.py` at the repository root and keep the `requirements.txt` file in the same folder."
    )

st.sidebar.markdown("---")
st.sidebar.markdown("### Project tags")
st.sidebar.write("• AIOps")
st.sidebar.write("• Anomaly Detection")
st.sidebar.write("• Isolation Forest")
st.sidebar.write("• FastAPI")
st.sidebar.write("• Monitoring")

st.markdown("---")
st.caption("Built for deployment with Streamlit Cloud or a standard Python hosting environment.")
