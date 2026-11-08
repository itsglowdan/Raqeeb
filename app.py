import json

import pandas as pd
import streamlit as st

from agents import distance_km
from data_loader import load_data
from simulation import Simulation, evaluate, scenario_reading


st.set_page_config(page_title="Raqeeb", page_icon="💧", layout="wide")


@st.cache_data
def dataset():
    return load_data()


try:
    readings, labels = dataset()
except (OSError, ValueError) as error:
    st.error(f"Could not load data: {error}")
    st.stop()

st.title("Raqeeb | رقيب")
st.caption("Water leak monitoring and maintenance dispatch · University simulation")

with st.sidebar:
    st.header("Simulation settings")
    source = st.radio("Reading source", ["Scenarios", "Dataset"])
    scenario = st.selectbox("Scenario", ["Normal", "Minor leak", "Major leak + team failure"],
                            disabled=source != "Scenarios")
    row_number = st.number_input("Dataset row", 1, len(readings), 1, disabled=source != "Dataset")
    st.caption("Scenario examples use the default limits. Changed limits can change their outcome.")
    pressure_limit = st.slider("Low pressure below (PSI)", 30, 70, 54)
    flow_limit = st.slider("High flow above (L/min)", 50, 120, 90)
    major_limit = st.slider("Major leak pressure at or below (PSI)", 20, pressure_limit - 1,
                            min(40, pressure_limit - 1))
    repair_ticks = st.slider("Repair duration (steps)", 3, 20, 8)
    fail_first = st.checkbox("Fail Team A after assignment", value=scenario == "Major leak + team failure")
    unavailable = st.checkbox("Both teams unavailable")
    if st.button("Load / Reset", width="stretch") or "sim" not in st.session_state:
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
    columns = st.columns(3)
    if columns[0].button("Run", width="stretch"):
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

    st.subheader(sim.result)
    st.caption(f"Loaded row {st.session_state.row} · Step {sim.step_number} · "
               f"Limits: pressure < {sim.pressure_limit} PSI and flow > {sim.flow_limit} L/min · "
               f"Major pressure ≤ {sim.major_limit} PSI")
    a, b, c, d = st.columns(4)
    a.metric("Pressure (PSI)", f"{sim.reading['Pressure']:.2f}")
    b.metric("Flow (L/min)", f"{sim.reading['Flow_Rate']:.2f}")
    c.metric("Leak confirmed", "Yes" if sim.detected else "No")
    d.metric("Repair", "Completed" if sim.repaired else "Pending" if sim.detected else "—")

    if sim.waiting_approval:
        st.warning("Major leak. Supervisor approval is needed before dispatch.")
        yes, no = st.columns(2)
        if yes.button("Approve dispatch", width="stretch"):
            sim.approve(True)
            st.session_state.running = True
            st.rerun(scope="fragment")
        if no.button("Reject dispatch", width="stretch"):
            sim.approve(False)
            st.session_state.running = True
            st.rerun(scope="fragment")

    left, right = st.columns([1, 1.4])
    with left:
        st.subheader("Agent status")
        st.dataframe(pd.DataFrame([{"Agent": agent.name, "Status": agent.status}
                                   for agent in sim.agents.values()]), hide_index=True,
                     width="stretch")
    with right:
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

    st.subheader("Message log")
    log = [{**message, "content": json.dumps(message["content"], ensure_ascii=False)} for message in sim.messages]
    if log:
        st.dataframe(pd.DataFrame(log), hide_index=True, width="stretch")
    else:
        st.info("Press Run or Next step to start.")
    st.download_button("Download message log", json.dumps(sim.messages, indent=2),
                       file_name="raqeeb_messages.json", mime="application/json")


dashboard()

with st.expander("Dataset evaluation"):
    st.caption("Evaluation uses the loaded simulation limits on all 5,000 rows. These are rule-based synthetic labels; this is not a trained model or proof of real-world accuracy.")
    sim = st.session_state.sim
    scores = evaluate(readings, labels, sim.pressure_limit, sim.flow_limit)
    st.dataframe(pd.DataFrame([scores]), hide_index=True, width="stretch")
st.caption("Synthetic Kaggle data · Pressure and flow are the only sensor inputs · Leakage_Flag is used only for evaluation.")
