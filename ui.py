from html import escape
import json
import altair as alt
import folium
from branca.element import MacroElement, Template, Element
from folium.plugins import FastMarkerCluster, Fullscreen
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium
from data_loader import LABELS, summarize


def table(frame, **kwargs):
    shown = frame.rename(columns=LABELS)
    st.dataframe(shown, hide_index=True, width='stretch', **kwargs)


def kpis(frame):
    values = summarize(frame)
    st.caption('Dataset summaries · selected records')
    for column, label, value in zip(st.columns(4),
            ['Readings', 'Leak-Flagged Readings', 'Average Pressure', 'Average Flow'],
            [f"{values['readings']:,}", f"{values['flagged']:,}",
             f"{values['pressure']:.2f} PSI" if values['pressure'] is not None else '—',
             f"{values['flow']:.2f} L/min" if values['flow'] is not None else '—']):
        column.metric(label, value)


@st.cache_data(show_spinner=False, max_entries=12)
def make_map(records, selected_ref, active_ref, basemap):
    map_view = folium.Map(location=[24.7136, 46.6753], zoom_start=11, tiles=None, control_scale=True)
    if basemap:
        folium.TileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                         attr='© OpenStreetMap contributors', name='Geographic background').add_to(map_view)
        map_view.get_root().header.add_child(Element('<style>.leaflet-tile-pane {filter: invert(1) hue-rotate(180deg) brightness(.78) saturate(.45);}</style>'))
    points = [[r['Latitude'], r['Longitude'], r['record_ref'], int(r['Leakage_Flag']),
               r['record_ref'] in [selected_ref, active_ref]] for r in records]
    callback = """function(row) {
        const color = row[3] ? '#E58D86' : '#41B3DC';
        const marker = L.circleMarker([row[0], row[1]], {
            radius: row[4] ? 7 : 4, color: row[4] ? '#E7EDF5' : color,
            weight: row[4] ? 2 : 1, fillColor: color, fillOpacity: .8
        });
        marker.bindTooltip(row[2]);
        marker.bindPopup('<b>'+row[2]+'</b><br>Dataset label: '+(row[3] ? 'Leak indicated (1)' : 'No leak indicated (0)'));
        return marker;
    }"""
    FastMarkerCluster(points, callback=callback, name='Reading clusters (record counts)',
                      options={'maxClusterRadius': 35, 'disableClusteringAtZoom': 17,
                               'spiderfyOnMaxZoom': True}).add_to(map_view)
    if records:
        latitudes, longitudes = [r['Latitude'] for r in records], [r['Longitude'] for r in records]
        map_view.fit_bounds([[min(latitudes), min(longitudes)], [max(latitudes), max(longitudes)]], max_zoom=15, padding=(25, 25))
    if basemap:
        warning = MacroElement()
        warning._template = Template("""{% macro script(this, kwargs) %}
        (function() {
          const map = {{this._parent.get_name()}};
          let warned = false;
          function bindTileErrors(layer) {
            if (!(layer instanceof L.TileLayer) || layer._raqeebErrorsBound) return;
            layer._raqeebErrorsBound = true;
            layer.on('tileerror', function() {
              if (warned) return;
              warned = true;
              const warning = L.control({position:'topright'});
              warning.onAdd = function() {
                const div = L.DomUtil.create('div');
                div.textContent = 'Background map unavailable. Dataset points and coordinates remain available.';
                div.setAttribute('role','alert');
                div.style.cssText='background:#1d2e40;color:#e7edf5;padding:12px;max-width:250px;border:1px solid #e58d86;border-radius:8px';
                return div;
              };
              warning.addTo(map);
            });
          }
          map.eachLayer(bindTileErrors);
          map.on('layeradd', function(event) { bindTileErrors(event.layer); });
        })();
        {% endmacro %}""")
        map_view.add_child(warning)
    Fullscreen(position='topright').add_to(map_view)
    folium.LayerControl(collapsed=True).add_to(map_view)
    map_view.get_root().header.add_child(Element('<style>.marker-cluster-small,.marker-cluster-medium,.marker-cluster-large{background:#3a7ca550!important}.marker-cluster div{background:#263b50!important;color:#e7edf5;border:1px solid #41b3dc80}</style>'))
    return map_view


def geographic(frame, dataset, run):
    st.subheader('Network Overview')
    st.markdown('<span class="badge">Dataset Coordinates</span>', unsafe_allow_html=True)
    st.caption('Reading locations from dataset; pipeline routes unavailable.')
    if frame.empty:
        st.info('No matching readings')
        return
    refs = frame.record_ref.tolist()
    selected = st.session_state.get('selected_record')
    if selected not in refs:
        selected = refs[0]
        st.session_state.selected_record = selected
    st.selectbox('Selected dataset record', refs, key='selected_record')
    selected = st.session_state.selected_record
    active_ref = (run.current.get('coordinate_reference') if run.current.get('source') == 'Custom simulation input' else run.current_ref) if run and run.current else None
    basemap = st.toggle('Geographic background', value=True, key='basemap_enabled')
    if not basemap:
        st.info('Background map disabled. Exact reading coordinates remain available.')
    map_view = make_map(frame.to_dict('records'), selected, active_ref, basemap)
    with st.spinner('Loading reading locations…'):
        result = st_folium(map_view, key=f'reading_map_{st.session_state.get("map_generation", 0)}', height=430, use_container_width=True,
                           returned_objects=['last_object_clicked', 'last_object_clicked_tooltip'])
    tooltip = result.get('last_object_clicked_tooltip')
    if tooltip in refs and tooltip != selected:
        st.session_state.pending_record = tooltip
        st.rerun()
    st.caption('Clusters show record counts, not sensors or unique incidents. Click a point to select its record. Reset view: reload selected records below.')
    if st.button('Reset map view', key='reset_map'):
        st.session_state.map_generation = st.session_state.get('map_generation', 0) + 1
        st.rerun()
    row = dataset.loc[dataset.record_ref == selected].iloc[0].to_dict()
    with st.container(border=True):
        st.markdown(f"**Reading details · {selected}**")
        a, b, c = st.columns(3)
        a.write(f"District: {row['Zone']}\n\nSection: {row['Block']}\n\nPipeline: {row['Pipe']}")
        b.write(f"Pressure: {row['Pressure_PSI']:.2f} PSI\n\nFlow: {row['Flow_Rate_Lmin']:.2f} L/min\n\nVibration: {row['Vibration_mms']:.2f} mm/s")
        c.write(f"Location Code: {row['Location_Code']}\n\nCoordinates: {row['Latitude']:.6f}, {row['Longitude']:.6f}\n\nDataset Leakage Label: {'Leak indicated (1)' if row['Leakage_Flag'] else 'No leak indicated (0)'}")
        assessments = [a for a in run.assessments if a['record_ref'] == selected] if run else []
        st.write('System assessment: ' + (assessments[-1]['assessment'] + ' · ' + assessments[-1]['reason'] if assessments else 'Not assessed in this run'))
        if active_ref:
            if run.current.get('source') == 'Custom simulation input':
                st.caption(f'Current custom simulation input: {run.current_ref} · coordinate reference {active_ref}. Details above belong to the original reference reading.')
            else:
                st.caption(f'Current playback record: {active_ref} · white marker outline')
            if active_ref not in refs:
                st.caption('Current playback location is outside the dataset filters. Clear the filters to see it.')
        if st.button('View record', key='view_record'):
            st.session_state.pending_page = 'Readings'
            st.rerun()
    st.caption('If the geographic background fails to load, disable it above; points remain at their exact dataset coordinates. Coordinate table:')
    with st.expander('Coordinate view'):
        table(frame[['record_ref', 'Latitude', 'Longitude']])


def charts(frame):
    if frame.empty:
        st.info('No matching readings')
        return
    left, right = st.columns([2, 1])
    with left:
        st.subheader('Readings in Dataset Order')
        options = {'Pressure (PSI)': 'Pressure_PSI', 'Flow (L/min)': 'Flow_Rate_Lmin', 'Vibration (mm/s)': 'Vibration_mms'}
        label = st.selectbox('Measurement', list(options), key='chart_metric')
        field = options[label]
        base = alt.Chart(frame).encode(x=alt.X('original_index:Q', title='Original Reading Index'),
                    y=alt.Y(f'{field}:Q', title=label, scale=alt.Scale(zero=False)),
                    tooltip=['record_ref:N', 'Location_Code:N', alt.Tooltip(f'{field}:Q', format='.2f')])
        area = base.mark_area(color='#41B3DC', opacity=.13, interpolate='linear')
        line = base.mark_line(color='#41B3DC', strokeWidth=2, interpolate='linear')
        selected = frame[frame.record_ref == st.session_state.get('selected_record')]
        point = alt.Chart(selected).mark_circle(size=95, color='#E7EDF5', stroke='#41B3DC', strokeWidth=2).encode(
            x='original_index:Q', y=f'{field}:Q', tooltip=['record_ref', 'Location_Code', field])
        st.altair_chart((area+line+point).properties(height=260), width='stretch')
        st.caption('Original row order, not measurement time. Lines connect observed samples only.')
    with right:
        st.subheader('Dataset Leakage Labels')
        flagged = int(frame.Leakage_Flag.sum())
        counts = pd.DataFrame({'Label': ['Leak indicated', 'No leak indicated'], 'Readings': [flagged, len(frame)-flagged]})
        donut = alt.Chart(counts).mark_arc(innerRadius=65).encode(
            theta='Readings:Q', color=alt.Color('Label:N', scale=alt.Scale(domain=['Leak indicated', 'No leak indicated'], range=['#E58D86', '#41B3DC'])),
            tooltip=['Label', 'Readings']).properties(height=220)
        st.altair_chart(donut, width='stretch')
        st.caption(f'{flagged:,} leak indicated ({flagged/len(frame):.2%}) · {len(frame)-flagged:,} no leak indicated')


def agent_activity(run):
    st.subheader('Live Agent Activity')
    if not run:
        st.info('Configure a sequence in Settings, then use Run in the sidebar.')
        return
    pairs = list(run.agents.values())
    for start in range(0, len(pairs), 4):
        for column, agent in zip(st.columns(4), pairs[start:start+4]):
            with column:
                st.markdown(f'<div class="agent-card"><strong>{escape(agent.name)}</strong><p>{escape(agent.role)}</p>'
                            f'<span class="badge">{escape(agent.state)}</span><p>{escape(agent.action)}</p>'
                            f'<small>Last runtime activity: {escape(agent.last_activity or "Not started")}</small>'
                            f'{"<p class=attention>"+escape(agent.failure)+"</p>" if agent.failure else ""}</div>', unsafe_allow_html=True)
    if run.waiting_approval:
        st.warning('Major rule assessment · Supervisor approval required for simulated dispatch.')
        approve, reject = st.columns(2)
        if approve.button('Approve simulated dispatch', disabled=run.status != 'Running'):
            run.approve(True)
            st.rerun()
        if reject.button('Reject simulated dispatch', disabled=run.status != 'Running'):
            run.approve(False)
            st.rerun()


def messages(run):
    st.subheader('Agent Messages')
    if not run or not run.bus.log:
        st.info('No messages exchanged yet.')
        return
    for message in run.bus.log[-4:]:
        st.markdown(f"**{message['sender']} → {message['receiver']}** · `{message['performative']}` · step {message['step']} · {message['record_ref']}")
    with st.expander('Detailed message log'):
        a, b, c = st.columns(3)
        agent = a.selectbox('Agent', ['All']+list(run.agents), key='message_agent')
        action = b.selectbox('Performative', ['All']+sorted({m['performative'] for m in run.bus.log}), key='message_action')
        conversation = c.selectbox('Conversation', ['All']+list(dict.fromkeys(m['conversation_id'] for m in run.bus.log)), key='message_conversation')
        rows = [m for m in run.bus.log if (agent == 'All' or agent in [m['sender'], m['receiver']])
                and (action == 'All' or action == m['performative']) and (conversation == 'All' or conversation == m['conversation_id'])]
        st.dataframe(pd.DataFrame([{**row, 'content': json.dumps(row['content'], ensure_ascii=False)} for row in rows]), hide_index=True, width='stretch')
        st.download_button('Export filtered messages', json.dumps(rows, indent=2), 'raqeeb_messages.json', 'application/json', on_click='ignore')
