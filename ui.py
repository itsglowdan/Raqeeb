from html import escape
import json
import folium
from branca.element import MacroElement, Template, Element
from folium.plugins import FastMarkerCluster, Fullscreen
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium
from data_loader import LABELS
from i18n import tr
from presentation import network_summary

COLUMN_LABELS = {**LABELS,'reading_order':'Processed reading order','record_ref':'Record reference',
    'assessment':'Assessment','reason':'Reason','outcome':'Outcome','step':'Execution step',
    'sender':'Sender','receiver':'Receiver','performative':'Performative','content':'Content',
    'conversation_id':'Conversation ID','message_id':'Message ID','ontology':'Ontology',
    'runtime_timestamp':'Runtime timestamp','task_ref':'Task reference','source':'Data Source',
    'Latitude':'Latitude','Longitude':'Longitude','state':'State','action':'Latest action','agent':'Agent','normal':'Normal assessments',
    'suspected':'Suspected assessments','leaks':'Leak assessments','completed':'Simulated tasks completed'}


def table(frame, language='en', **kwargs):
    shown = frame.copy()
    for column in shown.select_dtypes(include='object'):
        if column == 'content':
            continue
        shown[column] = shown[column].map(lambda value: tr(value,language) if isinstance(value,str) else value)
    shown = shown.rename(columns={name:tr(label,language) for name,label in COLUMN_LABELS.items()})
    st.dataframe(shown,hide_index=True,width='stretch',**kwargs)


@st.cache_data(show_spinner=False, max_entries=12)
def make_map(records, selected_ref, active_ref, basemap, language="en"):
    map_view = folium.Map(location=[24.7136, 46.6753], zoom_start=11, tiles=None, control_scale=True)
    if basemap:
        folium.TileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                         attr='© OpenStreetMap contributors', name=tr('Geographic background',language)).add_to(map_view)
        map_view.get_root().header.add_child(Element('<style>.leaflet-tile-pane {filter: invert(1) hue-rotate(180deg) brightness(.78) saturate(.45);}</style>'))
    points = [[r['Latitude'], r['Longitude'], r['record_ref'], int(r['Leakage_Flag']),
               r['record_ref'] in [selected_ref, active_ref]] for r in records]
    words = json.dumps([tr('Dataset label',language),tr('Leak indicated (1)',language),tr('No leak indicated (0)',language)],ensure_ascii=False)
    callback = 'function(row) { const words = '+words+';'+"""
        const color = row[3] ? '#E58D86' : '#41B3DC';
        const marker = L.circleMarker([row[0], row[1]], {
            radius: row[4] ? 7 : 4, color: row[4] ? '#E7EDF5' : color,
            weight: row[4] ? 2 : 1, fillColor: color, fillOpacity: .8
        });
        marker.bindTooltip(row[2]);
        marker.bindPopup('<b>'+row[2]+'</b><br>'+words[0]+': '+(row[3] ? words[1] : words[2]));
        return marker;
    }"""
    FastMarkerCluster(points, callback=callback, name=tr('Reading clusters (record counts)',language),
                      options={'maxClusterRadius': 35, 'disableClusteringAtZoom': 17,
                               'spiderfyOnMaxZoom': True}).add_to(map_view)
    if records:
        latitudes, longitudes = [r['Latitude'] for r in records], [r['Longitude'] for r in records]
        map_view.fit_bounds([[min(latitudes), min(longitudes)], [max(latitudes), max(longitudes)]], max_zoom=15, padding=(25, 25))
    if basemap:
        warning = MacroElement()
        warning.warning_json = json.dumps(tr('Background map unavailable. Dataset points and coordinates remain available.',language),ensure_ascii=False)
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
                div.textContent = {{ this.warning_json }};
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
    Fullscreen(position='topright',title=tr('Full Screen',language),title_cancel=tr('Exit Full Screen',language)).add_to(map_view)
    folium.LayerControl(collapsed=True).add_to(map_view)
    map_view.get_root().header.add_child(Element('<style>.marker-cluster-small,.marker-cluster-medium,.marker-cluster-large{background:#3a7ca550!important}.marker-cluster div{background:#263b50!important;color:#e7edf5;border:1px solid #41b3dc80}</style>'))
    return map_view


def geographic(frame, dataset, run, language='en'):
    t = lambda value: tr(value,language)
    st.subheader(t('Network Overview'))
    st.caption(t('Reading locations from dataset; pipeline routes unavailable.'))
    if frame.empty:
        st.info(t('No matching readings'))
        return
    refs = frame.record_ref.tolist()
    _, _, issues = network_summary(run)
    preferred = next((item['record_ref'] for item in reversed(issues) if item['assessment']=='Leak indicated'),None)
    preferred = preferred or (issues[-1]['record_ref'] if issues else None)
    current = run.current if run else None
    record = next((r for r in run.readings if r['record_ref']==preferred),None) if run and preferred else current
    if record is None and run and run.cursor:
        record = run.readings[run.cursor-1]
    active_ref = (record.get('coordinate_reference') or record['record_ref']) if record else None
    count = len(issues)
    if count != st.session_state.get('map_issue_count') or st.session_state.get('selected_record') not in refs:
        st.session_state.selected_record = active_ref if active_ref in refs else refs[0]
        st.session_state.map_issue_count = count
    selected = st.session_state.selected_record
    basemap = st.toggle(t('Geographic background'), value=True, key='basemap_enabled')
    if not basemap:
        st.info(t('Background map disabled. Exact reading coordinates remain available.'))
    view = make_map(frame.to_dict('records'),selected,active_ref,basemap,language)
    with st.spinner(t('Loading reading locations…')):
        result = st_folium(view,key=f'map_{language}_{st.session_state.get("map_generation",0)}',height=430,
                           use_container_width=True,returned_objects=['last_object_clicked_tooltip'])
    clicked = result.get('last_object_clicked_tooltip')
    if clicked in refs and clicked != selected:
        st.session_state.selected_record = clicked
        st.rerun()
    st.caption(t('Clusters show record counts. Cyan/coral represent dataset labels, not runtime assessments.'))
    if st.button(t('Reset map view'),key='reset_map'):
        st.session_state.map_generation = st.session_state.get('map_generation',0)+1
        st.rerun()
    row = dataset[dataset.record_ref==selected].iloc[0].to_dict()
    if record and record.get('source')=='Custom simulation input' and record.get('coordinate_reference')==selected:
        row = record
    with st.container(border=True):
        st.markdown(f"**{t('Reading details')} · {row['record_ref']}**")
        if row.get('source')=='Custom simulation input':
            st.caption(t('Custom simulation input')+' · '+row['coordinate_reference'])
        a,b,c = st.columns(3)
        for label,field in [('District','Zone'),('Section','Block'),('Pipeline','Pipe')]:
            a.write(f'{t(label)}: {row[field]}')
        for label,field in [('Pressure (PSI)','Pressure_PSI'),('Flow (L/min)','Flow_Rate_Lmin'),('Vibration (mm/s)','Vibration_mms')]:
            b.write(f'{t(label)}: {row[field]:.2f}')
        c.write(f"{t('Location Code')}: {row['Location_Code']}")
        c.write(f"{t('Coordinates')}: {row['Latitude']:.6f}, {row['Longitude']:.6f}")
        label = 'Not labeled' if 'Leakage_Flag' not in row else 'Leak indicated (1)' if row['Leakage_Flag'] else 'No leak indicated (0)'
        c.write(t('Dataset Leakage Label')+': '+t(label))
        assessment = next((a for a in reversed(run.assessments) if a['record_ref']==row['record_ref']),None) if run else None
        st.write(t('System assessment')+': '+(t(assessment['assessment'])+' · '+t(assessment['reason']) if assessment else t('Not assessed in this run')))
        if st.button(t('View record'),key='view_record'):
            table(pd.DataFrame([row]),language)
    with st.expander(t('Coordinate view')):
        table(frame[['record_ref','Latitude','Longitude']],language)
