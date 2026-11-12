from dataclasses import asdict
from pathlib import Path
from html import escape
import json
import time
import pandas as pd
import altair as alt
import streamlit as st
from data_loader import load_data
from simulation import Simulation, Configuration, evaluate
from controls import automatic_inputs, automatic_team_positions
from presentation import network_summary, observed_readings, line_chart, outcome_history, incident_rows, message_rows
from i18n import tr
from ui import geographic, table

st.set_page_config(page_title='Raqeeb | رقيب',page_icon='💧',layout='wide')
for key,value in {'language':'ar','run':None,'configuration':asdict(Configuration()),'last_tick':0.0}.items():
    if key not in st.session_state:
        st.session_state[key]=value
allowed_config=asdict(Configuration())
st.session_state.configuration={key:st.session_state.configuration.get(key,value) for key,value in allowed_config.items()}
if st.session_state.run and (not hasattr(st.session_state.run,'team_attempts') or any(name in st.session_state.run.agents for name in ['Reading Agent','Reporting Agent'])):
    st.session_state.run=None

with st.sidebar:
    st.selectbox('اللغة / Language',['ar','en'],format_func=lambda code:'العربية' if code=='ar' else 'English',key='language')
language=st.session_state.language
t=lambda text:tr(text,language)
st.markdown(f"<style>{Path(__file__).with_name('style.css').read_text()}</style>",unsafe_allow_html=True)
if language=='ar':
    st.markdown('<style>[data-testid="stMainBlockContainer"], [data-testid="stSidebarContent"]{direction:rtl;text-align:right}[data-testid="stVegaLiteChart"],[data-testid="stDataFrame"]{direction:ltr}.agent-flow{direction:rtl}.agent-flow .flow-arrow{transform:scaleX(-1)}</style>',unsafe_allow_html=True)


@st.cache_data
def dataset():
    return load_data()


try:
    data=dataset()
except (OSError,ValueError) as error:
    st.error(t(str(error)))
    st.stop()
run=st.session_state.run
locked=bool(run and run.status=='Running')
with st.sidebar:
    st.markdown('<div class="raqeeb-side">Raqeeb | رقيب</div>',unsafe_allow_html=True)
    with st.expander(t('Reading source and inputs'),expanded=True):
        source=st.radio(t('Data Source'),['Dataset Readings','Custom Readings'],format_func=t,key='input_source',disabled=locked)
        pressure=flow=None
        if source=='Custom Readings':
            pressure=st.number_input(t('Pressure (PSI)'),min_value=0.0,value=None,step=1.0,key='custom_pressure',disabled=locked)
            flow=st.number_input(t('Flow (L/min)'),min_value=0.0,value=None,step=1.0,key='custom_flow',disabled=locked)
            st.caption(t('Custom simulation input · Location is assigned automatically.'))
        else:
            st.caption(t('Dataset readings load automatically in their original order.'))
    inputs=automatic_inputs(data,source,pressure,flow)
    with st.expander(t('Agent parameters')):
        st.caption(t('Simulation rules, not official engineering safety limits.'))
        cfg=dict(st.session_state.configuration)
        cfg['pressure_limit']=st.number_input(t('Low pressure below (PSI)'),1.0,200.0,float(cfg['pressure_limit']),key='pressure_limit',disabled=locked)
        cfg['flow_limit']=st.number_input(t('High flow above (L/min)'),1.0,300.0,float(cfg['flow_limit']),key='flow_limit',disabled=locked)
        cfg['major_limit']=st.number_input(t('Major pressure at or below (PSI)'),.1,199.0,float(cfg['major_limit']),key='major_limit',disabled=locked)
        cfg['team_steps']=st.number_input(t('Simulated team task (steps)'),1,30,int(cfg['team_steps']),key='team_steps',disabled=locked)
        cfg['playback_interval']=st.slider(t('Playback interval (seconds)'),.5,5.0,float(cfg['playback_interval']),.5,key='playback_interval',disabled=locked)
    with st.expander(t('Team conditions')):
        for key,label in [('team_a_available','Team A available'),('team_b_available','Team B available'),
                          ('fail_team_a','Fail Team A after assignment'),('fail_team_b','Fail Team B after assignment')]:
            cfg[key]=st.checkbox(t(label),value=cfg[key],key=key,disabled=locked)
        if run:
            for name in ['Team A','Team B']:
                if st.button(t('Restore agent')+' · '+t(name),key='restore_'+name,disabled=run.status not in ['Paused','Running']):
                    run.restore(name)
                    st.rerun()
    valid=True
    try:
        config=Configuration(**cfg)
        st.session_state.configuration=asdict(config)
    except ValueError as error:
        valid=False
        st.error(t(str(error)))
    signature=json.dumps({'source':source,'configuration':cfg,'pressure':pressure,'flow':flow},sort_keys=True)
    changed=bool(run and signature!=st.session_state.get('loaded_signature'))
    st.caption(t('New settings apply on the next Run. Resume preserves the active run.'))
    st.caption(t('Execution')+': '+t(run.status if run else 'Ready'))
    a,b=st.columns(2)
    if a.button(t('Resume' if run and run.status=='Paused' and not changed else 'Run'),key='run_button',type='primary',width='stretch',
                disabled=not valid or not inputs or bool(run and (locked or (run.status in ['Completed','Failed'] and not changed)))):
        if run is None or changed:
            run=Simulation(inputs,config,team_positions=automatic_team_positions(data))
            st.session_state.run=run
            st.session_state.loaded_signature=signature
        run.run()
        st.session_state.last_tick=time.monotonic()
        st.rerun()
    if b.button(t('Pause'),key='pause_button',width='stretch',disabled=not locked):
        run.pause()
        st.rerun()
    if st.button(t('Load / Reset'),key='reset_button',width='stretch',disabled=locked):
        st.session_state.run=None
        st.session_state.last_tick=0.0
        st.rerun()


st.markdown(f'<div class="raqeeb-header"><div><small>{t("Water network monitoring")}</small><h1>Raqeeb | رقيب</h1><p>{t("Riyadh water network · Simulation")}</p></div></div>',unsafe_allow_html=True)


@st.fragment(run_every=.5 if run and run.status=='Running' else None)
def dynamic_view():
    run=st.session_state.run
    was_running=bool(run and run.status=='Running')
    if was_running and time.monotonic()-st.session_state.last_tick>=run.config.playback_interval:
        run.tick()
        st.session_state.last_tick=time.monotonic()
    if was_running and run.status!='Running':
        st.rerun()
    locked=bool(run and run.status=='Running')
    status,color,issues=network_summary(run)
    st.markdown(f'<div class="raqeeb-status {color}"><h3>{t(status)}</h3></div>',unsafe_allow_html=True)
    if issues:
        zones=sorted({item['Zone'] for item in issues})
        st.warning(t('Affected districts')+': '+', '.join(zones))
        with st.expander(t('Detected locations'),expanded=True):
            table(pd.DataFrame(issues)[['record_ref','Zone','Block','Pipe','assessment','reason']],language)
        st.caption(t('Rule assessments, not physical leak confirmation.'))
    a,b,c=st.columns(3)
    a.metric(t('Readings read'),run.cursor if run else 0)
    b.metric(t('Leak assessments'),sum(a['assessment']=='Leak indicated' for a in run.assessments) if run else 0)
    c.metric(t('Simulated tasks completed'),sum('Simulated task completed' in a['outcome'] for a in run.outcomes) if run else 0)

    st.subheader(t('Live agents'))
    roles=['Pressure Monitor','Usage Monitor','Leak Locator','Dispatch','Team A','Team B']
    latest=max(run.agents.values(),key=lambda a:a.last_activity or '').name if locked and run.bus.log else None
    flow_roles=['Pressure Monitor','Usage Monitor','Leak Locator','Dispatch','Repair Team Agent']
    flow_latest='Repair Team Agent' if latest in ['Team A','Team B'] else latest
    st.markdown('<div class="agent-flow">'+'<span class="flow-arrow">→</span>'.join(f'<span class="flow-node {"working" if name==flow_latest else ""}">{t(name)}</span>' for name in flow_roles)+'</div>',unsafe_allow_html=True)
    for start in range(0,len(roles),3):
        for column,name in zip(st.columns(3),roles[start:start+3]):
            agent=run.agents[name] if run else None
            state=t(agent.state if agent else 'Standing by')
            action=t(agent.action if agent else 'No activity yet')
            column.markdown(f'<div class="agent-card {"working" if name==latest else ""}"><div class="agent-card-title"><span class="agent-dot"></span><strong>{t(name)}</strong></div><div class="agent-state">{escape(state)}</div><small>{escape(action)}</small></div>',unsafe_allow_html=True)
    if run:
        st.caption(t('Recent activity'))
        for message in run.bus.log[-3:]:
            st.markdown(f"**{t(message['sender'])} → {t(message['receiver'])}** · {message['performative']} · {message['record_ref']}")
        if run.waiting_approval:
            st.warning(t('Major leak assessment · Supervisor approval required for simulated dispatch.'))
            a,b=st.columns(2)
            if a.button(t('Approve dispatch'),disabled=not locked):
                run.approve(True)
                st.rerun()
            if b.button(t('Reject dispatch'),disabled=not locked):
                run.approve(False)
                st.rerun()

    st.divider()
    st.subheader(t('Monitoring · All districts'))
    plots,counters=st.tabs([t('Pressure & flow'),t('System counters')])
    with plots:
        observed=observed_readings(run)
        if observed.empty:
            st.info(t('No readings yet.'))
        elif len(observed)==1:
            st.info(t('Only one reading is available. Values are shown below; a trend needs at least two readings.'))
            a,b=st.columns(2)
            a.metric(t('Pressure (PSI)'),f"{observed.iloc[0].Pressure_PSI:.2f}")
            b.metric(t('Flow (L/min)'),f"{observed.iloc[0].Flow_Rate_Lmin:.2f}")
        else:
            for column,field,label,limit in zip(st.columns(2),['Pressure_PSI','Flow_Rate_Lmin'],['Pressure (PSI)','Flow (L/min)'],[run.config.pressure_limit,run.config.flow_limit]):
                column.altair_chart(line_chart(observed,field,t(label),limit,language),width='stretch')
            st.caption(t('Lines follow processed records across all districts; the axis is reading order, not measurement time.'))
        history=outcome_history(run)
        if not history.empty:
            st.markdown('**'+t('Leak assessments and simulated task completions')+'**')
            fields=[t('Leak assessments'),t('Simulated tasks completed')]
            frame=history.rename(columns={'leaks':fields[0],'completed':fields[1]})
            chart=alt.Chart(frame).transform_fold(fields,as_=['Series','Count']).mark_line(interpolate='step-after',strokeWidth=2.5).encode(
                x=alt.X('step:Q',title=t('Execution step'),axis=alt.Axis(tickMinStep=1,format='d')),
                y=alt.Y('Count:Q',title=t('Count'),axis=alt.Axis(tickMinStep=1,format='d')),
                color=alt.Color('Series:N',title=t('Series'),legend=alt.Legend(orient='bottom',title=None,labelLimit=400),scale=alt.Scale(range=['#19A7A0','#1466C3'])),tooltip=[alt.Tooltip('step:Q',title=t('Execution step')),alt.Tooltip('Series:N',title=t('Series')),alt.Tooltip('Count:Q',title=t('Count'))]).properties(height=230)
            st.altair_chart(chart,width='stretch')
    with counters:
        for column,key,label in zip(st.columns(3),[None,'team_failure','execution_error'],['Messages sent','Team failures','Execution errors']):
            column.metric(t(label),len(run.bus.log) if run and key is None else sum(e['type']==key for e in run.events) if run else 0)

    detail_names=['Message log','Incidents','Dataset evaluation','Readings','Map']
    detail_key='details_'+language
    if detail_key not in st.session_state or st.session_state.get('last_ui_language')!=language:
        st.session_state[detail_key]=t(st.session_state.get('active_detail','Message log'))
    st.session_state.last_ui_language=language
    detail_tabs=st.tabs([t(name) for name in detail_names],key=detail_key,on_change='rerun')
    logs,incidents,evaluation,readings,map_tab=detail_tabs
    for name,tab in zip(detail_names,detail_tabs):
        if tab.open:
            st.session_state.active_detail=name
    with logs:
        if logs.open:
            if run and run.bus.log:
                messages=message_rows(run)
                messages['content']=messages['content'].map(lambda value:json.dumps(value,ensure_ascii=False))
                st.caption(t('All messages in the current run')+': '+str(len(messages)))
                table(messages,language,height=430)
                st.download_button(t('Download message log'),json.dumps(run.bus.log,indent=2),file_name='raqeeb_messages.json',mime='application/json',key='all_message_download',on_click='ignore')
            else:
                st.info(t('Press Run to start.'))
    with incidents:
        if incidents.open:
            rows=incident_rows(run)
            if not rows.empty:
                st.caption(t('Each row is an actual team attempt; a reassignment keeps the failed attempt visible.'))
                table(rows,language)
            else:
                st.info(t('No outcomes yet.'))
    with evaluation:
        if evaluation.open:
            scores=evaluate(data,*( (run.config.pressure_limit,run.config.flow_limit) if run else (cfg['pressure_limit'],cfg['flow_limit']) ))
            for column,key in zip(st.columns(4),['accuracy','precision','recall','f1']):
                column.metric(t(key.title()),f'{scores[key]:.2%}')
            st.caption(t('Rule agreement with dataset labels; labels are not used by detection agents.'))
    with readings:
        if readings.open:
            table(data,language)
    with map_tab:
        if map_tab.open:
            geographic(data,data,run,language)
    st.divider()
    st.subheader(t('Riyadh overview'))
    st.caption(t('All dataset districts · automatic issue detection'))
    summary=[]
    for zone in sorted(data.Zone.unique()):
        refs={r['record_ref'] for r in run.readings if r['Zone']==zone} if run else set()
        results=[a for a in run.assessments if a['record_ref'] in refs] if run else []
        summary.append({'Zone':zone,'normal':sum(a['assessment']=='Normal' for a in results),
                        'suspected':sum(a['assessment']=='Suspected' for a in results),'leaks':sum(a['assessment']=='Leak indicated' for a in results)})
    table(pd.DataFrame(summary),language)

dynamic_view()
