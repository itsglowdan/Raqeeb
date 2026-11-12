from dataclasses import asdict
from pathlib import Path
import json
import time
import pandas as pd
import streamlit as st
from data_loader import load_data, filter_data, custom_reading, LABELS
from simulation import Simulation, Configuration, evaluate
from protocol import utc_now
from ui import table, kpis, geographic, charts, agent_activity, messages

st.set_page_config(page_title='Raqeeb | رقيب', page_icon='💧', layout='wide')
st.markdown(f"<style>{Path(__file__).with_name('style.css').read_text()}</style>", unsafe_allow_html=True)


@st.cache_data
def dataset():
    return load_data(), utc_now()


try:
    data, loaded_at = dataset()
except (OSError, ValueError) as error:
    st.error(f'Dataset could not be loaded: {error}')
    if st.button('Retry loading data'):
        dataset.clear()
        st.rerun()
    st.stop()

for key, value in {'page': 'Dashboard', 'sequence': [], 'saved_runs': [], 'run': None,
                   'configuration': asdict(Configuration()), 'metadata': {}, 'last_tick': 0.0}.items():
    if key not in st.session_state:
        st.session_state[key] = value
# Preserve draft widget values when their page is temporarily unmounted.
for key in ['input_source', 'custom_pressure', 'custom_flow', 'custom_vibration',
            'custom_district', 'custom_section', 'custom_pipe', 'custom_reference',
            'selected_record', 'basemap_enabled']:
    if key in st.session_state:
        st.session_state[key] = st.session_state[key]

if 'pending_page' in st.session_state:
    st.session_state.page = st.session_state.pop('pending_page')
if 'pending_record' in st.session_state:
    st.session_state.selected_record = st.session_state.pop('pending_record')

PAGES = ['Dashboard', 'Readings', 'Leak Records', 'Analytics', 'Experiments', 'Reports', 'Settings']


def new_experiment():
    run = st.session_state.run
    if run:
        exported = run.export()
        if exported['status'] in ['Running', 'Paused', 'Ready']:
            exported['archive_note'] = 'Archived before completion by user'
        st.session_state.saved_runs.append(exported)
    st.session_state.run = None
    st.session_state.last_tick = 0.0


with st.sidebar:
    st.markdown('<div class="brand"><span class="drop">💧</span><div><b>Raqeeb | رقيب</b><small>Water Leak Monitoring</small></div></div>', unsafe_allow_html=True)
    page = st.radio('Navigation', PAGES, format_func=lambda item: item,
                    key='page', label_visibility='collapsed')
    st.divider()
    st.markdown('**Simulation Controls**')
    run = st.session_state.run
    status = run.status if run else 'Ready'
    st.markdown(f'<div class="execution-state">● {status}</div>', unsafe_allow_html=True)
    start, pause = st.columns(2)
    if start.button('Resume' if status == 'Paused' else 'Run', icon=':material/play_arrow:',
                    type='primary', width='stretch', disabled=status not in ['Ready', 'Paused'] or (not run and (not st.session_state.sequence or not st.session_state.get('configuration_valid', True)))):
        if not run:
            positions = {}
            for name, key in [('Team A', 'team_a_record'), ('Team B', 'team_b_record')]:
                reference = st.session_state.get('configured_'+key, data.record_ref.iloc[0] if name == 'Team A' else data.record_ref.iloc[-1])
                row = data.loc[data.record_ref == reference].iloc[0]
                positions[name] = {'record_ref': reference, 'position': [float(row.Latitude), float(row.Longitude)]}
            st.session_state.run = Simulation(st.session_state.sequence, Configuration(**st.session_state.configuration),
                                                st.session_state.metadata, positions)
            run = st.session_state.run
        run.run()
        st.session_state.last_tick = time.monotonic()
        st.rerun()
    if pause.button('Pause', icon=':material/pause:', width='stretch', disabled=status != 'Running'):
        run.pause()
        st.rerun()
    st.caption('Dataset playback and custom-input simulation')
    if run:
        st.caption(f'Run {run.run_id} · step {run.step}\n\nReadings started: {run.cursor} / {len(run.readings)}')
    else:
        st.caption(f'{len(st.session_state.sequence):,} configured readings')
    st.markdown('<div class="sidebar-wave" aria-hidden="true"></div>', unsafe_allow_html=True)

run = st.session_state.run


@st.fragment(run_every=0.5 if run and run.status == 'Running' else None)
def heartbeat():
    active = st.session_state.run
    if active and active.status == 'Running' and time.monotonic() - st.session_state.last_tick >= active.config.playback_interval:
        active.tick()
        st.session_state.last_tick = time.monotonic()
        st.rerun()


heartbeat()

st.title(page)
st.caption({'Dashboard': 'Water network data and simulation overview.', 'Readings': 'Original dataset readings and exact record locations.',
            'Leak Records': 'Dataset leakage labels and runtime alerts, shown separately.', 'Analytics': 'Dataset distributions and rule-based assessment evaluation.',
            'Experiments': 'Prepare user-controlled experiments and record observed results.', 'Reports': 'Export dataset selections and actual execution records.',
            'Settings': 'Configure simulation inputs and reading sequences.'}[page])
st.caption(f'riyadh_leakage_dataset_with_units.csv · {len(data):,} readings · Simulation environment')

with st.expander('Dataset filters', expanded=page in ['Dashboard', 'Readings', 'Leak Records']):
    a, b, c = st.columns(3)
    district = a.selectbox('District', ['All']+sorted(data.Zone.unique()), key='filter_district')
    sections = ['All']+sorted(data[data.Zone == district].Block.unique() if district != 'All' else data.Block.unique())
    if st.session_state.get('filter_section', 'All') not in sections:
        st.session_state.filter_section = 'All'
    section = b.selectbox('Section', sections, key='filter_section')
    partial = filter_data(data, district, section)
    pipes = ['All']+sorted(partial.Pipe.unique())
    if st.session_state.get('filter_pipeline', 'All') not in pipes:
        st.session_state.filter_pipeline = 'All'
    pipeline = c.selectbox('Pipeline', pipes, key='filter_pipeline')
    query = st.text_input('Search record reference or location identifier', key='dataset_search')
selected = filter_data(data, district, section, pipeline, query)


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
    source = st.segmented_control('Data Source', ['Dataset Readings', 'Custom Readings'], default='Dataset Readings', key='input_source')
    if source == 'Dataset Readings':
        st.caption('Use the dataset filters above. Measurements, coordinates and labels remain unchanged.')
        all_rows = st.checkbox('Include all filtered records', value=True)
        refs = selected.record_ref.tolist()
        chosen = refs if all_rows else st.multiselect('Dataset records', refs)
        if st.button('Add dataset readings', type='primary', disabled=locked or not chosen):
            current = {row['record_ref'] for row in st.session_state.sequence}
            records = selected[selected.record_ref.isin(chosen)].to_dict('records')
            st.session_state.sequence.extend([{**row, 'source': 'Dataset Readings'} for row in records if row['record_ref'] not in current])
            # Dataset playback always preserves original row order.
            st.session_state.sequence.sort(key=lambda row: (row.get('source') == 'Custom simulation input', row.get('original_index') or 0))
            st.rerun()
    elif source == 'Custom Readings':
        st.info('Custom simulation input · not labeled. Select one exact dataset record as the coordinate reference.')
        location, values = st.columns(2)
        with location:
            st.markdown('**Select Location**')
            zone = st.selectbox('District', sorted(data.Zone.unique()), key='custom_district', disabled=locked)
            block = st.selectbox('Section', sorted(data[data.Zone == zone].Block.unique()), key='custom_section', disabled=locked)
            pipe = st.selectbox('Pipeline', sorted(data[(data.Zone == zone)&(data.Block == block)].Pipe.unique()), key='custom_pipe', disabled=locked)
            candidates = data[(data.Zone == zone)&(data.Block == block)&(data.Pipe == pipe)]
            reference = st.selectbox('Coordinate reference record', candidates.record_ref.tolist(), key='custom_reference', disabled=locked)
            row = candidates.loc[candidates.record_ref == reference].iloc[0].to_dict()
            st.caption(f"{reference} · {row['Location_Code']}\n\nLatitude {row['Latitude']:.6f} · Longitude {row['Longitude']:.6f}")
        with values:
            st.markdown('**Enter Reading**')
            pressure = st.number_input('Pressure (PSI)', min_value=0.0, value=None, step=1.0, key='custom_pressure', disabled=locked)
            flow = st.number_input('Flow (L/min)', min_value=0.0, value=None, step=1.0, key='custom_flow', disabled=locked)
            vibration = st.number_input('Vibration (mm/s)', min_value=0.0, value=None, step=.1, key='custom_vibration', disabled=locked)
            st.caption('Vibration is preserved and displayed; the approved dual-monitor detection rule uses pressure and flow.')
            if st.button('Add reading', type='primary', disabled=locked or None in [pressure, flow, vibration]):
                try:
                    count = max([int(r['record_ref'].split('-')[1]) for r in st.session_state.sequence if r['record_ref'].startswith('CUSTOM-')]+[0])+1
                    st.session_state.sequence.append(custom_reading(row, pressure, flow, vibration, count))
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))
        st.caption('Add each reading to the sequence before running.')
    st.subheader('Reading Sequence')
    a, b = st.columns(2)
    if a.button('Remove last', disabled=locked or not st.session_state.sequence):
        st.session_state.sequence.pop()
        st.rerun()
    if b.button('Reset inputs', disabled=locked):
        st.session_state.sequence = []
        for key in ['custom_pressure', 'custom_flow', 'custom_vibration']:
            st.session_state.pop(key, None)
        st.rerun()
    if st.session_state.sequence:
        frame = pd.DataFrame(st.session_state.sequence)
        frame.insert(0, 'Sequence number', range(1, len(frame)+1))
        table(frame)
    else:
        st.info('No readings added yet')
    st.caption(f'Readiness: {len(st.session_state.sequence):,} readings configured' if st.session_state.sequence else 'Not ready · Add at least one valid reading')
    with st.expander('Agent Parameters · simulation configuration', expanded=True):
        st.caption('These are configurable demonstration rules, not official engineering safety limits. Changes take effect in a fresh run.')
        old = st.session_state.configuration
        a, b, c = st.columns(3)
        pressure_limit = a.number_input('Low pressure below (PSI)', 1.0, 200.0, float(old['pressure_limit']), help='Pressure Monitor flags values strictly below this limit.', disabled=locked)
        flow_limit = b.number_input('High flow above (L/min)', 1.0, 300.0, float(old['flow_limit']), help='Usage Monitor flags values strictly above this limit.', disabled=locked)
        major_limit = c.number_input('Major pressure at or below (PSI)', 0.1, 199.0, float(old['major_limit']), help='Requires dual-rule confirmation first, then supervisor approval.', disabled=locked)
        a, b, c = st.columns(3)
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
    st.subheader('Configured Simulated Teams')
    st.caption('Positions are user-selected dataset coordinate references; not real maintenance depots. Straight-line distance is not travel distance.')
    for name, key, default in [('Team A', 'team_a_record', 0), ('Team B', 'team_b_record', len(data)-1)]:
        saved = st.session_state.get('configured_'+key, data.record_ref.iloc[default])
        choice = st.selectbox(f'{name} position reference', data.record_ref.tolist(), index=data.record_ref.tolist().index(saved), key=key, disabled=locked)
        st.session_state['configured_'+key] = choice


def experiments_view():
    st.caption('Configure readings and parameters in Settings. No preset scenarios or scripted outcomes are loaded.')
    if st.button('Open simulation settings'):
        st.session_state.pending_page = 'Settings'
        st.rerun()
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


if page == 'Dashboard':
    kpis(selected)
    geographic(selected, data, run)
    st.divider()
    agent_activity(run)
    messages(run)
    st.divider()
    charts(selected)
    with st.expander('Detailed readings'):
        table(selected)
elif page == 'Readings':
    readings_view(selected)
elif page == 'Leak Records':
    labeled, runtime = st.tabs(['Dataset leak-flagged readings', 'Runtime-generated records'])
    with labeled:
        flagged = selected[selected.Leakage_Flag == 1]
        if flagged.empty:
            st.info('No leak-flagged readings in this selection')
        else:
            st.caption(f'{len(flagged)} labeled readings · repeated locations are not unique confirmed incidents')
            table(flagged)
    with runtime:
        if run and run.reports:
            st.dataframe(pd.DataFrame([{**r, 'assessment': json.dumps(r['assessment']), 'location': json.dumps(r['location'])} for r in run.reports]), hide_index=True, width='stretch')
        else:
            st.info('No runtime-generated reports yet.')
elif page == 'Analytics':
    kpis(selected)
    charts(selected)
    st.subheader('Rule assessment against dataset labels')
    st.caption('Evaluation of configured pressure-and-flow rules on this dataset selection. Not a trained machine-learning model or an independent test set.')
    cfg = run.config if run else Configuration(**st.session_state.configuration)
    st.caption(f'Pressure < {cfg.pressure_limit} PSI AND flow > {cfg.flow_limit} L/min. Dataset Leakage Label is used only as the evaluation target.')
    if len(selected):
        scores = evaluate(selected, cfg.pressure_limit, cfg.flow_limit)
        for column, key in zip(st.columns(4), ['accuracy', 'precision', 'recall', 'f1']):
            column.metric(key.title(), f'{scores[key]:.2%}')
        table(pd.DataFrame([scores]))
        st.caption('Accuracy: correct labels / all records. Precision: correct leak assessments / all leak assessments. Recall: detected labeled leaks / all labeled leaks. F1: harmonic mean of precision and recall. Zero denominators return 0.')
    if run and run.assessments:
        st.subheader('Actual runtime assessments')
        table(pd.DataFrame(run.assessments))
elif page == 'Settings':
    settings_view()
elif page == 'Experiments':
    experiments_view()
elif page == 'Reports':
    st.caption(f'Report generation runtime (UTC): {utc_now()} · The dataset has no measurement timestamps.')
    st.download_button('Export filtered readings', selected.drop(columns=['record_ref', 'original_index']).to_csv(index=False), 'raqeeb_filtered_readings.csv', 'text/csv', on_click='ignore')
    st.download_button('Export readings with record references', selected.to_csv(index=False), 'raqeeb_referenced_readings.csv', 'text/csv', on_click='ignore')
    if run:
        st.download_button('Export actual run summary and messages', json.dumps(run.export(), indent=2), f'raqeeb_{run.run_id}.json', 'application/json', on_click='ignore')
    if st.session_state.saved_runs:
        st.write(f'Saved experiment snapshots: {len(st.session_state.saved_runs)}')
        st.download_button('Export saved experiments', json.dumps(st.session_state.saved_runs, indent=2), 'raqeeb_experiments.json', 'application/json', on_click='ignore')
    st.info('Session state survives navigation. Download results before closing the session. Academic report, poster and presentation are separate submission files.')
