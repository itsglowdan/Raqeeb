import json
from html import escape
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from agents import distance_km
from data_loader import load_data
from monitoring import CITIES, ContinuousMonitor
from simulation import evaluate, scenario_reading


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

st.markdown('''
<div class="raqeeb-header">
 <div class="raqeeb-mark" aria-hidden="true"><svg width="36" height="44" viewBox="0 0 36 44" fill="none">
 <path d="M18 2C15 9 3 20 3 28a15 15 0 0 0 30 0C33 20 21 9 18 2Z" fill="#7EC8FF"/>
 <path d="M11 29l5 5 10-12" stroke="#103D70" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
 </svg></div>
 <div><small>WATER NETWORK MONITORING</small><h1>Raqeeb <span lang="ar">| رقيب</span></h1>
 <p>Continuous water leak monitoring and maintenance dispatch · University simulation</p></div>
</div>''', unsafe_allow_html=True)

with st.sidebar:
    st.markdown('<div class="raqeeb-side">Raqeeb | رقيب</div>', unsafe_allow_html=True)
    st.caption("Simulation settings")
    st.subheader("1 · Reading stream")
    source = st.radio("Reading source", ["Dataset", "Scenarios"])
    scenario = st.selectbox("Scenario", ["Normal", "Minor leak", "Major leak + team failure"],
                            disabled=source != "Scenarios")
    if source == "Dataset":
        row_number = st.number_input("Starting dataset row", 1, len(readings), 1)
    else:
        row_number = scenario_reading(readings, scenario)[0] + 1
        st.caption(f"Starting dataset row: {row_number}")
    interval = st.slider("Minimum reading interval (seconds)", 0.5, 5.0, 2.0, 0.5)
    st.caption("Starts at the selected row and stops at the last reading.")
    with st.expander("2 · Detection limits", expanded=False):
        pressure_limit = st.slider("Low pressure below (PSI)", 30, 70, 54)
        flow_limit = st.slider("High flow above (L/min)", 50, 120, 90)
        major_limit = st.slider("Major leak pressure at or below (PSI)", 20, pressure_limit - 1,
                                min(40, pressure_limit - 1))
        repair_ticks = st.slider("Repair duration (steps)", 3, 20, 8)
    with st.expander("3 · Team conditions", expanded=False):
        fail_first = st.checkbox("Fail Team A after assignment", value=scenario == "Major leak + team failure")
        unavailable = st.checkbox("Both teams unavailable")
        st.caption("Each city has two local teams. Failed teams remain unavailable until Reset.")
    if st.button("Load / Reset", width="stretch", type="primary") or "monitor" not in st.session_state:
        index = scenario_reading(readings, scenario)[0] if source == "Scenarios" else int(row_number) - 1
        st.session_state.monitor = ContinuousMonitor(
            readings, index, interval, pressure_limit, flow_limit, major_limit,
            repair_ticks, fail_first, unavailable)
        st.session_state.focus_city = readings[index]["Zone"]
        st.session_state.follow_live = False
    st.caption("Apply changes with Load / Reset.")


def trend(data, x, columns, y_title):
    frame = pd.DataFrame(data)
    melted = frame.melt(id_vars=[x], value_vars=columns, var_name="Series", value_name="Value")
    melted["Series"] = melted["Series"].replace({
        "confirmed": "Confirmed incidents", "completed": "Completed repairs",
        "messages": "Messages sent",
        "failures": "Team failures", "errors": "Execution errors",
    })
    return alt.Chart(melted).mark_line(point=True).encode(
        x=alt.X(f"{x}:Q", title="Simulation time (seconds)"),
        y=alt.Y("Value:Q", title=y_title, scale=alt.Scale(zero=False)),
        color=alt.Color("Series:N", scale=alt.Scale(range=["#1466C3", "#19A7A0", "#DC6A50"])),
        tooltip=[alt.Tooltip(f"{x}:Q", title="Simulation seconds"), "Series:N", "Value:Q"],
    ).properties(height=230)


def sensor_chart(frame, field, title, limit):
    chart = alt.Chart(frame).mark_line(point=True, color="#1466C3").encode(
        x=alt.X("seconds:Q", title="Simulation time (seconds)"),
        y=alt.Y(f"{field}:Q", title=title, scale=alt.Scale(zero=False)),
        tooltip=["seconds:Q", "row:Q", alt.Tooltip(f"{field}:Q", format=".2f")],
    )
    rule = alt.Chart(pd.DataFrame({"limit": [limit]})).mark_rule(
        color="#DC6A50", strokeDash=[6, 4]).encode(y="limit:Q", tooltip=["limit:Q"])
    return (chart + rule).properties(height=240)


def city_cards(monitor):
    st.subheader("Kingdom overview")
    st.caption("Virtual city networks")
    zones = list(CITIES)
    for group in (zones[:3], zones[3:]):
        columns = st.columns(len(group))
        for column, zone in zip(columns, group):
            city = monitor.cities[zone]
            status, task = monitor.city_status(zone)
            color = {"Normal": "normal", "Suspected": "suspected", "Confirmed leak": "leak"}.get(status, "empty")
            reading = city["latest"]
            pressure = f"{reading['Pressure']:.1f}" if reading else "—"
            flow = f"{reading['Flow_Rate']:.1f}" if reading else "—"
            latest_status = city["classification"]
            open_count = sum(key[0] == zone for key in monitor.open_incidents)
            with column:
                st.markdown(f'''<div class="city-card {color}">
                 <div class="city-heading"><h3>{CITIES[zone]['name']}</h3><span>{escape(status)}</span></div>
                 <p>{zone} · 5 blocks · {open_count} open incidents</p>
                 <div class="city-readings"><div><small>Pressure · PSI</small><strong>{pressure}</strong></div>
                 <div><small>Flow · L/min</small><strong>{flow}</strong></div></div>
                 <p>Latest reading: {escape(latest_status)}</p><div class="city-task">{escape(task)}</div>
                 </div>''', unsafe_allow_html=True)
                st.button(f"View {CITIES[zone]['name']}", key=f"view_{zone}", width="stretch",
                          on_click=select_city, args=(zone,))
    st.caption("Normal · Suspected · Confirmed leak")


def select_city(zone):
    st.session_state.focus_city = zone
    st.session_state.follow_live = False


def pin_city():
    st.session_state.follow_live = False


def live_agents(monitor):
    states = monitor.agent_states(monitor.focus_zone)
    active = {name for _, name in monitor.activity} if monitor.running else set()
    flow = []
    for name in ("Pressure Monitor", "Usage Monitor", "Leak Locator", "Dispatch", "Repair Teams"):
        working = name in active or (name == "Repair Teams" and bool(active & {"Team A", "Team B"}))
        flow.append(f'<span class="flow-node {"working" if working else ""}">{name}</span>')
    flow[0] += '<span class="flow-arrow"> ↔ </span>' + flow.pop(1)
    st.markdown('<div class="agent-flow">' + '<span class="flow-arrow">→</span>'.join(flow) + '</div>', unsafe_allow_html=True)
    names = list(states)
    for group in (names[:3], names[3:]):
        for column, name in zip(st.columns(3), group):
            working = name in active
            snapshot = monitor.role_states.get(name, {})
            status = snapshot.get("status", states[name])
            location = snapshot.get("city", "")
            with column:
                st.markdown(f'<div class="agent-card {"working" if working else ""}">'
                            f'<div class="agent-card-title"><span class="agent-dot"></span><strong>{name}</strong></div>'
                            f'<div class="agent-state">{escape(status)}</div>'
                            f'<small>{"Active now" if working else "Paused" if not monitor.running and monitor.observed else "Standing by"} · {location}</small></div>', unsafe_allow_html=True)
    recent = list(monitor.deliveries)[-3:]
    if recent:
        lines = [f'<div class="live-message"><strong>{escape(m["sender"])}</strong> → '
                 f'<strong>{escape(m["receiver"])}</strong><span>{escape(m["city"])} · {escape(m["performative"])}</span></div>' for m in reversed(recent)]
        st.markdown('<div class="live-messages">' + ''.join(lines) + '</div>', unsafe_allow_html=True)


@st.fragment(run_every=0.5)
def dashboard():
    monitor = st.session_state.monitor
    run, pause = st.columns(2)
    if run.button("Run", width="stretch", type="primary", disabled=monitor.finished):
        monitor.running = True
    if pause.button("Pause", width="stretch"):
        monitor.running = False
    monitor.advance()
    result = "All readings processed" if monitor.finished else "Running" if monitor.running else "Paused" if monitor.observed else "Ready"
    st.markdown(f'<div class="raqeeb-status"><h3>{result}</h3></div>', unsafe_allow_html=True)
    st.progress(monitor.processed / monitor.total_readings, text=f"Readings processed: {monitor.processed:,} / {monitor.total_readings:,}")
    a, b, c = st.columns(3)
    a.metric("Readings read", monitor.observed)
    b.metric("Open incidents", len(monitor.open_incidents))
    c.metric("Repairs completed", monitor.completed)
    if monitor.dropped:
        st.warning(f"Queue full: {monitor.dropped} incidents not admitted.")

    st.subheader("Live agents")
    live_agents(monitor)
    for zone, city in monitor.cities.items():
        incident = city["active"]
        if incident and incident["sim"].waiting_approval:
            st.warning(f"{CITIES[zone]['name']}: major leak at {incident['sim'].location['area']}. Approval required.")
            yes, no = st.columns(2)
            if yes.button(f"Approve dispatch · {CITIES[zone]['name']}", key=f"yes_{zone}", type="primary", width="stretch"):
                monitor.approve(zone, True)
                st.rerun(scope="fragment")
            if no.button(f"Reject dispatch · {CITIES[zone]['name']}", key=f"no_{zone}", width="stretch"):
                monitor.approve(zone, False)
                st.rerun(scope="fragment")

    st.divider()
    city_cards(monitor)
    st.divider()
    selection, follow = st.columns([2, 1])
    with follow:
        follow_live = st.checkbox("Follow active city", key="follow_live")
    if follow_live:
        st.session_state.focus_city = monitor.focus_zone
    with selection:
        zone = st.selectbox("City", list(CITIES), format_func=lambda key: CITIES[key]["name"], key="focus_city", on_change=pin_city)
    sim = monitor.selected_sim(zone)
    live, performance = st.tabs(["Pressure & flow", "Agent performance"])
    with live:
        frame = pd.DataFrame([row for row in monitor.history if row["city"] == CITIES[zone]["name"]])
        if not frame.empty:
            a, b = st.columns(2)
            with a:
                st.altair_chart(sensor_chart(frame, "Pressure", "Pressure (PSI)", monitor.settings["pressure_limit"]), width="stretch")
            with b:
                st.altair_chart(sensor_chart(frame, "Flow_Rate", "Flow (L/min)", monitor.settings["flow_limit"]), width="stretch")
            st.caption("Dashed line: detection limit · Simulation time")
        else:
            st.info("No reading for this city yet. Run the stream or choose another city.")
        if monitor.performance:
            st.altair_chart(trend(list(monitor.performance), "seconds", ["confirmed", "completed"], "Incidents / repairs (all cities)"), width="stretch")
    with performance:
        a, b, c, d = st.columns(4)
        a.metric("Messages sent", monitor.total_messages)
        b.metric("Agent calls", monitor.total_calls)
        c.metric("Team failures", monitor.failure_count)
        d.metric("Execution errors", monitor.error_count)
        st.metric("Average agent execution (ms)", f"{monitor.total_duration_ms / max(1, monitor.total_calls):.5f}")
        if monitor.traces:
            trace_frame = pd.DataFrame(monitor.traces)
            grouped = trace_frame.groupby(["seconds", "agent"], as_index=False)["duration_ms"].mean()
            chart = alt.Chart(grouped).mark_line(point=True).encode(
                x=alt.X("seconds:Q", title="Simulation time (seconds)"),
                y=alt.Y("duration_ms:Q", title="Mean execution time (ms)"), color="agent:N",
                tooltip=["seconds:Q", "agent:N", "duration_ms:Q"]).properties(height=250)
            st.altair_chart(chart, width="stretch")
            st.dataframe(trace_frame, hide_index=True, width="stretch")
        if monitor.performance:
            count, faults = st.columns(2)
            with count:
                st.altair_chart(trend(list(monitor.performance), "seconds", ["messages"], "Messages sent (all cities)"), width="stretch")
            with faults:
                st.altair_chart(trend(list(monitor.performance), "seconds", ["failures", "errors"], "Failures / errors (all cities)"), width="stretch")
    st.divider()
    details, messages, incidents, evaluation = st.tabs(["Map", "Message log", "Incidents", "Dataset evaluation"])
    with details:
        with st.container(border=True):
            st.subheader("Incident and teams")
            if sim:
                st.write(" / ".join(sim.reading[key] for key in ("Zone", "Block", "Pipe")))
                points = [{"latitude": sim.reading["Latitude"], "longitude": sim.reading["Longitude"], "Point": "Incident / reading", "Distance (km)": 0.0}]
                points += [{"latitude": t.position[0], "longitude": t.position[1], "Point": t.name,
                            "Distance (km)": round(distance_km(t.position, (sim.reading["Latitude"], sim.reading["Longitude"])), 3)} for t in sim.teams]
                st.dataframe(pd.DataFrame(points), hide_index=True, width="stretch")
            else:
                points = [{"latitude": CITIES[zone]["latitude"], "longitude": CITIES[zone]["longitude"], "Point": CITIES[zone]["name"]}]
            st.map(pd.DataFrame(points), latitude="latitude", longitude="longitude", zoom=11, height=280)
            st.caption("Virtual Saudi locations · Straight-line distances")
    with messages:
        st.subheader("Message log")
        log = [{**m, "content": json.dumps(m["content"], ensure_ascii=False)} for m in monitor.messages]
        if log:
            st.dataframe(pd.DataFrame(log), hide_index=True, width="stretch", column_config={
                "sender": "From", "receiver": "To", "performative": "Message type", "content": "Content", "seconds": "Simulation seconds"})
        else:
            st.info("Press Run to start.")
        st.download_button("Download message log", json.dumps(list(monitor.messages), indent=2), file_name="raqeeb_messages.json", mime="application/json")

    with incidents:
        recent = {item["id"]: item for item in monitor.incidents}
        recent.update({item["id"]: item for item in monitor.open_incidents.values()})
        rows = [{"ID": item["id"], "City": CITIES[item["zone"]]["name"],
                 "Pipe": "/".join(item["key"]), "Status": item["status"],
                 "Created (s)": item["created_seconds"], "Finished (s)": item["finished_seconds"]} for item in recent.values()]
        if rows:
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        else:
            st.info("No confirmed incidents yet.")

    with evaluation:

        scores = evaluate(readings, labels, monitor.settings["pressure_limit"], monitor.settings["flow_limit"])
        for card, key in zip(st.columns(4), ("accuracy", "precision", "recall", "f1")):
            card.metric("F1 score" if key == "f1" else key.title(), f"{scores[key]:.2%}")
        st.dataframe(pd.DataFrame([scores]), hide_index=True, width="stretch")



dashboard()
