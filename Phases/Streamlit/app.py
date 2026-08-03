import pandas as pd
import streamlit as st

# =============================================================================
# PAGE CONFIGURATION
# =============================================================================

st.set_page_config(
    page_title="Sales Analytics Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATABASE = "SALES_ANALYTICS_DB"
SCHEMA = "GOLD"

# Use the current validated production views.
# Do not use the older *_SME views because they can retain obsolete
# references such as DATE_OF_SALE.
VIEWS = {
    "inbound": f"{DATABASE}.{SCHEMA}.INBOUND_SETTER_REPORT",
    "outbound": f"{DATABASE}.{SCHEMA}.OUTBOUND_SETTER_REPORT",
    "closer": f"{DATABASE}.{SCHEMA}.CLOSER_REPORT",
    "objections": f"{DATABASE}.{SCHEMA}.OBJECTIONS_FACED_REPORT",
}


# =============================================================================
# SNOWFLAKE CONNECTION
# =============================================================================

@st.cache_resource
def get_session():
    """Return the active Snowflake session for the Streamlit app."""
    return st.connection("snowflake").session()


@st.cache_data(ttl=300, show_spinner=False)
def run_query(sql: str) -> pd.DataFrame:
    """Execute Snowflake SQL and normalize all returned column names."""
    df = get_session().sql(sql).to_pandas()
    df.columns = [str(column).upper() for column in df.columns]
    return df


# =============================================================================
# GENERAL HELPERS
# =============================================================================

def money(value) -> str:
    try:
        return f"${float(value):,.0f}"
    except (TypeError, ValueError):
        return "$0"


def whole(value) -> str:
    try:
        return f"{int(round(float(value))):,}"
    except (TypeError, ValueError):
        return "0"


def pct(value) -> str:
    try:
        return f"{float(value):,.2f}%"
    except (TypeError, ValueError):
        return "0.00%"


def num_series(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(0.0, index=df.index, dtype="float64")
    return pd.to_numeric(df[column], errors="coerce").fillna(0.0)


def total(df: pd.DataFrame, column: str) -> float:
    return float(num_series(df, column).sum())


def weighted_rate(df: pd.DataFrame, numerator: str, denominator: str) -> float:
    denominator_total = total(df, denominator)
    if denominator_total == 0:
        return 0.0
    return 100.0 * total(df, numerator) / denominator_total


def prep_date(df: pd.DataFrame, column: str) -> pd.DataFrame:
    output = df.copy()
    if column in output.columns:
        output[column] = pd.to_datetime(output[column], errors="coerce")
    return output


def filter_date(
    df: pd.DataFrame,
    column: str,
    start_date,
    end_date,
) -> pd.DataFrame:
    if column not in df.columns:
        return df.copy()

    output = prep_date(df, column)
    return output[
        output[column].notna()
        & (output[column].dt.date >= start_date)
        & (output[column].dt.date <= end_date)
    ].copy()


def filter_values(
    df: pd.DataFrame,
    column: str,
    selected_values: list[str],
) -> pd.DataFrame:
    if column not in df.columns or not selected_values:
        return df.copy()

    return df[
        df[column]
        .fillna("UNMAPPED")
        .astype(str)
        .isin(selected_values)
    ].copy()


def add_rate(
    df: pd.DataFrame,
    new_column: str,
    numerator: str,
    denominator: str,
) -> pd.DataFrame:
    output = df.copy()
    denominator_series = num_series(output, denominator).replace(0, pd.NA)
    output[new_column] = (
        100.0 * num_series(output, numerator) / denominator_series
    ).fillna(0.0).round(2)
    return output


def download_csv(df: pd.DataFrame, filename: str, key: str) -> None:
    st.download_button(
        label="Download CSV",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=filename,
        mime="text/csv",
        key=key,
    )


def bar_chart(
    df: pd.DataFrame,
    label_column: str,
    value_column: str,
    title: str,
) -> None:
    st.subheader(title)

    if (
        df.empty
        or label_column not in df.columns
        or value_column not in df.columns
    ):
        st.info("No data is available for the selected filters.")
        return

    chart_df = (
        df[[label_column, value_column]]
        .dropna(subset=[label_column])
        .set_index(label_column)
    )

    st.bar_chart(chart_df, use_container_width=True)


def line_chart(
    df: pd.DataFrame,
    date_column: str,
    metric_columns: list[str],
    title: str,
) -> None:
    st.subheader(title)

    valid_metrics = [
        column for column in metric_columns if column in df.columns
    ]

    if (
        df.empty
        or date_column not in df.columns
        or not valid_metrics
    ):
        st.info("No data is available for the selected filters.")
        return

    chart_df = (
        df[[date_column] + valid_metrics]
        .dropna(subset=[date_column])
        .set_index(date_column)
        .sort_index()
    )

    st.line_chart(chart_df, use_container_width=True)


def first_existing_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for column in candidates:
        if column in df.columns:
            return column
    return None


def alias_column(
    df: pd.DataFrame,
    target: str,
    candidates: list[str],
    default_value=0,
) -> pd.DataFrame:
    """Create a canonical dashboard column from the first available source."""
    output = df.copy()

    if target in output.columns:
        return output

    source = first_existing_column(output, candidates)

    if source is not None:
        output[target] = output[source]
    else:
        output[target] = default_value

    return output


# =============================================================================
# REPORT-SCHEMA NORMALIZATION
# =============================================================================

def normalize_inbound(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize the current INBOUND_SETTER_REPORT into stable dashboard names.
    """
    output = df.copy()

    mappings = {
        "TRIAGE_DATE": ["TRIAGE_DATE", "ACTIVITY_DATE", "ACTIVITY_LOG_DATE"],
        "SETTER": ["SETTER", "SETTER_NAME", "SETTER_CLOSER_NAME"],
        "INBOUND_BOOKED": ["INBOUND_BOOKED"],
        "INBOUND_TAKEN": ["INBOUND_TAKEN"],
        "STRATEGY_CALL_BOOKED": ["STRATEGY_CALL_BOOKED"],
        "STRATEGY_CALL_TAKEN": ["STRATEGY_CALL_TAKEN"],
        "OFFERS_PRESENTED": ["OFFERS_PRESENTED", "TOTAL_OFFER"],
        "TOTAL_SALES": ["TOTAL_SALES", "TOTAL_SALE"],
        "TOTAL_REVENUE": [
            "TOTAL_REVENUE",
            "TOTAL_CONTRACT_VALUE",
            "CONTRACTED_VALUE",
        ],
    }

    for target, candidates in mappings.items():
        output = alias_column(output, target, candidates)

    output = prep_date(output, "TRIAGE_DATE")
    return output


def normalize_outbound(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize the current OUTBOUND_SETTER_REPORT.

    Current production columns include OUTBOUND_DATE, OUTBOUND_DIALS,
    STRATEGY_CALL_BOOKED, STRATEGY_CALL_TAKEN, OFFERS_PRESENTED,
    TOTAL_SALES, and TOTAL_CONTRACT_VALUE.
    """
    output = df.copy()

    mappings = {
        "DIAL_DATE": ["DIAL_DATE", "OUTBOUND_DATE", "ACTIVITY_DATE"],
        "SETTER": ["SETTER", "SETTER_NAME", "SETTER_CLOSER_NAME"],
        "TOTAL_OUTBOUND_CALLS": [
            "TOTAL_OUTBOUND_CALLS",
            "OUTBOUND_DIALS",
        ],
        "TOTAL_LEADS_TOUCHED": ["TOTAL_LEADS_TOUCHED"],
        "OUTBOUND_SET": ["OUTBOUND_SET", "STRATEGY_CALL_BOOKED"],
        "TOTAL_CLOSER_SHOW": [
            "TOTAL_CLOSER_SHOW",
            "STRATEGY_CALL_TAKEN",
        ],
        "TOTAL_OFFER": ["TOTAL_OFFER", "OFFERS_PRESENTED"],
        "TOTAL_SALE": ["TOTAL_SALE", "TOTAL_SALES"],
        "TOTAL_REVENUE": [
            "TOTAL_REVENUE",
            "TOTAL_CONTRACT_VALUE",
        ],
        "TOTAL_CASH_COLLECTED": ["TOTAL_CASH_COLLECTED"],
    }

    for target, candidates in mappings.items():
        output = alias_column(output, target, candidates)

    output = prep_date(output, "DIAL_DATE")
    return output


def normalize_closer(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize the current CLOSER_REPORT.

    The current deployed report uses:
      STRATEGY_CALLS
      STRATEGY_CALL_TAKEN
      OFFERS_PRESENTED
      TOTAL_SALES
      TOTAL_CONTRACT_VALUE
      TOTAL_CASH_COLLECTED
    """
    output = df.copy()

    mappings = {
        "CLOSER_NAME": ["CLOSER_NAME", "CLOSER"],
        "CALL_YEAR_MONTH": [
            "CALL_YEAR_MONTH",
            "ACTIVITY_MONTH",
            "REPORTING_MONTH",
        ],
        "STRATEGY_CALLS": ["STRATEGY_CALLS", "CALL_BOOKED"],
        "STRATEGY_CALL_TAKEN": [
            "STRATEGY_CALL_TAKEN",
            "STRTGY_CALL_SHW",
        ],
        "OFFERS_PRESENTED": ["OFFERS_PRESENTED"],
        "TOTAL_SALES": ["TOTAL_SALES", "SALE"],
        "TOTAL_CONTRACT_VALUE": [
            "TOTAL_CONTRACT_VALUE",
            "AVG_VALUE",
        ],
        "TOTAL_CASH_COLLECTED": [
            "TOTAL_CASH_COLLECTED",
            "CASH_COLLECTED",
        ],
        "AVERAGE_CONTRACT_VALUE": [
            "AVERAGE_CONTRACT_VALUE",
            "AVG_VALUE",
            "AVG_VAUE",
        ],
        "AVERAGE_CASH_COLLECTED": ["AVERAGE_CASH_COLLECTED"],
    }

    for target, candidates in mappings.items():
        output = alias_column(output, target, candidates)

    return output


def normalize_objections(df: pd.DataFrame) -> pd.DataFrame:
    output = df.copy()

    mappings = {
        "ACTIVITY_DATE": [
            "ACTIVITY_DATE",
            "DATE_OF_STRATEGY_CALL",
            "ACTIVITY_LOG_DATE",
        ],
        "CLOSER_NAME": ["CLOSER_NAME", "CLOSER"],
        "TOTAL_CALLS": ["TOTAL_CALLS"],
        "MONEY_COUNT": ["MONEY_COUNT"],
        "FEAR_COUNT": ["FEAR_COUNT"],
        "HUNG_UP_COUNT": ["HUNG_UP_COUNT"],
        "LOGISTICAL_COUNT": ["LOGISTICAL_COUNT"],
        "NO_OBJ_COUNT": ["NO_OBJ_COUNT"],
        "OTHER_COACHES_COUNT": ["OTHER_COACHES_COUNT"],
        "PARTNER_COUNT": ["PARTNER_COUNT"],
        "THINK_ABT_IT_COUNT": ["THINK_ABT_IT_COUNT"],
        "TIME_COUNT": ["TIME_COUNT"],
        "TRUST_COUNT": ["TRUST_COUNT"],
        "VALUE_COUNT": ["VALUE_COUNT"],
        "NOT_LOOKING_COUNT": ["NOT_LOOKING_COUNT"],
    }

    for target, candidates in mappings.items():
        output = alias_column(output, target, candidates)

    output = prep_date(output, "ACTIVITY_DATE")
    return output


# =============================================================================
# PAGE HEADER AND SIDEBAR
# =============================================================================

st.title("Sales Analytics Dashboard")
st.caption(
    "Snowflake-native Streamlit dashboard built from the validated Gold reports."
)

with st.sidebar:
    st.header("Navigation")

    page = st.radio(
        "Dashboard page",
        [
            "Executive Overview",
            "Inbound Setter",
            "Outbound Setter",
            "Closer Performance",
            "Objections",
            "Data Quality",
        ],
        label_visibility="collapsed",
    )

    st.divider()
    st.caption("Snowflake results are cached for five minutes.")

    if st.button("Refresh data", use_container_width=True):
        run_query.clear()
        get_session.clear()
        st.rerun()


# =============================================================================
# LOAD CURRENT PRODUCTION REPORT VIEWS
# =============================================================================

try:
    with st.spinner("Loading the latest validated reports from Snowflake..."):
        inbound_raw = run_query(
            f"SELECT * FROM {VIEWS['inbound']}"
        )
        outbound_raw = run_query(
            f"SELECT * FROM {VIEWS['outbound']}"
        )
        closer_raw = run_query(
            f"SELECT * FROM {VIEWS['closer']}"
        )
        objections_raw = run_query(
            f"SELECT * FROM {VIEWS['objections']}"
        )

        inbound = normalize_inbound(inbound_raw)
        outbound = normalize_outbound(outbound_raw)
        closer = normalize_closer(closer_raw)
        objections = normalize_objections(objections_raw)

except Exception as exc:
    st.error("The app could not query the current Snowflake Gold reports.")
    st.code(str(exc))
    st.info(
        "Verify that the app owner role has USAGE on "
        "SALES_ANALYTICS_DB and GOLD, and SELECT on the four report views."
    )
    st.stop()


# =============================================================================
# GLOBAL DATE FILTER
# =============================================================================

all_dates = []

for frame, column in [
    (inbound, "TRIAGE_DATE"),
    (outbound, "DIAL_DATE"),
    (objections, "ACTIVITY_DATE"),
]:
    if column in frame.columns and not frame[column].dropna().empty:
        all_dates.extend(frame[column].dropna().dt.date.tolist())

today = pd.Timestamp.today().date()
min_date = min(all_dates) if all_dates else today
max_date = max(all_dates) if all_dates else today

with st.sidebar:
    st.header("Global date filter")

    selected_range = st.date_input(
        "Date range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )

    if isinstance(selected_range, tuple) and len(selected_range) == 2:
        start_date, end_date = selected_range
    else:
        start_date = selected_range
        end_date = selected_range


inbound_filtered = filter_date(
    inbound,
    "TRIAGE_DATE",
    start_date,
    end_date,
)

outbound_filtered = filter_date(
    outbound,
    "DIAL_DATE",
    start_date,
    end_date,
)

objections_filtered = filter_date(
    objections,
    "ACTIVITY_DATE",
    start_date,
    end_date,
)


# =============================================================================
# EXECUTIVE OVERVIEW
# =============================================================================

if page == "Executive Overview":
    st.header("Executive Overview")

    metric_columns = st.columns(6)

    metric_columns[0].metric(
        "Inbound calls",
        whole(total(inbound_filtered, "INBOUND_BOOKED")),
    )

    metric_columns[1].metric(
        "Outbound calls",
        whole(total(outbound_filtered, "TOTAL_OUTBOUND_CALLS")),
    )

    metric_columns[2].metric(
        "Inbound sales",
        whole(total(inbound_filtered, "TOTAL_SALES")),
    )

    metric_columns[3].metric(
        "Outbound sales",
        whole(total(outbound_filtered, "TOTAL_SALE")),
    )

    metric_columns[4].metric(
        "Outbound revenue",
        money(total(outbound_filtered, "TOTAL_REVENUE")),
    )

    metric_columns[5].metric(
        "Cash collected",
        money(total(closer, "TOTAL_CASH_COLLECTED")),
    )

    st.subheader("Conversion performance")

    conversion_columns = st.columns(4)

    conversion_columns[0].metric(
        "Inbound show rate",
        pct(
            weighted_rate(
                inbound_filtered,
                "INBOUND_TAKEN",
                "INBOUND_BOOKED",
            )
        ),
    )

    conversion_columns[1].metric(
        "Inbound sale rate",
        pct(
            weighted_rate(
                inbound_filtered,
                "TOTAL_SALES",
                "STRATEGY_CALL_TAKEN",
            )
        ),
    )

    conversion_columns[2].metric(
        "Outbound dial-to-set",
        pct(
            weighted_rate(
                outbound_filtered,
                "OUTBOUND_SET",
                "TOTAL_OUTBOUND_CALLS",
            )
        ),
    )

    conversion_columns[3].metric(
        "Outbound show-to-sale",
        pct(
            weighted_rate(
                outbound_filtered,
                "TOTAL_SALE",
                "TOTAL_CLOSER_SHOW",
            )
        ),
    )

    if not inbound_filtered.empty:
        inbound_daily = (
            inbound_filtered.groupby(
                "TRIAGE_DATE",
                as_index=False,
            )[
                [
                    "INBOUND_BOOKED",
                    "INBOUND_TAKEN",
                    "TOTAL_SALES",
                ]
            ]
            .sum()
        )
    else:
        inbound_daily = pd.DataFrame()

    if not outbound_filtered.empty:
        outbound_daily = (
            outbound_filtered.groupby(
                "DIAL_DATE",
                as_index=False,
            )[
                [
                    "TOTAL_OUTBOUND_CALLS",
                    "OUTBOUND_SET",
                    "TOTAL_CLOSER_SHOW",
                    "TOTAL_SALE",
                ]
            ]
            .sum()
        )
    else:
        outbound_daily = pd.DataFrame()

    left_column, right_column = st.columns(2)

    with left_column:
        line_chart(
            inbound_daily,
            "TRIAGE_DATE",
            [
                "INBOUND_BOOKED",
                "INBOUND_TAKEN",
                "TOTAL_SALES",
            ],
            "Inbound performance trend",
        )

    with right_column:
        line_chart(
            outbound_daily,
            "DIAL_DATE",
            [
                "TOTAL_OUTBOUND_CALLS",
                "OUTBOUND_SET",
                "TOTAL_CLOSER_SHOW",
                "TOTAL_SALE",
            ],
            "Outbound performance trend",
        )


# =============================================================================
# INBOUND SETTER PAGE
# =============================================================================

elif page == "Inbound Setter":
    st.header("Inbound Setter Performance")

    setter_options = (
        sorted(
            inbound_filtered["SETTER"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )
        if "SETTER" in inbound_filtered.columns
        else []
    )

    selected_setters = st.multiselect(
        "Setter",
        setter_options,
        default=setter_options,
    )

    df = filter_values(
        inbound_filtered,
        "SETTER",
        selected_setters,
    )

    metric_columns = st.columns(6)

    metric_columns[0].metric(
        "Inbound booked",
        whole(total(df, "INBOUND_BOOKED")),
    )

    metric_columns[1].metric(
        "Inbound taken",
        whole(total(df, "INBOUND_TAKEN")),
    )

    metric_columns[2].metric(
        "Show rate",
        pct(weighted_rate(df, "INBOUND_TAKEN", "INBOUND_BOOKED")),
    )

    metric_columns[3].metric(
        "Strategy calls booked",
        whole(total(df, "STRATEGY_CALL_BOOKED")),
    )

    metric_columns[4].metric(
        "Strategy calls taken",
        whole(total(df, "STRATEGY_CALL_TAKEN")),
    )

    metric_columns[5].metric(
        "Total sales",
        whole(total(df, "TOTAL_SALES")),
    )

    if df.empty:
        st.info("No data is available for the selected filters.")
    else:
        summary = (
            df.groupby("SETTER", as_index=False)
            .agg(
                INBOUND_BOOKED=("INBOUND_BOOKED", "sum"),
                INBOUND_TAKEN=("INBOUND_TAKEN", "sum"),
                STRATEGY_CALL_BOOKED=("STRATEGY_CALL_BOOKED", "sum"),
                STRATEGY_CALL_TAKEN=("STRATEGY_CALL_TAKEN", "sum"),
                OFFERS_PRESENTED=("OFFERS_PRESENTED", "sum"),
                TOTAL_SALES=("TOTAL_SALES", "sum"),
            )
        )

        summary = add_rate(
            summary,
            "SHOW_RATE",
            "INBOUND_TAKEN",
            "INBOUND_BOOKED",
        )

        summary = add_rate(
            summary,
            "SALE_RATE",
            "TOTAL_SALES",
            "STRATEGY_CALL_TAKEN",
        )

        left_column, right_column = st.columns(2)

        with left_column:
            bar_chart(
                summary.sort_values(
                    "INBOUND_BOOKED",
                    ascending=False,
                ).head(15),
                "SETTER",
                "INBOUND_BOOKED",
                "Top setters by inbound calls",
            )

        with right_column:
            bar_chart(
                summary.sort_values(
                    "TOTAL_SALES",
                    ascending=False,
                ).head(15),
                "SETTER",
                "TOTAL_SALES",
                "Top setters by sales",
            )

        st.subheader("Inbound setter summary")

        st.dataframe(
            summary.sort_values(
                ["TOTAL_SALES", "INBOUND_BOOKED"],
                ascending=False,
            ),
            use_container_width=True,
            hide_index=True,
        )

        download_csv(
            summary,
            "inbound_setter_summary.csv",
            "download_inbound",
        )


# =============================================================================
# OUTBOUND SETTER PAGE
# =============================================================================

elif page == "Outbound Setter":
    st.header("Outbound Setter Performance")

    setter_options = (
        sorted(
            outbound_filtered["SETTER"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )
        if "SETTER" in outbound_filtered.columns
        else []
    )

    selected_setters = st.multiselect(
        "Setter",
        setter_options,
        default=setter_options,
    )

    df = filter_values(
        outbound_filtered,
        "SETTER",
        selected_setters,
    )

    metric_columns = st.columns(6)

    metric_columns[0].metric(
        "Outbound calls",
        whole(total(df, "TOTAL_OUTBOUND_CALLS")),
    )

    metric_columns[1].metric(
        "Leads touched",
        whole(total(df, "TOTAL_LEADS_TOUCHED")),
    )

    metric_columns[2].metric(
        "Outbound sets",
        whole(total(df, "OUTBOUND_SET")),
    )

    metric_columns[3].metric(
        "Closer shows",
        whole(total(df, "TOTAL_CLOSER_SHOW")),
    )

    metric_columns[4].metric(
        "Sales",
        whole(total(df, "TOTAL_SALE")),
    )

    metric_columns[5].metric(
        "Revenue",
        money(total(df, "TOTAL_REVENUE")),
    )

    st.subheader("Outbound conversion funnel")

    funnel = pd.DataFrame(
        {
            "STAGE": [
                "Outbound Calls",
                "Outbound Set",
                "Closer Show",
                "Offer",
                "Sale",
            ],
            "COUNT": [
                total(df, "TOTAL_OUTBOUND_CALLS"),
                total(df, "OUTBOUND_SET"),
                total(df, "TOTAL_CLOSER_SHOW"),
                total(df, "TOTAL_OFFER"),
                total(df, "TOTAL_SALE"),
            ],
        }
    )

    st.bar_chart(
        funnel.set_index("STAGE"),
        use_container_width=True,
    )

    initial_count = funnel["COUNT"].iloc[0] if not funnel.empty else 0

    funnel["PERCENT_OF_INITIAL"] = funnel["COUNT"].apply(
        lambda value: (
            0.0
            if initial_count == 0
            else round(100.0 * value / initial_count, 2)
        )
    )

    st.dataframe(
        funnel,
        use_container_width=True,
        hide_index=True,
    )

    if df.empty:
        st.info("No data is available for the selected filters.")
    else:
        summary = (
            df.groupby("SETTER", as_index=False)
            .agg(
                TOTAL_OUTBOUND_CALLS=("TOTAL_OUTBOUND_CALLS", "sum"),
                TOTAL_LEADS_TOUCHED=("TOTAL_LEADS_TOUCHED", "sum"),
                OUTBOUND_SET=("OUTBOUND_SET", "sum"),
                TOTAL_CLOSER_SHOW=("TOTAL_CLOSER_SHOW", "sum"),
                TOTAL_OFFER=("TOTAL_OFFER", "sum"),
                TOTAL_SALE=("TOTAL_SALE", "sum"),
                TOTAL_REVENUE=("TOTAL_REVENUE", "sum"),
            )
        )

        summary = add_rate(
            summary,
            "DIAL_TO_SET_RATE",
            "OUTBOUND_SET",
            "TOTAL_OUTBOUND_CALLS",
        )

        summary = add_rate(
            summary,
            "SET_TO_SHOW_RATE",
            "TOTAL_CLOSER_SHOW",
            "OUTBOUND_SET",
        )

        summary = add_rate(
            summary,
            "SHOW_TO_SALE_RATE",
            "TOTAL_SALE",
            "TOTAL_CLOSER_SHOW",
        )

        left_column, right_column = st.columns(2)

        with left_column:
            bar_chart(
                summary.sort_values(
                    "TOTAL_OUTBOUND_CALLS",
                    ascending=False,
                ).head(15),
                "SETTER",
                "TOTAL_OUTBOUND_CALLS",
                "Top setters by outbound calls",
            )

        with right_column:
            bar_chart(
                summary.sort_values(
                    "TOTAL_SALE",
                    ascending=False,
                ).head(15),
                "SETTER",
                "TOTAL_SALE",
                "Top setters by sales",
            )

        st.subheader("Outbound setter summary")

        st.dataframe(
            summary.sort_values(
                ["TOTAL_SALE", "TOTAL_REVENUE"],
                ascending=False,
            ),
            use_container_width=True,
            hide_index=True,
        )

        download_csv(
            summary,
            "outbound_setter_summary.csv",
            "download_outbound",
        )


# =============================================================================
# CLOSER PAGE
# =============================================================================

elif page == "Closer Performance":
    st.header("Closer Performance")

    closer_options = (
        sorted(
            closer["CLOSER_NAME"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )
        if "CLOSER_NAME" in closer.columns
        else []
    )

    selected_closers = st.multiselect(
        "Closer",
        closer_options,
        default=closer_options,
    )

    df = filter_values(
        closer,
        "CLOSER_NAME",
        selected_closers,
    )

    metric_columns = st.columns(6)

    metric_columns[0].metric(
        "Strategy calls",
        whole(total(df, "STRATEGY_CALLS")),
    )

    metric_columns[1].metric(
        "Calls taken",
        whole(total(df, "STRATEGY_CALL_TAKEN")),
    )

    metric_columns[2].metric(
        "Show rate",
        pct(
            weighted_rate(
                df,
                "STRATEGY_CALL_TAKEN",
                "STRATEGY_CALLS",
            )
        ),
    )

    metric_columns[3].metric(
        "Offers presented",
        whole(total(df, "OFFERS_PRESENTED")),
    )

    metric_columns[4].metric(
        "Sales",
        whole(total(df, "TOTAL_SALES")),
    )

    metric_columns[5].metric(
        "Cash collected",
        money(total(df, "TOTAL_CASH_COLLECTED")),
    )

    if df.empty:
        st.info("No data is available for the selected filters.")
    else:
        summary = (
            df.groupby("CLOSER_NAME", as_index=False)
            .agg(
                STRATEGY_CALLS=("STRATEGY_CALLS", "sum"),
                STRATEGY_CALL_TAKEN=("STRATEGY_CALL_TAKEN", "sum"),
                OFFERS_PRESENTED=("OFFERS_PRESENTED", "sum"),
                TOTAL_SALES=("TOTAL_SALES", "sum"),
                TOTAL_CONTRACT_VALUE=("TOTAL_CONTRACT_VALUE", "sum"),
                TOTAL_CASH_COLLECTED=("TOTAL_CASH_COLLECTED", "sum"),
            )
        )

        summary = add_rate(
            summary,
            "SHOW_RATE",
            "STRATEGY_CALL_TAKEN",
            "STRATEGY_CALLS",
        )

        summary = add_rate(
            summary,
            "CLOSE_RATE",
            "TOTAL_SALES",
            "STRATEGY_CALL_TAKEN",
        )

        left_column, right_column = st.columns(2)

        with left_column:
            bar_chart(
                summary.sort_values(
                    "TOTAL_SALES",
                    ascending=False,
                ).head(15),
                "CLOSER_NAME",
                "TOTAL_SALES",
                "Sales by closer",
            )

        with right_column:
            bar_chart(
                summary.sort_values(
                    "TOTAL_CASH_COLLECTED",
                    ascending=False,
                ).head(15),
                "CLOSER_NAME",
                "TOTAL_CASH_COLLECTED",
                "Cash collected by closer",
            )

        st.subheader("Closer leaderboard")

        st.dataframe(
            summary.sort_values(
                ["TOTAL_SALES", "TOTAL_CASH_COLLECTED"],
                ascending=False,
            ),
            use_container_width=True,
            hide_index=True,
        )

        download_csv(
            summary,
            "closer_summary.csv",
            "download_closer",
        )


# =============================================================================
# OBJECTIONS PAGE
# =============================================================================

elif page == "Objections":
    st.header("Objections Faced")

    closer_options = (
        sorted(
            objections_filtered["CLOSER_NAME"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )
        if "CLOSER_NAME" in objections_filtered.columns
        else []
    )

    selected_closers = st.multiselect(
        "Closer",
        closer_options,
        default=closer_options,
    )

    df = filter_values(
        objections_filtered,
        "CLOSER_NAME",
        selected_closers,
    )

    objection_mapping = {
        "Money": "MONEY_COUNT",
        "Fear": "FEAR_COUNT",
        "Hung Up": "HUNG_UP_COUNT",
        "Logistical": "LOGISTICAL_COUNT",
        "No Objections": "NO_OBJ_COUNT",
        "Other Coaches": "OTHER_COACHES_COUNT",
        "Partner": "PARTNER_COUNT",
        "Think About It": "THINK_ABT_IT_COUNT",
        "Time": "TIME_COUNT",
        "Trust": "TRUST_COUNT",
        "Value": "VALUE_COUNT",
        "Not Looking": "NOT_LOOKING_COUNT",
    }

    objection_totals = pd.DataFrame(
        {
            "OBJECTION": list(objection_mapping.keys()),
            "COUNT": [
                total(df, column)
                for column in objection_mapping.values()
            ],
        }
    ).sort_values("COUNT", ascending=False)

    metric_columns = st.columns(3)

    metric_columns[0].metric(
        "Total calls",
        whole(total(df, "TOTAL_CALLS")),
    )

    metric_columns[1].metric(
        "Top objection",
        (
            str(objection_totals.iloc[0]["OBJECTION"])
            if not objection_totals.empty
            else "N/A"
        ),
    )

    metric_columns[2].metric(
        "Top objection count",
        (
            whole(objection_totals.iloc[0]["COUNT"])
            if not objection_totals.empty
            else "0"
        ),
    )

    bar_chart(
        objection_totals,
        "OBJECTION",
        "COUNT",
        "Objection frequency",
    )

    st.subheader("Objections by closer")

    valid_columns = [
        column
        for column in objection_mapping.values()
        if column in df.columns
    ]

    if (
        not df.empty
        and "CLOSER_NAME" in df.columns
        and valid_columns
    ):
        objections_by_closer = (
            df.groupby(
                "CLOSER_NAME",
                as_index=False,
            )[valid_columns]
            .sum()
        )

        st.dataframe(
            objections_by_closer,
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No data is available for the selected filters.")

    st.subheader("Objection detail")

    if "ACTIVITY_DATE" in df.columns:
        objection_detail = df.sort_values(
            "ACTIVITY_DATE",
            ascending=False,
        )
    else:
        objection_detail = df

    st.dataframe(
        objection_detail,
        use_container_width=True,
        hide_index=True,
    )

    download_csv(
        objection_detail,
        "objections_detail.csv",
        "download_objections",
    )


# =============================================================================
# DATA QUALITY PAGE
# =============================================================================

elif page == "Data Quality":
    st.header("Data Quality")

    checks = []

    inbound_booked = total(inbound, "INBOUND_BOOKED")
    inbound_taken = total(inbound, "INBOUND_TAKEN")
    inbound_strategy_booked = total(inbound, "STRATEGY_CALL_BOOKED")
    inbound_strategy_taken = total(inbound, "STRATEGY_CALL_TAKEN")
    inbound_sales = total(inbound, "TOTAL_SALES")

    checks.extend(
        [
            {
                "CHECK": "Inbound calls taken do not exceed inbound calls booked",
                "STATUS": (
                    "PASS"
                    if inbound_taken <= inbound_booked
                    else "REVIEW"
                ),
                "DETAIL": (
                    f"{whole(inbound_taken)} taken / "
                    f"{whole(inbound_booked)} booked"
                ),
            },
            {
                "CHECK": "Inbound strategy calls taken do not exceed strategy calls booked",
                "STATUS": (
                    "PASS"
                    if inbound_strategy_taken <= inbound_strategy_booked
                    else "REVIEW"
                ),
                "DETAIL": (
                    f"{whole(inbound_strategy_taken)} taken / "
                    f"{whole(inbound_strategy_booked)} booked"
                ),
            },
            {
                "CHECK": "Inbound sales do not exceed strategy calls taken",
                "STATUS": (
                    "PASS"
                    if inbound_sales <= inbound_strategy_taken
                    else "REVIEW"
                ),
                "DETAIL": (
                    f"{whole(inbound_sales)} sales / "
                    f"{whole(inbound_strategy_taken)} calls taken"
                ),
            },
        ]
    )

    outbound_calls = total(outbound, "TOTAL_OUTBOUND_CALLS")
    outbound_leads = total(outbound, "TOTAL_LEADS_TOUCHED")
    outbound_sets = total(outbound, "OUTBOUND_SET")
    outbound_shows = total(outbound, "TOTAL_CLOSER_SHOW")
    outbound_sales = total(outbound, "TOTAL_SALE")

    checks.extend(
        [
            {
                "CHECK": "Outbound leads touched do not exceed outbound calls",
                "STATUS": (
                    "PASS"
                    if outbound_leads <= outbound_calls
                    else "REVIEW"
                ),
                "DETAIL": (
                    f"{whole(outbound_leads)} leads / "
                    f"{whole(outbound_calls)} calls"
                ),
            },
            {
                "CHECK": "Outbound sets do not exceed outbound calls",
                "STATUS": (
                    "PASS"
                    if outbound_sets <= outbound_calls
                    else "REVIEW"
                ),
                "DETAIL": (
                    f"{whole(outbound_sets)} sets / "
                    f"{whole(outbound_calls)} calls"
                ),
            },
            {
                "CHECK": "Closer shows do not exceed outbound sets",
                "STATUS": (
                    "PASS"
                    if outbound_shows <= outbound_sets
                    else "REVIEW"
                ),
                "DETAIL": (
                    f"{whole(outbound_shows)} shows / "
                    f"{whole(outbound_sets)} sets"
                ),
            },
            {
                "CHECK": "Outbound sales do not exceed closer shows",
                "STATUS": (
                    "PASS"
                    if outbound_sales <= outbound_shows
                    else "REVIEW"
                ),
                "DETAIL": (
                    f"{whole(outbound_sales)} sales / "
                    f"{whole(outbound_shows)} shows"
                ),
            },
        ]
    )

    closer_calls = total(closer, "STRATEGY_CALLS")
    closer_taken = total(closer, "STRATEGY_CALL_TAKEN")
    closer_offers = total(closer, "OFFERS_PRESENTED")
    closer_sales = total(closer, "TOTAL_SALES")

    checks.extend(
        [
            {
                "CHECK": "Closer calls taken do not exceed strategy calls",
                "STATUS": (
                    "PASS"
                    if closer_taken <= closer_calls
                    else "REVIEW"
                ),
                "DETAIL": (
                    f"{whole(closer_taken)} taken / "
                    f"{whole(closer_calls)} calls"
                ),
            },
            {
                "CHECK": "Closer offers do not exceed calls taken",
                "STATUS": (
                    "PASS"
                    if closer_offers <= closer_taken
                    else "REVIEW"
                ),
                "DETAIL": (
                    f"{whole(closer_offers)} offers / "
                    f"{whole(closer_taken)} calls taken"
                ),
            },
            {
                "CHECK": "Closer sales do not exceed calls taken",
                "STATUS": (
                    "PASS"
                    if closer_sales <= closer_taken
                    else "REVIEW"
                ),
                "DETAIL": (
                    f"{whole(closer_sales)} sales / "
                    f"{whole(closer_taken)} calls taken"
                ),
            },
        ]
    )

    checks_df = pd.DataFrame(checks)

    passed_checks = int((checks_df["STATUS"] == "PASS").sum())

    st.metric(
        "Checks passed",
        f"{passed_checks}/{len(checks_df)}",
    )

    st.dataframe(
        checks_df,
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Current Gold report row counts")

    row_counts = pd.DataFrame(
        {
            "VIEW": [
                "INBOUND_SETTER_REPORT",
                "OUTBOUND_SETTER_REPORT",
                "CLOSER_REPORT",
                "OBJECTIONS_FACED_REPORT",
            ],
            "ROWS": [
                len(inbound_raw),
                len(outbound_raw),
                len(closer_raw),
                len(objections_raw),
            ],
        }
    )

    st.dataframe(
        row_counts,
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Current source columns")

    with st.expander("Show loaded report columns"):
        st.write(
            {
                "INBOUND_SETTER_REPORT": inbound_raw.columns.tolist(),
                "OUTBOUND_SETTER_REPORT": outbound_raw.columns.tolist(),
                "CLOSER_REPORT": closer_raw.columns.tolist(),
                "OBJECTIONS_FACED_REPORT": objections_raw.columns.tolist(),
            }
        )
