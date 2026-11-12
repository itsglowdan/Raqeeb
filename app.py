from dataclasses import asdict
from pathlib import Path
from html import escape
import json
import time
import altair as alt
import pandas as pd
import streamlit as st
from data_loader import load_data, filter_data, custom_reading, LABELS
from simulation import Simulation, Configuration, evaluate
from ui import geographic, table, agent_activity, messages
from controls import automatic_inputs, automatic_team_positions, assessment_status

st.set_page_config(page_title='Raqeeb | رقيب', page_icon='💧', layout='wide')
st.markdown(f"<style>{Path(__file__).with_name('style.css').read_text()}</style>", unsafe_allow_html=True)


@st.cache_data
def dataset():
    return load_data()


try:
    data = dataset()
except (ValueError, OSError) as error:
    st.error(str(error))
    st.stop()

for key, value in {'sequence': [], 'saved_runs': [], 'run': None, 'configuration': asdict(Configuration()),
                   'metadata': {}, 'last_tick': 0.0, 'focus_zone': 'Zone_1'}.items():
    if key not in st.session_state:
        st.session_state[key] = value
if 'pending_record' in st.session_state:
    st.session_state.selected_record = st.session_state.pop('pending_record')
st.session_state.classic_layout = True


def new_experiment():
    if st.session_state.run:
        st.session_state.saved_runs.append(st.session_state.run.export())
    st.session_state.run = None
    st.session_state.last_tick = 0.0


def pin_zone(zone):
    st.session_state.focus_zone = zone


run = st.session_state.run
selected = data
def readings_view(frame):
    if frame.empty:
        st.info('No matching readings')
        return
    st.caption(f'{len(frame):,} readings · select a row to link its exact map location')
    event = st.dataframe(frame.rename(columns=LABELS), hide_index=True, width='stretch', height=420,
                         on_select='rerun', selection_mode='single-row', key='readings_table',
                         column_config={LABELS['Pressure_PSI']: st.column_config.NumberColumn(format='%.2f'),
                                        LABELS['Flow_Rate_Lmin']: st.column_config.NumberColumn(format='%.2f'),
                                        LABELS['Vibration_mms']: st.column_config.NumberColumn(format='%.2f'),
                                        'Latitude': st.column_config.NumberColumn(format='%.6f'),
                                        'Longitude': st.column_config.NumberColumn(format='%.6f')})
    if event.selection.rows:
        st.session_state.pending_record = frame.iloc[event.selection.rows[0]].record_ref
    if st.button('Show selected record on map', disabled=not event.selection.rows):
        st.session_state.pending_page = 'Dashboard'
        st.rerun()

def settings_view():
    st.markdown('### Simulation settings')
    locked = bool(run and run.status == 'Running')
    if run:
        st.info('Configuration changes apply to a fresh experiment. Resume keeps the active run configuration.')
    source = st.radio('Data Source', ['Dataset Readings', 'Custom Readings'], key='input_source', disabled=locked)
    pressure = flow = None
    if source == 'Dataset Readings':
        st.caption('Dataset readings load automatically in their original order.')
    else:
        pressure = st.number_input('Pressure (PSI)', min_value=0.0, value=None, step=1.0, key='custom_pressure', disabled=locked)
        flow = st.number_input('Flow (L/min)', min_value=0.0, value=None, step=1.0, key='custom_flow', disabled=locked)
        st.caption('Custom simulation input · Location is assigned automatically.')
    st.session_state.sequence = automatic_inputs(data, source, pressure, flow)
    with st.expander('Agent Parameters · simulation configuration', expanded=False):
        st.caption('These are configurable demonstration rules, not official engineering safety limits. Changes take effect in a fresh run.')
        old = st.session_state.configuration
        a, b, c = st.container(), st.container(), st.container()
        pressure_limit = a.number_input('Low pressure below (PSI)', 1.0, 200.0, float(old['pressure_limit']), help='Pressure Monitor flags values strictly below this limit.', disabled=locked)
        flow_limit = b.number_input('High flow above (L/min)', 1.0, 300.0, float(old['flow_limit']), help='Usage Monitor flags values strictly above this limit.', disabled=locked)
        major_limit = c.number_input('Major pressure at or below (PSI)', 0.1, 199.0, float(old['major_limit']), help='Requires dual-rule confirmation first, then supervisor approval.', disabled=locked)
        a, b, c = st.container(), st.container(), st.container()
        timeout = a.number_input('Report timeout (execution steps)', 4, 100, old['timeout_steps'], help='Wait this many running steps for acknowledgment before retry.', disabled=locked)
        retries = b.number_input('Maximum report retries', 0, 5, old['retries'], help='Bounded extra attempts after the first request.', disabled=locked)
        duration = c.number_input('Simulated team task (steps)', 1, 30, old['team_steps'], disabled=locked)
        interval = st.slider('Playback interval (application seconds per execution step)', .5, 5.0, old['playback_interval'], .5, disabled=locked)
        st.caption('Pause freezes all agents, in-flight simulated work and timeout counters. Row order is not measurement time.')
        try:
            config = Configuration(**{**old, 'pressure_limit': pressure_limit, 'flow_limit': flow_limit, 'major_limit': major_limit,
                                      'timeout_steps': int(timeout), 'retries': int(retries), 'team_steps': int(duration), 'playback_interval': interval})
            st.session_state.configuration = asdict(config)
            st.session_state.configuration_valid = True
        except ValueError as error:
            st.session_state.configuration_valid = False
            st.error(str(error))
            st.caption('Invalid changes were not applied. The previous valid configuration remains active.')

def experiments_view():
    st.caption('Configure readings and parameters in Settings. No preset scenarios or scripted outcomes are loaded.')
    st.caption('Reading inputs and parameters are available in the sidebar.')
    locked = bool(run and run.status == 'Running')
    name = st.text_input('Experiment name (optional)', value=st.session_state.metadata.get('name', ''), disabled=locked)
    purpose = st.text_area('Purpose (optional)', value=st.session_state.metadata.get('purpose', ''), disabled=locked)
    expected = st.text_area('Expected outcome (optional)', value=st.session_state.metadata.get('expected_outcome', ''), disabled=locked)
    st.session_state.metadata = {'name': name, 'purpose': purpose, 'expected_outcome': expected}
    st.subheader('Failure and availability configuration')
    config = st.session_state.configuration
    a, b = st.columns(2)
    config['team_a_available'] = a.checkbox('Team A available', value=config['team_a_available'], disabled=locked)
    config['team_b_available'] = b.checkbox('Team B available', value=config['team_b_available'], disabled=locked)
    config['fail_team_a'] = st.checkbox('Fail Team A after assignment', value=config['fail_team_a'], disabled=locked)
    config['reporting_unavailable'] = st.checkbox('Reporting Agent unavailable', value=config['reporting_unavailable'], disabled=locked)
    config['reporting_silent'] = st.checkbox('Drop Reporting Agent acknowledgments', value=config['reporting_silent'], disabled=locked)
    st.caption('These deliberate agent faults apply to the next fresh run. They are unrelated to physical sensor connectivity.')
    if st.button('Start fresh experiment', disabled=locked):
        new_experiment()
        st.rerun()
    if run:
        st.write('Active run configuration')
        st.json({'configuration': asdict(run.config), 'metadata': run.metadata, 'team_references': run.positions}, expanded=False)
        st.caption(f'Active run inputs: {len(run.readings)} readings')
        if run.metadata.get('expected_outcome'):
            st.write('Expected outcome (user supplied):', run.metadata['expected_outcome'])
        st.markdown('**Observed results**')
        st.write(f'Status: {run.status} · assessments: {len(run.assessments)} · report records: {len(run.reports)}')
        if run.outcomes:
            st.write('Latest observed outcome:', run.outcomes[-1]['outcome'])
            table(pd.DataFrame(run.outcomes))
        if run.events:
            st.dataframe(pd.DataFrame(run.events), hide_index=True, width='stretch')
        for agent_name in ['Reporting Agent', 'Team A', 'Team B']:
            if st.button(f'Restore {agent_name}', disabled=run.status not in ['Running', 'Paused']):
                run.restore(agent_name)
                st.rerun()
        if st.button('Save experiment result'):
            st.session_state.saved_runs.append(run.export())
            st.success('Experiment snapshot saved for this browser session. Download it in Reports for permanent storage.')
        agent_activity(run)
        messages(run)
        st.download_button('Export experiment', json.dumps(run.export(), indent=2), f'raqeeb_{run.run_id}.json', 'application/json', on_click='ignore')
    else:
        st.info('Ready to run the configured sequence using the sidebar controls.')
    st.caption('At least three user-run experiments are needed for submission, including one failure or conflict. Expected outcomes are not execution results.')

with st.sidebar:
    st.markdown('<div class="raqeeb-side">Raqeeb | رقيب</div>', unsafe_allow_html=True)
    st.caption('Simulation settings')
    with st.expander('Reading source and inputs', expanded=True):
        settings_view()
    st.divider()
    current = st.session_state.run
    signature = json.dumps({'source': st.session_state.input_source, 'configuration': st.session_state.configuration,
                            'custom': [(r['Pressure_PSI'],r['Flow_Rate_Lmin']) for r in st.session_state.sequence] if st.session_state.input_source == 'Custom Readings' else None}, sort_keys=True)
    changed = bool(current and signature != st.session_state.get('loaded_signature'))
    st.caption('Execution: ' + (current.status if current else 'Ready'))
    a, b = st.columns(2)
    if a.button('Resume' if current and current.status == 'Paused' and not changed else 'Run', type='primary', width='stretch',
                disabled=bool(current and (current.status == 'Running' or (current.status in ['Completed','Failed'] and not changed))) or not st.session_state.sequence or not st.session_state.get('configuration_valid', True)):
        if changed:
            new_experiment()
            current = None
        if current is None:
            positions = automatic_team_positions(data)
            current = Simulation(st.session_state.sequence, Configuration(**st.session_state.configuration), st.session_state.metadata, positions)
            st.session_state.run = current
            st.session_state.focus_zone = current.readings[0]['Zone']
            st.session_state.loaded_signature = signature
        current.run()
        st.session_state.last_tick = time.monotonic()
        st.rerun()
    if b.button('Pause', width='stretch', disabled=not current or current.status != 'Running'):
        current.pause()
        st.rerun()
    if st.button('Load / Reset', width='stretch', disabled=bool(current and current.status == 'Running')):
        new_experiment()
        st.rerun()

run = st.session_state.run


@st.fragment(run_every=.5 if run and run.status == 'Running' else None)
def heartbeat():
    active = st.session_state.run
    if active and active.status == 'Running' and time.monotonic()-st.session_state.last_tick >= active.config.playback_interval:
        active.tick()
        st.session_state.last_tick = time.monotonic()
        st.rerun()


heartbeat()
st.markdown('''<div class="raqeeb-header"><div><small>WATER NETWORK MONITORING</small>
<h1>Raqeeb <span lang="ar">| رقيب</span></h1>
<p>Riyadh water network · Leak monitoring and maintenance dispatch</p></div></div>''', unsafe_allow_html=True)
status, status_class = assessment_status(run)
st.markdown(f'<div class="raqeeb-status {status_class}"><h3>{status}</h3></div>', unsafe_allow_html=True)
a, b, c = st.columns(3)
a.metric('Readings read', run.cursor if run else 0)
b.metric('Leak assessments', sum(a['assessment']=='Leak indicated' for a in run.assessments) if run else 0)
c.metric('Simulated tasks completed', sum('Simulated task completed' in a['outcome'] for a in run.outcomes) if run else 0)

st.subheader('Live agents')
roles = ['Pressure Monitor', 'Usage Monitor', 'Leak Locator', 'Dispatch', 'Team A', 'Team B']
latest = max(run.agents.values(),key=lambda a:a.last_activity or '').name if run and run.bus.log and run.status == 'Running' else None
st.markdown('<div class="agent-flow">'+ '<span class="flow-arrow">→</span>'.join(
    f'<span class="flow-node {"working" if name==latest else ""}">{name}</span>' for name in roles)+'</div>', unsafe_allow_html=True)
if run:
    for start in range(0, len(roles), 3):
        for column, name in zip(st.columns(3), roles[start:start+3]):
            agent = run.agents[name]
            with column:
                st.markdown(f'<div class="agent-card {"working" if name==latest else ""}"><div class="agent-card-title"><span class="agent-dot"></span><strong>{name}</strong></div><div class="agent-state">{escape(agent.state)}</div><small>{escape(agent.action)}</small></div>', unsafe_allow_html=True)
    with st.expander('Reading and reporting agents'):
        table(pd.DataFrame([{'Agent': name, 'State': run.agents[name].state, 'Latest action': run.agents[name].action} for name in ['Reading Agent', 'Reporting Agent']]))
    for message in run.bus.log[-3:]:
        st.markdown(f"**{message['sender']} → {message['receiver']}** · {message['performative']} · {message['record_ref']}")
    if run.waiting_approval:
        st.warning('Major leak assessment · Supervisor approval required for simulated dispatch.')
        yes, no = st.columns(2)
        if yes.button('Approve dispatch', disabled=run.status != 'Running'):
            run.approve(True)
            st.rerun()
        if no.button('Reject dispatch', disabled=run.status != 'Running'):
            run.approve(False)
            st.rerun()
else:
    for start in range(0, len(roles), 3):
        for column, name in zip(st.columns(3), roles[start:start+3]):
            column.markdown(f'<div class="agent-card"><div class="agent-card-title"><span class="agent-dot"></span><strong>{name}</strong></div><div class="agent-state">Standing by</div></div>', unsafe_allow_html=True)

st.divider()
zone = st.selectbox('Zone', sorted(data.Zone.unique()), key='focus_zone')
selected = filter_data(data, zone)
st.subheader('Monitoring')
plots, counters = st.tabs(['Pressure & flow', 'System counters'])
with plots:
    observed = pd.DataFrame([r for r in run.readings[:run.cursor] if r['Zone'] == zone]) if run else pd.DataFrame()
    if not observed.empty:
        observed['Reading sequence'] = range(1, len(observed)+1)
        for column, field, title, limit in zip(st.columns(2), ['Pressure_PSI','Flow_Rate_Lmin'], ['Pressure (PSI)','Flow (L/min)'], [run.config.pressure_limit,run.config.flow_limit]):
            base = alt.Chart(observed).mark_line(point=True,color='#1466C3').encode(x=alt.X('Reading sequence:Q'), y=alt.Y(f'{field}:Q',title=title,scale=alt.Scale(zero=False)), tooltip=['record_ref',field])
            threshold = alt.Chart(pd.DataFrame({'limit':[limit]})).mark_rule(color='#DC6A50',strokeDash=[6,4]).encode(y='limit:Q')
            column.altair_chart((base+threshold).properties(height=240),width='stretch')
        st.caption('Dashed line: detection limit · Reading order, not measurement time')
    else:
        st.info('No readings for this zone yet.')
    if run and run.assessments:
        events = sorted([(a['step'], int(a['assessment']=='Leak indicated'), 0) for a in run.assessments]
                        + [(o['step'], 0, int('Simulated task completed' in o['outcome'])) for o in run.outcomes])
        rows=[]
        leaks=completed=0
        for step, leak, complete in events:
            leaks += leak
            completed += complete
            rows.append({'Execution step':step,'Leak assessments':leaks,'Simulated tasks completed':completed})
        rows = rows[-5000:]
        frame=pd.DataFrame(rows).melt('Execution step',var_name='Series',value_name='Count')
        st.altair_chart(alt.Chart(frame).mark_line(point=True).encode(x='Execution step:Q',y='Count:Q',color=alt.Color('Series:N',scale=alt.Scale(range=['#19A7A0','#1466C3']))).properties(height=230),width='stretch')
with counters:
    a,b,c=st.columns(3)
    a.metric('Messages sent',len(run.bus.log) if run else 0)
    b.metric('Team failures',sum(e['type']=='team_failure' for e in run.events) if run else 0)
    c.metric('Execution errors',sum(e['type']=='execution_error' for e in run.events) if run else 0)

logs, incidents, evaluation, experiments, readings, reports, map_tab = st.tabs(['Message log','Incidents','Dataset evaluation','Experiments','Readings','Reports','Map'])
with logs:
    if run:
        st.dataframe(pd.DataFrame([{**m,'content':json.dumps(m['content'],ensure_ascii=False)} for m in run.bus.log]),hide_index=True,width='stretch')
        st.download_button('Download message log',json.dumps(run.bus.log,indent=2),'raqeeb_messages.json','application/json',on_click='ignore')
    else:
        st.info('Press Run to start.')
with incidents:
    if run and run.outcomes:
        table(pd.DataFrame(run.outcomes))
    else:
        st.info('No outcomes yet.')
with evaluation:
    config = run.config if run else Configuration(**st.session_state.configuration)
    scores=evaluate(data,config.pressure_limit,config.flow_limit)
    for column,key in zip(st.columns(4),['accuracy','precision','recall','f1']):
        column.metric(key.title(),f'{scores[key]:.2%}')
    st.caption('Rule agreement with dataset labels · labels are not used by detection agents')
with experiments:
    experiments_view()
with readings:
    table(selected)
with reports:
    st.download_button('Export filtered readings',selected.to_csv(index=False),'raqeeb_readings.csv','text/csv',on_click='ignore')
    if run:
        st.download_button('Export actual run summary',json.dumps(run.export(),indent=2),f'raqeeb_{run.run_id}.json','application/json',on_click='ignore')
    if st.session_state.saved_runs:
        st.download_button('Export saved experiments',json.dumps(st.session_state.saved_runs,indent=2),'raqeeb_experiments.json','application/json',on_click='ignore')
with map_tab:
    geographic(selected,data,run)

st.divider()
st.subheader('Riyadh overview')
for group in [sorted(data.Zone.unique())[:3],sorted(data.Zone.unique())[3:]]:
    for column, key in zip(st.columns(len(group)),group):
        candidates=[r for r in run.readings[:run.cursor] if r['Zone']==key] if run else []
        record=candidates[-1] if candidates else None
        assessment=next((a for a in reversed(run.assessments) if record and a['record_ref']==record['record_ref']),None) if run else None
        state=assessment['assessment'] if assessment else 'Checking' if record else 'No readings'
        color={'Normal':'normal','Suspected':'suspected','Leak indicated':'leak'}.get(state,'empty')
        pressure=f"{record['Pressure_PSI']:.1f}" if record else '—'
        flow=f"{record['Flow_Rate_Lmin']:.1f}" if record else '—'
        with column:
            st.markdown(f'<div class="city-card {color}"><div class="city-heading"><h3>{key.replace("_"," ")}</h3><span>{state}</span></div><p>{key} · 5 sections</p><div class="city-readings"><div><small>Pressure · PSI</small><strong>{pressure}</strong></div><div><small>Flow · L/min</small><strong>{flow}</strong></div></div><div class="city-task">Latest system assessment</div></div>',unsafe_allow_html=True)
            st.button(f'View {key.replace("_"," ")}',key=f'view_{key}',on_click=pin_zone,args=(key,),width='stretch')
