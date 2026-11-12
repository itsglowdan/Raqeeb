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
