import pandas as pd
import streamlit as st

st.set_page_config(page_title='Sales Analytics Dashboard', page_icon='📊', layout='wide', initial_sidebar_state='expanded')

DATABASE = 'SALES_ANALYTICS_DB'
SCHEMA = 'GOLD'
VIEWS = {
    'inbound': f'{DATABASE}.{SCHEMA}.INBOUND_SETTER_REPORT_SME',
    'outbound': f'{DATABASE}.{SCHEMA}.OUTBOUND_SETTER_REPORT_SME',
    'closer': f'{DATABASE}.{SCHEMA}.CLOSER_REPORT_SME',
    'objections': f'{DATABASE}.{SCHEMA}.OBJECTIONS_FACED_REPORT',
}

@st.cache_resource
def get_session():
    return st.connection('snowflake').session()

@st.cache_data(ttl=300, show_spinner=False)
def run_query(sql: str) -> pd.DataFrame:
    df = get_session().sql(sql).to_pandas()
    df.columns = [str(c).upper() for c in df.columns]
    return df

def money(v):
    try: return f'${float(v):,.0f}'
    except Exception: return '$0'

def whole(v):
    try: return f'{int(round(float(v))):,}'
    except Exception: return '0'

def pct(v):
    try: return f'{float(v):,.2f}%'
    except Exception: return '0.00%'

def num_series(df, col):
    if col not in df.columns:
        return pd.Series(0, index=df.index, dtype='float64')
    return pd.to_numeric(df[col], errors='coerce').fillna(0)

def total(df, col):
    return float(num_series(df, col).sum())

def weighted_rate(df, num_col, den_col):
    d = total(df, den_col)
    return 0.0 if d == 0 else 100.0 * total(df, num_col) / d

def prep_date(df, col):
    out = df.copy()
    if col in out.columns:
        out[col] = pd.to_datetime(out[col], errors='coerce')
    return out

def filter_date(df, col, start, end):
    if col not in df.columns:
        return df.copy()
    out = prep_date(df, col)
    return out[(out[col].notna()) & (out[col].dt.date >= start) & (out[col].dt.date <= end)].copy()

def filter_values(df, col, values):
    if col not in df.columns or not values:
        return df.copy()
    return df[df[col].fillna('UNMAPPED').astype(str).isin(values)].copy()

def add_rate(df, new_col, num_col, den_col):
    out = df.copy()
    out[new_col] = (100.0 * num_series(out, num_col) / num_series(out, den_col).replace(0, pd.NA)).fillna(0).round(2)
    return out

def download_csv(df, filename):
    st.download_button('Download CSV', df.to_csv(index=False).encode('utf-8'), filename, 'text/csv')

def bar_chart(df, label_col, value_col, title):
    st.subheader(title)
    if df.empty or label_col not in df.columns or value_col not in df.columns:
        st.info('No data is available for the selected filters.')
        return
    st.bar_chart(df[[label_col, value_col]].dropna(subset=[label_col]).set_index(label_col), use_container_width=True)

def line_chart(df, date_col, metric_cols, title):
    st.subheader(title)
    valid = [c for c in metric_cols if c in df.columns]
    if df.empty or date_col not in df.columns or not valid:
        st.info('No data is available for the selected filters.')
        return
    st.line_chart(df[[date_col] + valid].dropna(subset=[date_col]).set_index(date_col).sort_index(), use_container_width=True)

st.title('Sales Analytics Dashboard')
st.caption('Snowflake-native Streamlit dashboard built from the Gold reporting layer.')

with st.sidebar:
    st.header('Navigation')
    page = st.radio('Dashboard page', ['Executive Overview','Inbound Setter','Outbound Setter','Closer Performance','Objections','Data Quality'], label_visibility='collapsed')
    st.divider()
    st.caption('Snowflake data is cached for five minutes.')
    if st.button('Refresh data', use_container_width=True):
        run_query.clear(); get_session.clear(); st.rerun()

try:
    with st.spinner('Loading data from Snowflake...'):
        inbound = prep_date(run_query(f"SELECT * FROM {VIEWS['inbound']}"), 'TRIAGE_DATE')
        outbound = prep_date(run_query(f"SELECT * FROM {VIEWS['outbound']}"), 'DIAL_DATE')
        closer = run_query(f"SELECT * FROM {VIEWS['closer']}")
        objections = prep_date(run_query(f"SELECT * FROM {VIEWS['objections']}"), 'ACTIVITY_DATE')
except Exception as exc:
    st.error('The app could not query the Snowflake Gold views.')
    st.code(str(exc))
    st.info('Confirm the app owner role has USAGE on the database and schema and SELECT on all four views.')
    st.stop()

dates = []
for frame, col in [(inbound,'TRIAGE_DATE'),(outbound,'DIAL_DATE'),(objections,'ACTIVITY_DATE')]:
    if col in frame.columns and not frame[col].dropna().empty:
        dates.extend(frame[col].dropna().dt.date.tolist())
min_date = min(dates) if dates else pd.Timestamp.today().date()
max_date = max(dates) if dates else pd.Timestamp.today().date()

with st.sidebar:
    st.header('Global date filter')
    dr = st.date_input('Date range', value=(min_date,max_date), min_value=min_date, max_value=max_date)
    if isinstance(dr, tuple) and len(dr) == 2: start_date, end_date = dr
    else: start_date = end_date = dr

inbound_f = filter_date(inbound,'TRIAGE_DATE',start_date,end_date)
outbound_f = filter_date(outbound,'DIAL_DATE',start_date,end_date)
objections_f = filter_date(objections,'ACTIVITY_DATE',start_date,end_date)

if page == 'Executive Overview':
    st.header('Executive Overview')
    cols = st.columns(6)
    cols[0].metric('Inbound calls', whole(total(inbound_f,'INBOUND_BOOKED')))
    cols[1].metric('Outbound calls', whole(total(outbound_f,'TOTAL_OUTBOUND_CALLS')))
    cols[2].metric('Inbound sales', whole(total(inbound_f,'TOTAL_SALES')))
    cols[3].metric('Outbound sales', whole(total(outbound_f,'TOTAL_SALE')))
    cols[4].metric('Outbound revenue', money(total(outbound_f,'TOTAL_REVENUE')))
    cols[5].metric('Cash collected', money(total(closer,'CASH_COLLECTED')))
    st.subheader('Conversion performance')
    cols = st.columns(4)
    cols[0].metric('Inbound show rate', pct(weighted_rate(inbound_f,'INBOUND_TAKEN','INBOUND_BOOKED')))
    cols[1].metric('Inbound sale rate', pct(weighted_rate(inbound_f,'TOTAL_SALES','STRATEGY_CALL_TAKEN')))
    cols[2].metric('Outbound dial-to-set', pct(weighted_rate(outbound_f,'OUTBOUND_SET','TOTAL_OUTBOUND_CALLS')))
    cols[3].metric('Outbound show-to-sale', pct(weighted_rate(outbound_f,'TOTAL_SALE','TOTAL_CLOSER_SHOW')))
    in_daily = inbound_f.groupby('TRIAGE_DATE',as_index=False)[['INBOUND_BOOKED','INBOUND_TAKEN','TOTAL_SALES']].sum() if not inbound_f.empty else pd.DataFrame()
    out_daily = outbound_f.groupby('DIAL_DATE',as_index=False)[['TOTAL_OUTBOUND_CALLS','OUTBOUND_SET','TOTAL_CLOSER_SHOW','TOTAL_SALE']].sum() if not outbound_f.empty else pd.DataFrame()
    l,r = st.columns(2)
    with l: line_chart(in_daily,'TRIAGE_DATE',['INBOUND_BOOKED','INBOUND_TAKEN','TOTAL_SALES'],'Inbound performance trend')
    with r: line_chart(out_daily,'DIAL_DATE',['TOTAL_OUTBOUND_CALLS','OUTBOUND_SET','TOTAL_CLOSER_SHOW','TOTAL_SALE'],'Outbound performance trend')

elif page == 'Inbound Setter':
    st.header('Inbound Setter Performance')
    options = sorted(inbound_f['SETTER'].dropna().astype(str).unique().tolist()) if 'SETTER' in inbound_f.columns else []
    selected = st.multiselect('Setter', options, default=options)
    df = filter_values(inbound_f,'SETTER',selected)
    cols = st.columns(6)
    cols[0].metric('Inbound booked',whole(total(df,'INBOUND_BOOKED')))
    cols[1].metric('Inbound taken',whole(total(df,'INBOUND_TAKEN')))
    cols[2].metric('Show rate',pct(weighted_rate(df,'INBOUND_TAKEN','INBOUND_BOOKED')))
    cols[3].metric('Strategy calls booked',whole(total(df,'STRATEGY_CALL_BOOKED')))
    cols[4].metric('Strategy calls taken',whole(total(df,'STRATEGY_CALL_TAKEN')))
    cols[5].metric('Total sales',whole(total(df,'TOTAL_SALES')))
    if df.empty: st.info('No data is available for the selected filters.')
    else:
        s = df.groupby('SETTER',as_index=False).agg(INBOUND_BOOKED=('INBOUND_BOOKED','sum'),INBOUND_TAKEN=('INBOUND_TAKEN','sum'),STRATEGY_CALL_BOOKED=('STRATEGY_CALL_BOOKED','sum'),STRATEGY_CALL_TAKEN=('STRATEGY_CALL_TAKEN','sum'),TOTAL_SALES=('TOTAL_SALES','sum'))
        s = add_rate(add_rate(s,'SHOW_RATE','INBOUND_TAKEN','INBOUND_BOOKED'),'SALE_RATE','TOTAL_SALES','STRATEGY_CALL_TAKEN')
        l,r=st.columns(2)
        with l: bar_chart(s.sort_values('INBOUND_BOOKED',ascending=False).head(15),'SETTER','INBOUND_BOOKED','Top setters by inbound calls')
        with r: bar_chart(s.sort_values('TOTAL_SALES',ascending=False).head(15),'SETTER','TOTAL_SALES','Top setters by sales')
        st.subheader('Inbound setter summary'); st.dataframe(s.sort_values(['TOTAL_SALES','INBOUND_BOOKED'],ascending=False),use_container_width=True); download_csv(s,'inbound_setter_summary.csv')

elif page == 'Outbound Setter':
    st.header('Outbound Setter Performance')
    options = sorted(outbound_f['SETTER'].dropna().astype(str).unique().tolist()) if 'SETTER' in outbound_f.columns else []
    selected = st.multiselect('Setter', options, default=options)
    df = filter_values(outbound_f,'SETTER',selected)
    cols = st.columns(6)
    cols[0].metric('Outbound calls',whole(total(df,'TOTAL_OUTBOUND_CALLS')))
    cols[1].metric('Leads touched',whole(total(df,'TOTAL_LEADS_TOUCHED')))
    cols[2].metric('Outbound sets',whole(total(df,'OUTBOUND_SET')))
    cols[3].metric('Closer shows',whole(total(df,'TOTAL_CLOSER_SHOW')))
    cols[4].metric('Sales',whole(total(df,'TOTAL_SALE')))
    cols[5].metric('Revenue',money(total(df,'TOTAL_REVENUE')))
    st.subheader('Outbound conversion funnel')
    funnel = pd.DataFrame({'STAGE':['Outbound Calls','Outbound Set','Closer Show','Offer','Sale'],'COUNT':[total(df,'TOTAL_OUTBOUND_CALLS'),total(df,'OUTBOUND_SET'),total(df,'TOTAL_CLOSER_SHOW'),total(df,'TOTAL_OFFER'),total(df,'TOTAL_SALE')]})
    st.bar_chart(funnel.set_index('STAGE'),use_container_width=True)
    initial = funnel['COUNT'].iloc[0] if len(funnel) else 0
    funnel['PERCENT_OF_INITIAL'] = funnel['COUNT'].apply(lambda x: 0 if initial==0 else round(100*x/initial,2))
    st.dataframe(funnel,use_container_width=True,hide_index=True)
    if df.empty: st.info('No data is available for the selected filters.')
    else:
        s = df.groupby('SETTER',as_index=False).agg(TOTAL_OUTBOUND_CALLS=('TOTAL_OUTBOUND_CALLS','sum'),TOTAL_LEADS_TOUCHED=('TOTAL_LEADS_TOUCHED','sum'),OUTBOUND_SET=('OUTBOUND_SET','sum'),TOTAL_CLOSER_SHOW=('TOTAL_CLOSER_SHOW','sum'),TOTAL_OFFER=('TOTAL_OFFER','sum'),TOTAL_SALE=('TOTAL_SALE','sum'),TOTAL_REVENUE=('TOTAL_REVENUE','sum'))
        s = add_rate(add_rate(add_rate(s,'DIAL_TO_SET_RATE','OUTBOUND_SET','TOTAL_OUTBOUND_CALLS'),'SET_TO_SHOW_RATE','TOTAL_CLOSER_SHOW','OUTBOUND_SET'),'SHOW_TO_SALE_RATE','TOTAL_SALE','TOTAL_CLOSER_SHOW')
        l,r=st.columns(2)
        with l: bar_chart(s.sort_values('TOTAL_OUTBOUND_CALLS',ascending=False).head(15),'SETTER','TOTAL_OUTBOUND_CALLS','Top setters by outbound calls')
        with r: bar_chart(s.sort_values('TOTAL_SALE',ascending=False).head(15),'SETTER','TOTAL_SALE','Top setters by sales')
        st.subheader('Outbound setter summary'); st.dataframe(s.sort_values(['TOTAL_SALE','TOTAL_REVENUE'],ascending=False),use_container_width=True); download_csv(s,'outbound_setter_summary.csv')

elif page == 'Closer Performance':
    st.header('Closer Performance')
    options = sorted(closer['CLOSER_NAME'].dropna().astype(str).unique().tolist()) if 'CLOSER_NAME' in closer.columns else []
    selected = st.multiselect('Closer',options,default=options)
    df = filter_values(closer,'CLOSER_NAME',selected)
    cols=st.columns(6)
    cols[0].metric('Calls booked',whole(total(df,'CALL_BOOKED')))
    cols[1].metric('Shows',whole(total(df,'STRTGY_CALL_SHW')))
    cols[2].metric('No shows',whole(total(df,'NO_SHOW')))
    cols[3].metric('Cancellations',whole(total(df,'TOTAL_CANCEL')))
    cols[4].metric('Sales',whole(total(df,'SALE')))
    cols[5].metric('Cash collected',money(total(df,'CASH_COLLECTED')))
    if df.empty: st.info('No data is available for the selected filters.')
    else:
        s = df.groupby('CLOSER_NAME',as_index=False).agg(CALL_BOOKED=('CALL_BOOKED','sum'),TOTAL_CANCEL=('TOTAL_CANCEL','sum'),NO_SHOW=('NO_SHOW','sum'),STRTGY_CALL_SHW=('STRTGY_CALL_SHW','sum'),LOST=('LOST','sum'),SALE=('SALE','sum'),CASH_COLLECTED=('CASH_COLLECTED','sum'))
        s = add_rate(add_rate(s,'SHOW_RATE','STRTGY_CALL_SHW','CALL_BOOKED'),'CLOSE_RATE','SALE','STRTGY_CALL_SHW')
        l,r=st.columns(2)
        with l: bar_chart(s.sort_values('SALE',ascending=False).head(15),'CLOSER_NAME','SALE','Sales by closer')
        with r: bar_chart(s.sort_values('CASH_COLLECTED',ascending=False).head(15),'CLOSER_NAME','CASH_COLLECTED','Cash collected by closer')
        st.subheader('Closer leaderboard'); st.dataframe(s.sort_values(['SALE','CASH_COLLECTED'],ascending=False),use_container_width=True); download_csv(s,'closer_summary.csv')

elif page == 'Objections':
    st.header('Objections Faced')
    options = sorted(objections_f['CLOSER_NAME'].dropna().astype(str).unique().tolist()) if 'CLOSER_NAME' in objections_f.columns else []
    selected = st.multiselect('Closer',options,default=options)
    df = filter_values(objections_f,'CLOSER_NAME',selected)
    mapping = {'Money':'MONEY_COUNT','Fear':'FEAR_COUNT','Hung Up':'HUNG_UP_COUNT','Logistical':'LOGISTICAL_COUNT','No Objections':'NO_OBJ_COUNT','Other Coaches':'OTHER_COACHES_COUNT','Partner':'PARTNER_COUNT','Think About It':'THINK_ABT_IT_COUNT','Time':'TIME_COUNT','Trust':'TRUST_COUNT','Value':'VALUE_COUNT','Not Looking':'NOT_LOOKING_COUNT'}
    totals = pd.DataFrame({'OBJECTION':list(mapping.keys()),'COUNT':[total(df,c) for c in mapping.values()]}).sort_values('COUNT',ascending=False)
    cols=st.columns(3)
    cols[0].metric('Total calls',whole(total(df,'TOTAL_CALLS')))
    cols[1].metric('Top objection',str(totals.iloc[0]['OBJECTION']) if not totals.empty else 'N/A')
    cols[2].metric('Top objection count',whole(totals.iloc[0]['COUNT']) if not totals.empty else '0')
    bar_chart(totals,'OBJECTION','COUNT','Objection frequency')
    st.subheader('Objections by closer')
    valid=[c for c in mapping.values() if c in df.columns]
    if not df.empty and 'CLOSER_NAME' in df.columns and valid:
        st.dataframe(df.groupby('CLOSER_NAME',as_index=False)[valid].sum(),use_container_width=True)
    else: st.info('No data is available for the selected filters.')
    st.subheader('Objection detail'); st.dataframe(df.sort_values('ACTIVITY_DATE',ascending=False) if 'ACTIVITY_DATE' in df.columns else df,use_container_width=True); download_csv(df,'objections_detail.csv')

elif page == 'Data Quality':
    st.header('Data Quality')
    checks=[]

    # Inbound row-level validation
    if 'INBOUND_TAKEN' in inbound.columns and 'INBOUND_BOOKED' in inbound.columns:
        checks.append({
            'CHECK':'Inbound taken does not exceed inbound booked',
            'INVALID_ROWS':int(
                (
                    num_series(inbound,'INBOUND_TAKEN')
                    > num_series(inbound,'INBOUND_BOOKED')
                ).sum()
            )
        })

    # Overall strategy-call validation.
    # Strategy calls may be booked on one date and taken on a later date,
    # so comparing individual daily rows can create false REVIEW results.
    if 'STRATEGY_CALL_TAKEN' in inbound.columns and 'STRATEGY_CALL_BOOKED' in inbound.columns:
        total_strategy_calls_taken = total(
            inbound,
            'STRATEGY_CALL_TAKEN'
        )

        total_strategy_calls_booked = total(
            inbound,
            'STRATEGY_CALL_BOOKED'
        )

        checks.append({
            'CHECK':'Total strategy calls taken do not exceed total strategy calls booked',
            'INVALID_ROWS':(
                1
                if total_strategy_calls_taken > total_strategy_calls_booked
                else 0
            )
        })

    # Outbound row-level funnel validations
    for name,n,d,frame in [
        (
            'Leads touched do not exceed outbound calls',
            'TOTAL_LEADS_TOUCHED',
            'TOTAL_OUTBOUND_CALLS',
            outbound
        ),
        (
            'Outbound sets do not exceed outbound calls',
            'OUTBOUND_SET',
            'TOTAL_OUTBOUND_CALLS',
            outbound
        ),
        (
            'Closer shows do not exceed outbound sets',
            'TOTAL_CLOSER_SHOW',
            'OUTBOUND_SET',
            outbound
        ),
        (
            'Offers do not exceed closer shows',
            'TOTAL_OFFER',
            'TOTAL_CLOSER_SHOW',
            outbound
        ),
        (
            'Sales do not exceed closer shows',
            'TOTAL_SALE',
            'TOTAL_CLOSER_SHOW',
            outbound
        ),
    ]:
        if n in frame.columns and d in frame.columns:
            checks.append({
                'CHECK':name,
                'INVALID_ROWS':int(
                    (
                        num_series(frame,n)
                        > num_series(frame,d)
                    ).sum()
                )
            })

    checks_df=pd.DataFrame(checks)

    if checks_df.empty:
        st.info('No data-quality checks could be evaluated.')
    else:
        checks_df['STATUS']=checks_df['INVALID_ROWS'].apply(
            lambda x:'PASS' if x==0 else 'REVIEW'
        )

        passed_checks = int(
            (checks_df['INVALID_ROWS']==0).sum()
        )

        st.metric(
            'Checks passed',
            f"{passed_checks}/{len(checks_df)}"
        )

        st.dataframe(
            checks_df,
            use_container_width=True,
            hide_index=True
        )

    st.subheader('Gold view row counts')

    st.dataframe(
        pd.DataFrame({
            'VIEW':[
                'INBOUND_SETTER_REPORT_SME',
                'OUTBOUND_SETTER_REPORT_SME',
                'CLOSER_REPORT_SME',
                'OBJECTIONS_FACED_REPORT'
            ],
            'ROWS':[
                len(inbound),
                len(outbound),
                len(closer),
                len(objections)
            ]
        }),
        use_container_width=True,
        hide_index=True
    )
