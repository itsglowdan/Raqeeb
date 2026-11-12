import pandas as pd
import altair as alt
from i18n import tr


def network_summary(run):
    if not run or not run.assessments:
        return ('Checking readings' if run and run.cursor else 'Awaiting readings'), 'checking', []
    rows = {row['record_ref']: row for row in run.readings}
    issues = [{**a, **{k: rows[a['record_ref']][k] for k in ['Zone','Block','Pipe','Location_Code','Latitude','Longitude']}}
              for a in run.assessments if a['assessment'] != 'Normal']
    if any(a['assessment'] == 'Leak indicated' for a in issues):
        return 'Leaks indicated by detection rules', 'leak', issues
    if issues:
        return 'Suspected leaks in assessed readings', 'suspected', issues
    return 'No anomalies in assessed readings', 'normal', []


def observed_readings(run):
    if not run:
        return pd.DataFrame()
    rows = [dict(row, reading_order=i) for i, row in enumerate(run.readings[:run.cursor], 1)]
    return pd.DataFrame(rows)


def line_chart(frame, field, title, limit, language):
    base = alt.Chart(frame).mark_line(color='#1466C3', strokeWidth=2.5, clip=True).encode(
        x=alt.X('reading_order:Q', title=tr('Processed reading order',language), axis=alt.Axis(tickMinStep=1,format='d')),
        y=alt.Y(f'{field}:Q', title=title, scale=alt.Scale(zero=False)),
        order=alt.Order('reading_order:Q'),
        tooltip=[alt.Tooltip('record_ref:N',title=tr('Record reference',language)),
                 alt.Tooltip('Zone:N',title=tr('District',language)),
                 alt.Tooltip(f'{field}:Q',title=title,format='.2f')])
    rule = alt.Chart(pd.DataFrame({'limit':[limit]})).mark_rule(color='#DC6A50',strokeDash=[6,4]).encode(
        y='limit:Q',tooltip=[alt.Tooltip('limit:Q',title=tr('Detection limit',language))])
    return (base+rule).properties(height=250)


def outcome_history(run):
    if not run or not run.assessments:
        return pd.DataFrame()
    events = sorted([(a['step'],int(a['assessment']=='Leak indicated'),0) for a in run.assessments]
                    + [(o['step'],0,int('Simulated task completed' in o['outcome'])) for o in run.outcomes])
    rows = [{'step':0,'leaks':0,'completed':0}]
    leaks = completed = 0
    for step, alert, task in events:
        leaks += alert
        completed += task
        rows.append({'step':step,'leaks':leaks,'completed':completed})
    return pd.DataFrame(rows[-5000:])


def incident_rows(run):
    if not run:
        return pd.DataFrame()
    rows_by_ref = {r['record_ref']: r for r in run.readings}
    outcomes = {o['record_ref']: o['outcome'] for o in run.outcomes}
    attempts = {}
    for attempt in run.team_attempts:
        attempts.setdefault(attempt['record_ref'], []).append(attempt)
    rows = []
    for assessment in run.assessments:
        if assessment['assessment'] == 'Normal':
            continue
        ref = assessment['record_ref']
        reading = rows_by_ref[ref]
        outcome = outcomes.get(ref, 'Pending')
        assignments = attempts.get(ref, [])
        if not assignments:
            state = ('No dispatch required' if assessment['assessment']=='Suspected' else
                     'Waiting approval' if run.waiting_approval and run.current_ref==ref else
                     'Unresolved' if 'unresolved' in outcome else
                     'Rejected' if 'rejected' in outcome else 'Awaiting assignment')
            assignments = [{'team':'Not assigned','attempt':0,'state':state,
                            'reassigned_from':None,'assigned_step':None,'finished_step':None,'reason':None}]
        for attempt in assignments:
            rows.append({'record_ref':ref, 'assigned_team':attempt['team'], 'task_status':attempt['state'],
                         'reassigned_from':attempt['reassigned_from'] or '—', 'incident_result':outcome,
                         'attempt':attempt['attempt'], **{k:reading[k] for k in ['Zone','Block','Pipe']},
                         'assessment':assessment['assessment'], 'assigned_step':attempt['assigned_step'],
                         'finished_step':attempt['finished_step'], 'reason':attempt['reason'] or '—'})
    return pd.DataFrame(rows)


def message_rows(run):
    if not run:
        return pd.DataFrame()
    # Keep every actual message; put the useful reading fields first.
    columns=['step','sender','receiver','performative','record_ref','content',
             'message_id','conversation_id','runtime_timestamp','ontology','task_ref']
    return pd.DataFrame(run.bus.log, columns=columns)
