import json
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st

from agents import distance_km
from data_loader import load_data
from simulation import Simulation, evaluate, scenario_reading


st.set_page_config(page_title="Raqeeb | رقيب", page_icon="💧", layout="wide")
st.markdown(f"<style>{Path(__file__).with_name('style.css').read_text()}</style>", unsafe_allow_html=True)


@st.cache_data
def dataset():
    return load_data()


try:
    readings, labels = dataset()
except (OSError, ValueError) as error:
    st.error(f"Could not load data: {error}")
    st.stop()

st.markdown("""
<div class="raqeeb-header">
  <div class="raqeeb-mark" aria-hidden="true">
    <svg width="36" height="44" viewBox="0 0 36 44" fill="none">
      <path d="M18 2C15 9 3 20 3 28a15 15 0 0 0 30 0C33 20 21 9 18 2Z" fill="#7EC8FF"/>
      <path d="M11 29l5 5 10-12" stroke="#103D70" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
  </div>
  <div><small>WATER NETWORK MONITORING</small>
    <h1>Raqeeb <span lang="ar">| رقيب</span></h1>
    <p>Water leak monitoring and maintenance dispatch · University simulation</p>
  </div>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown('<div class="raqeeb-side">Raqeeb | رقيب</div>', unsafe_allow_html=True)
    st.caption("Simulation settings")
    st.subheader("1 · Choose a reading")
    source = st.radio("Reading source", ["Scenarios", "Dataset"])
    scenario = st.selectbox("Scenario", ["Normal", "Minor leak", "Major leak + team failure"],
                            disabled=source != "Scenarios")
    row_number = st.number_input("Dataset row", 1, len(readings), 1, disabled=source != "Dataset")
    st.caption("Scenario examples use the default limits. Changed limits can change their outcome.")
    st.divider()
    st.subheader("2 · Detection limits")
    pressure_limit = st.slider("Low pressure below (PSI)", 30, 70, 54)
    flow_limit = st.slider("High flow above (L/min)", 50, 120, 90)
    major_limit = st.slider("Major leak pressure at or below (PSI)", 20, pressure_limit - 1,
                            min(40, pressure_limit - 1))
    repair_ticks = st.slider("Repair duration (steps)", 3, 20, 8)
    st.divider()
    st.subheader("3 · Team conditions")
    fail_first = st.checkbox("Fail Team A after assignment", value=scenario == "Major leak + team failure")
    unavailable = st.checkbox("Both teams unavailable")
    if st.button("Load / Reset", width="stretch", type="primary") or "sim" not in st.session_state:
        if source == "Scenarios":
            index, reading = scenario_reading(readings, scenario)
        else:
            index, reading = int(row_number) - 1, readings[int(row_number) - 1]
        st.session_state.sim = Simulation(reading, pressure_limit, flow_limit, major_limit,
                                          repair_ticks, fail_first, unavailable)
        st.session_state.row = index + 1
        st.session_state.running = False
    st.info("Change settings, then press Load / Reset to apply them.")


@st.fragment(run_every=0.5)
def dashboard():
    sim = st.session_state.sim
    st.subheader("Simulation controls")
    columns = st.columns(3)
    if columns[0].button("Run", width="stretch", type="primary"):
        sim.start()
        st.session_state.running = True
    if columns[1].button("Pause", width="stretch"):
        st.session_state.running = False
    if columns[2].button("Next step", width="stretch"):
        st.session_state.running = False
        sim.start()
        sim.step()
    if st.session_state.running and sim.active:
        sim.step()
    if not sim.active:
        st.session_state.running = False

    st.markdown(f'<div class="raqeeb-status"><small>Current result</small><h3>{escape(sim.result)}</h3></div>',
                unsafe_allow_html=True)
    st.caption(f"Loaded row {st.session_state.row} · Step {sim.step_number} · "
               f"Limits: pressure < {sim.pressure_limit} PSI and flow > {sim.flow_limit} L/min · "
               f"Major pressure ≤ {sim.major_limit} PSI")
    st.subheader("Reading overview")
    a, b, c, d = st.columns(4)
    a.metric("Pressure (PSI)", f"{sim.reading['Pressure']:.2f}")
    b.metric("Flow (L/min)", f"{sim.reading['Flow_Rate']:.2f}")
    c.metric("Leak confirmed", "Yes" if sim.detected else "No")
    d.metric("Repair", "Completed" if sim.repaired else "Pending" if sim.detected else "—")

    if sim.waiting_approval:
        st.warning("Major leak. Supervisor approval is needed before dispatch.")
        yes, no = st.columns(2)
        if yes.button("Approve dispatch", width="stretch", type="primary"):
            sim.approve(True)
            st.session_state.running = True
            st.rerun(scope="fragment")
        if no.button("Reject dispatch", width="stretch"):
            sim.approve(False)
            st.session_state.running = True
            st.rerun(scope="fragment")

    st.divider()
    left, right = st.columns([1, 1.4])
    with left, st.container(border=True):
        st.subheader("Agent status")
        st.dataframe(pd.DataFrame([{"Agent": agent.name, "Status": agent.status}
                                   for agent in sim.agents.values()]), hide_index=True,
                     width="stretch")
    with right, st.container(border=True):
        st.subheader("Incident and teams")
        st.write(" / ".join(sim.reading[key] for key in ("Zone", "Block", "Pipe")))
        points = [{"latitude": sim.reading["Latitude"], "longitude": sim.reading["Longitude"],
                   "Point": "Reading", "Distance (km)": 0.0}]
        points += [{"latitude": team.position[0], "longitude": team.position[1], "Point": team.name,
                    "Distance (km)": round(distance_km(team.position,
                        (sim.reading["Latitude"], sim.reading["Longitude"])), 3)}
                   for team in sim.teams]
        st.dataframe(pd.DataFrame(points), hide_index=True, width="stretch")
        st.map(pd.DataFrame(points), latitude="latitude", longitude="longitude", zoom=10, height=280)
        st.caption("Original synthetic incident coordinates; simulated team positions. Distance is straight-line, not road distance.")

    st.divider()
    st.subheader("Message log")
    log = [{**message, "content": json.dumps(message["content"], ensure_ascii=False)} for message in sim.messages]
    if log:
        st.dataframe(pd.DataFrame(log), hide_index=True, width="stretch", column_config={
            "step": "Step", "sender": "From", "receiver": "To", "performative": "Message type",
            "ontology": "Ontology", "conversation_id": "Conversation", "content": "Content",
            "delivered": "Delivered",
        })
    else:
        st.info("Press Run or Next step to start.")
    st.download_button("Download message log", json.dumps(sim.messages, indent=2),
                       file_name="raqeeb_messages.json", mime="application/json")


dashboard()

with st.expander("Dataset evaluation"):
    st.caption("Evaluation uses the loaded simulation limits on all 5,000 rows. These are rule-based synthetic labels; this is not a trained model or proof of real-world accuracy.")
    sim = st.session_state.sim
    scores = evaluate(readings, labels, sim.pressure_limit, sim.flow_limit)
    cards = st.columns(4)
    for card, key in zip(cards, ("accuracy", "precision", "recall", "f1")):
        card.metric("F1 score" if key == "f1" else key.title(), f"{scores[key]:.2%}")
    st.dataframe(pd.DataFrame([scores]), hide_index=True, width="stretch", column_config={
        "accuracy": st.column_config.NumberColumn("Accuracy", format="%.4f"),
        "precision": st.column_config.NumberColumn("Precision", format="%.4f"),
        "recall": st.column_config.NumberColumn("Recall", format="%.4f"),
        "f1": st.column_config.NumberColumn("F1", format="%.4f"),
    })
st.caption("Synthetic Kaggle data · Pressure and flow are the only sensor inputs · Leakage_Flag is used only for evaluation.")
