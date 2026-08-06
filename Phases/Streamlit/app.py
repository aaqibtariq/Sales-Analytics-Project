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
GOLD_SCHEMA = "GOLD"
BRONZE_SCHEMA = "BRONZE"

VIEWS = {
    "inbound": f"{DATABASE}.{GOLD_SCHEMA}.INBOUND_SETTER_REPORT",
    "outbound": f"{DATABASE}.{GOLD_SCHEMA}.OUTBOUND_SETTER_REPORT",
    "closer": f"{DATABASE}.{GOLD_SCHEMA}.CLOSER_REPORT",
    "objections": f"{DATABASE}.{GOLD_SCHEMA}.OBJECTIONS_FACED_REPORT",
}

REQUIRED_COLUMNS = {
    "INBOUND_SETTER_REPORT": [
        "TRIAGE_DATE",
        "SETTER",
        "SETTER_EMAIL",
        "INBOUND_BOOKED",
        "INBOUND_TAKEN",
        "SHOW_RATE",
        "TRIAGE_SET_RATE",
        "STRATEGY_CALL_BOOKED",
        "STRATEGY_CALL_TAKEN",
        "OFFERS_PRESENTED",
        "OFFER_RATE",
        "TOTAL_SALES",
        "SALE_RATE",
        "AVERAGE_ORDER_VALUE",
    ],
    "OUTBOUND_SETTER_REPORT": [
        "OUTBOUND_DATE",
        "REPORTING_WEEK",
        "SETTER",
        "SETTER_EMAIL",
        "OUTBOUND_DIALS",
        "TOTAL_LEADS_TOUCHED",
        "OUTBOUND_TAKEN",
        "CONNECT_RATE",
        "STRATEGY_CALL_BOOKED",
        "SET_RATE",
        "STRATEGY_CALL_TAKEN",
        "OFFERS_PRESENTED",
        "OFFER_RATE",
        "TOTAL_SALES",
        "SALE_RATE",
        "AVERAGE_ORDER_VALUE",
        "TOTAL_CONTRACT_VALUE",
        "TOTAL_CASH_COLLECTED",
    ],
    "CLOSER_REPORT": [
        "STRATEGY_DATE",
        "REPORTING_WEEK",
        "CLOSER",
        "CLOSER_EMAIL",
        "STRATEGY_CALLS",
        "STRATEGY_CALL_TAKEN",
        "SHOW_RATE",
        "OFFERS_PRESENTED",
        "OFFER_RATE",
        "TOTAL_SALES",
        "SALE_RATE",
        "OFFER_TO_SALE_RATE",
        "TOTAL_CONTRACT_VALUE",
        "TOTAL_CASH_COLLECTED",
        "AVERAGE_CONTRACT_VALUE",
        "AVERAGE_CASH_COLLECTED",
    ],
    "OBJECTIONS_FACED_REPORT": [
        "CLOSER_NAME",
        "CLOSER_EMAIL",
        "ACTIVITY_DATE",
        "TOTAL_CALLS",
        "MONEY_COUNT",
        "FEAR_COUNT",
        "HUNG_UP_COUNT",
        "LOGISTICAL_COUNT",
        "NO_OBJ_COUNT",
        "OTHER_COACHES_COUNT",
        "PARTNER_COUNT",
        "THINK_ABT_IT_COUNT",
        "TIME_COUNT",
        "TRUST_COUNT",
        "VALUE_COUNT",
        "NOT_LOOKING_COUNT",
        "MONEY%",
        "FEAR%",
        "HUNG UP%",
        "LOGISTICAL%",
        "NO OBJ%",
        "OTHER COACHES%",
        "PARTNER%",
        "THINK ABT IT%",
        "TIME%",
        "TRUST%",
        "VALUE%",
        "WSN'T LKNG FR WHT WE OFFRD%",
    ],
}


# =============================================================================
# SNOWFLAKE CONNECTION
# =============================================================================

@st.cache_resource
def get_session():
    return st.connection("snowflake").session()


@st.cache_data(ttl=300, show_spinner=False)
def run_query(sql: str) -> pd.DataFrame:
    df = get_session().sql(sql).to_pandas()
    df.columns = [str(column).upper() for column in df.columns]
    return df


# =============================================================================
# FORMATTERS AND HELPERS
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


def numeric_series(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(0.0, index=df.index, dtype="float64")
    return pd.to_numeric(df[column], errors="coerce").fillna(0.0)


def total(df: pd.DataFrame, column: str) -> float:
    return float(numeric_series(df, column).sum())


def weighted_rate(df: pd.DataFrame, numerator: str, denominator: str) -> float:
    denominator_total = total(df, denominator)
    if denominator_total == 0:
        return 0.0
    return round(100.0 * total(df, numerator) / denominator_total, 2)


def safe_divide(numerator, denominator) -> float:
    try:
        numerator = float(numerator)
        denominator = float(denominator)
        if denominator == 0:
            return 0.0
        return round(100.0 * numerator / denominator, 2)
    except (TypeError, ValueError):
        return 0.0


def prepare_date(df: pd.DataFrame, column: str) -> pd.DataFrame:
    output = df.copy()
    output[column] = pd.to_datetime(output[column], errors="coerce")
    return output


def filter_date(
    df: pd.DataFrame,
    column: str,
    start_date,
    end_date,
) -> pd.DataFrame:
    output = prepare_date(df, column)
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
    if not selected_values:
        return df.iloc[0:0].copy()

    return df[
        df[column]
        .fillna("UNMAPPED")
        .astype(str)
        .isin(selected_values)
    ].copy()


def require_columns(
    df: pd.DataFrame,
    required_columns: list[str],
    report_name: str,
) -> None:
    missing = [
        column for column in required_columns
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            f"{report_name} is missing required columns: "
            + ", ".join(missing)
        )


def add_rate(
    df: pd.DataFrame,
    new_column: str,
    numerator: str,
    denominator: str,
) -> pd.DataFrame:
    output = df.copy()
    denominator_values = numeric_series(output, denominator).replace(0, pd.NA)

    output[new_column] = (
        100.0 * numeric_series(output, numerator) / denominator_values
    ).fillna(0.0).round(2)

    return output


def add_average(
    df: pd.DataFrame,
    new_column: str,
    numerator: str,
    denominator: str,
) -> pd.DataFrame:
    output = df.copy()
    denominator_values = numeric_series(output, denominator).replace(0, pd.NA)

    output[new_column] = (
        numeric_series(output, numerator) / denominator_values
    ).fillna(0.0).round(2)

    return output


def download_csv(
    df: pd.DataFrame,
    filename: str,
    key: str,
) -> None:
    st.download_button(
        label="Download CSV",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=filename,
        mime="text/csv",
        key=key,
    )


def bar_chart(
    df: pd.DataFrame,
    category_column: str,
    value_column: str,
    title: str,
) -> None:
    st.subheader(title)

    if df.empty:
        st.info("No data is available for the selected filters.")
        return

    chart_df = (
        df[[category_column, value_column]]
        .dropna(subset=[category_column])
        .set_index(category_column)
    )

    st.bar_chart(chart_df, use_container_width=True)


def line_chart(
    df: pd.DataFrame,
    date_column: str,
    metric_columns: list[str],
    title: str,
) -> None:
    st.subheader(title)

    if df.empty:
        st.info("No data is available for the selected filters.")
        return

    chart_df = (
        df[[date_column] + metric_columns]
        .dropna(subset=[date_column])
        .set_index(date_column)
        .sort_index()
    )

    st.line_chart(chart_df, use_container_width=True)


def display_dataframe(
    df: pd.DataFrame,
    column_config: dict | None = None,
    height: int = 460,
) -> None:
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        height=height,
        column_config=column_config,
    )


# =============================================================================
# LOAD AND VALIDATE CURRENT GOLD REPORTS
# =============================================================================

try:
    with st.spinner("Loading validated Gold reports from Snowflake..."):
        inbound = run_query(f"SELECT * FROM {VIEWS['inbound']}")
        outbound = run_query(f"SELECT * FROM {VIEWS['outbound']}")
        closer = run_query(f"SELECT * FROM {VIEWS['closer']}")
        objections = run_query(f"SELECT * FROM {VIEWS['objections']}")

        require_columns(
            inbound,
            REQUIRED_COLUMNS["INBOUND_SETTER_REPORT"],
            "INBOUND_SETTER_REPORT",
        )
        require_columns(
            outbound,
            REQUIRED_COLUMNS["OUTBOUND_SETTER_REPORT"],
            "OUTBOUND_SETTER_REPORT",
        )
        require_columns(
            closer,
            REQUIRED_COLUMNS["CLOSER_REPORT"],
            "CLOSER_REPORT",
        )
        require_columns(
            objections,
            REQUIRED_COLUMNS["OBJECTIONS_FACED_REPORT"],
            "OBJECTIONS_FACED_REPORT",
        )

        inbound = prepare_date(inbound, "TRIAGE_DATE")
        outbound = prepare_date(outbound, "OUTBOUND_DATE")
        closer = prepare_date(closer, "STRATEGY_DATE")
        objections = prepare_date(objections, "ACTIVITY_DATE")

except Exception as exc:
    st.error("The app could not load the required Gold reporting structure.")
    st.code(str(exc))
    st.info(
        "Confirm that the Streamlit owner role has USAGE on "
        "SALES_ANALYTICS_DB and GOLD, plus SELECT on all four report views."
    )
    st.stop()


# =============================================================================
# OPTIONAL PIPELINE FRESHNESS
# =============================================================================

@st.cache_data(ttl=300, show_spinner=False)
def load_pipeline_freshness() -> pd.DataFrame:
    return run_query(
        f"""
        SELECT
            MAX(INSERT_DATE) AS LATEST_INGESTION_DATE
        FROM {DATABASE}.{BRONZE_SCHEMA}.LEAD_ACTIVITIES_RAW
        """
    )


try:
    freshness = load_pipeline_freshness()
    latest_ingestion = freshness.loc[0, "LATEST_INGESTION_DATE"]
except Exception:
    latest_ingestion = None

latest_business_activity = max(
    date_value
    for date_value in [
        inbound["TRIAGE_DATE"].max(),
        outbound["OUTBOUND_DATE"].max(),
        closer["STRATEGY_DATE"].max(),
        objections["ACTIVITY_DATE"].max(),
    ]
    if pd.notna(date_value)
)


# =============================================================================
# HEADER AND SIDEBAR
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
        load_pipeline_freshness.clear()
        get_session.clear()
        st.rerun()


# =============================================================================
# GLOBAL DATE FILTER
# =============================================================================

all_dates = []

for frame, column in [
    (inbound, "TRIAGE_DATE"),
    (outbound, "OUTBOUND_DATE"),
    (closer, "STRATEGY_DATE"),
    (objections, "ACTIVITY_DATE"),
]:
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

    st.caption(
        "The date filter uses CRM business dates, not pipeline ingestion dates."
    )


inbound_filtered = filter_date(
    inbound,
    "TRIAGE_DATE",
    start_date,
    end_date,
)

outbound_filtered = filter_date(
    outbound,
    "OUTBOUND_DATE",
    start_date,
    end_date,
)

closer_filtered = filter_date(
    closer,
    "STRATEGY_DATE",
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

    freshness_columns = st.columns(2)

    if latest_ingestion is not None and pd.notna(latest_ingestion):
        freshness_columns[0].metric(
            "Latest pipeline ingestion",
            pd.to_datetime(latest_ingestion).strftime("%b %d, %Y %I:%M %p"),
        )
    else:
        freshness_columns[0].metric(
            "Latest pipeline ingestion",
            "Unavailable",
        )

    freshness_columns[1].metric(
        "Latest business activity",
        pd.to_datetime(latest_business_activity).strftime("%b %d, %Y"),
    )

    st.subheader("Business performance")

    metric_columns = st.columns(6)

    metric_columns[0].metric(
        "Inbound calls",
        whole(total(inbound_filtered, "INBOUND_BOOKED")),
    )
    metric_columns[1].metric(
        "Outbound dials",
        whole(total(outbound_filtered, "OUTBOUND_DIALS")),
    )
    metric_columns[2].metric(
        "Inbound sales",
        whole(total(inbound_filtered, "TOTAL_SALES")),
    )
    metric_columns[3].metric(
        "Outbound sales",
        whole(total(outbound_filtered, "TOTAL_SALES")),
    )
    metric_columns[4].metric(
        "Contract value",
        money(total(closer_filtered, "TOTAL_CONTRACT_VALUE")),
    )
    metric_columns[5].metric(
        "Cash collected",
        money(total(closer_filtered, "TOTAL_CASH_COLLECTED")),
    )

    st.subheader("Conversion performance")

    conversion_columns = st.columns(6)

    conversion_columns[0].metric(
        "Inbound show rate",
        pct(weighted_rate(
            inbound_filtered,
            "INBOUND_TAKEN",
            "INBOUND_BOOKED",
        )),
    )
    conversion_columns[1].metric(
        "Inbound triage-to-set",
        pct(weighted_rate(
            inbound_filtered,
            "STRATEGY_CALL_BOOKED",
            "INBOUND_TAKEN",
        )),
    )
    conversion_columns[2].metric(
        "Outbound connect rate",
        pct(weighted_rate(
            outbound_filtered,
            "OUTBOUND_TAKEN",
            "OUTBOUND_DIALS",
        )),
    )
    conversion_columns[3].metric(
        "Outbound set rate",
        pct(weighted_rate(
            outbound_filtered,
            "STRATEGY_CALL_BOOKED",
            "OUTBOUND_TAKEN",
        )),
    )
    conversion_columns[4].metric(
        "Closer offer rate",
        pct(weighted_rate(
            closer_filtered,
            "OFFERS_PRESENTED",
            "STRATEGY_CALL_TAKEN",
        )),
    )
    conversion_columns[5].metric(
        "Closer sale rate",
        pct(weighted_rate(
            closer_filtered,
            "TOTAL_SALES",
            "STRATEGY_CALL_TAKEN",
        )),
    )

    inbound_daily = (
        inbound_filtered.groupby("TRIAGE_DATE", as_index=False)
        .agg(
            INBOUND_BOOKED=("INBOUND_BOOKED", "sum"),
            INBOUND_TAKEN=("INBOUND_TAKEN", "sum"),
            STRATEGY_CALL_BOOKED=("STRATEGY_CALL_BOOKED", "sum"),
            TOTAL_SALES=("TOTAL_SALES", "sum"),
        )
    )

    outbound_daily = (
        outbound_filtered.groupby("OUTBOUND_DATE", as_index=False)
        .agg(
            OUTBOUND_DIALS=("OUTBOUND_DIALS", "sum"),
            OUTBOUND_TAKEN=("OUTBOUND_TAKEN", "sum"),
            STRATEGY_CALL_BOOKED=("STRATEGY_CALL_BOOKED", "sum"),
            TOTAL_SALES=("TOTAL_SALES", "sum"),
        )
    )

    left_column, right_column = st.columns(2)

    with left_column:
        line_chart(
            inbound_daily,
            "TRIAGE_DATE",
            [
                "INBOUND_BOOKED",
                "INBOUND_TAKEN",
                "STRATEGY_CALL_BOOKED",
                "TOTAL_SALES",
            ],
            "Inbound performance trend",
        )

    with right_column:
        line_chart(
            outbound_daily,
            "OUTBOUND_DATE",
            [
                "OUTBOUND_DIALS",
                "OUTBOUND_TAKEN",
                "STRATEGY_CALL_BOOKED",
                "TOTAL_SALES",
            ],
            "Outbound performance trend",
        )


# =============================================================================
# INBOUND SETTER
# =============================================================================

elif page == "Inbound Setter":
    st.header("Inbound Setter Performance")

    setter_options = sorted(
        inbound_filtered["SETTER"]
        .fillna("UNMAPPED SETTER")
        .astype(str)
        .unique()
        .tolist()
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

    metric_row_1 = st.columns(7)

    metric_row_1[0].metric(
        "Inbound booked",
        whole(total(df, "INBOUND_BOOKED")),
    )
    metric_row_1[1].metric(
        "Inbound taken",
        whole(total(df, "INBOUND_TAKEN")),
    )
    metric_row_1[2].metric(
        "Show rate",
        pct(weighted_rate(df, "INBOUND_TAKEN", "INBOUND_BOOKED")),
    )
    metric_row_1[3].metric(
        "Strategy booked",
        whole(total(df, "STRATEGY_CALL_BOOKED")),
    )
    metric_row_1[4].metric(
        "Triage set rate",
        pct(weighted_rate(
            df,
            "STRATEGY_CALL_BOOKED",
            "INBOUND_TAKEN",
        )),
    )
    metric_row_1[5].metric(
        "Offers",
        whole(total(df, "OFFERS_PRESENTED")),
    )
    metric_row_1[6].metric(
        "Sales",
        whole(total(df, "TOTAL_SALES")),
    )

    metric_row_2 = st.columns(4)

    metric_row_2[0].metric(
        "Strategy calls taken",
        whole(total(df, "STRATEGY_CALL_TAKEN")),
    )
    metric_row_2[1].metric(
        "Offer rate",
        pct(weighted_rate(
            df,
            "OFFERS_PRESENTED",
            "STRATEGY_CALL_TAKEN",
        )),
    )
    metric_row_2[2].metric(
        "Sale rate",
        pct(weighted_rate(
            df,
            "TOTAL_SALES",
            "STRATEGY_CALL_TAKEN",
        )),
    )

    inbound_aov_numerator = (
        numeric_series(df, "AVERAGE_ORDER_VALUE")
        * numeric_series(df, "TOTAL_SALES")
    ).sum()
    inbound_sales_total = total(df, "TOTAL_SALES")

    metric_row_2[3].metric(
        "Average order value",
        money(
            0
            if inbound_sales_total == 0
            else inbound_aov_numerator / inbound_sales_total
        ),
    )

    summary_tab, trend_tab, detail_tab = st.tabs(
        ["Setter Summary", "Daily Trend", "Detailed Report"]
    )

    with summary_tab:
        summary = (
            df.groupby(
                ["SETTER", "SETTER_EMAIL"],
                as_index=False,
                dropna=False,
            )
            .agg(
                INBOUND_BOOKED=("INBOUND_BOOKED", "sum"),
                INBOUND_TAKEN=("INBOUND_TAKEN", "sum"),
                STRATEGY_CALL_BOOKED=("STRATEGY_CALL_BOOKED", "sum"),
                STRATEGY_CALL_TAKEN=("STRATEGY_CALL_TAKEN", "sum"),
                OFFERS_PRESENTED=("OFFERS_PRESENTED", "sum"),
                TOTAL_SALES=("TOTAL_SALES", "sum"),
                WEIGHTED_ORDER_VALUE=(
                    "AVERAGE_ORDER_VALUE",
                    lambda values: 0.0,
                ),
            )
        ).drop(columns=["WEIGHTED_ORDER_VALUE"])

        summary = add_rate(
            summary,
            "SHOW_RATE",
            "INBOUND_TAKEN",
            "INBOUND_BOOKED",
        )
        summary = add_rate(
            summary,
            "TRIAGE_SET_RATE",
            "STRATEGY_CALL_BOOKED",
            "INBOUND_TAKEN",
        )
        summary = add_rate(
            summary,
            "OFFER_RATE",
            "OFFERS_PRESENTED",
            "STRATEGY_CALL_TAKEN",
        )
        summary = add_rate(
            summary,
            "SALE_RATE",
            "TOTAL_SALES",
            "STRATEGY_CALL_TAKEN",
        )

        aov_by_setter = (
            df.assign(
                ORDER_VALUE_WEIGHTED=(
                    numeric_series(df, "AVERAGE_ORDER_VALUE")
                    * numeric_series(df, "TOTAL_SALES")
                )
            )
            .groupby(["SETTER", "SETTER_EMAIL"], dropna=False)
            .agg(
                ORDER_VALUE_WEIGHTED=("ORDER_VALUE_WEIGHTED", "sum"),
                SALES_FOR_AOV=("TOTAL_SALES", "sum"),
            )
            .reset_index()
        )

        aov_by_setter["AVERAGE_ORDER_VALUE"] = (
            aov_by_setter["ORDER_VALUE_WEIGHTED"]
            / aov_by_setter["SALES_FOR_AOV"].replace(0, pd.NA)
        ).fillna(0.0).round(2)

        summary = summary.merge(
            aov_by_setter[
                ["SETTER", "SETTER_EMAIL", "AVERAGE_ORDER_VALUE"]
            ],
            on=["SETTER", "SETTER_EMAIL"],
            how="left",
        )

        chart_left, chart_right = st.columns(2)

        with chart_left:
            bar_chart(
                summary.sort_values(
                    "INBOUND_BOOKED",
                    ascending=False,
                ).head(15),
                "SETTER",
                "INBOUND_BOOKED",
                "Top setters by inbound calls",
            )

        with chart_right:
            bar_chart(
                summary.sort_values(
                    "TOTAL_SALES",
                    ascending=False,
                ).head(15),
                "SETTER",
                "TOTAL_SALES",
                "Top setters by sales",
            )

        display_dataframe(
            summary.sort_values(
                ["TOTAL_SALES", "INBOUND_BOOKED"],
                ascending=False,
            ),
            column_config={
                "AVERAGE_ORDER_VALUE": st.column_config.NumberColumn(
                    "AVERAGE_ORDER_VALUE",
                    format="$%.2f",
                ),
                "SHOW_RATE": st.column_config.NumberColumn(
                    "SHOW_RATE",
                    format="%.2f%%",
                ),
                "TRIAGE_SET_RATE": st.column_config.NumberColumn(
                    "TRIAGE_SET_RATE",
                    format="%.2f%%",
                ),
                "OFFER_RATE": st.column_config.NumberColumn(
                    "OFFER_RATE",
                    format="%.2f%%",
                ),
                "SALE_RATE": st.column_config.NumberColumn(
                    "SALE_RATE",
                    format="%.2f%%",
                ),
            },
        )

        download_csv(
            summary,
            "inbound_setter_summary.csv",
            "download_inbound_summary",
        )

    with trend_tab:
        daily = (
            df.groupby("TRIAGE_DATE", as_index=False)
            .agg(
                INBOUND_BOOKED=("INBOUND_BOOKED", "sum"),
                INBOUND_TAKEN=("INBOUND_TAKEN", "sum"),
                STRATEGY_CALL_BOOKED=("STRATEGY_CALL_BOOKED", "sum"),
                STRATEGY_CALL_TAKEN=("STRATEGY_CALL_TAKEN", "sum"),
                OFFERS_PRESENTED=("OFFERS_PRESENTED", "sum"),
                TOTAL_SALES=("TOTAL_SALES", "sum"),
            )
        )

        daily = add_rate(
            daily,
            "SHOW_RATE",
            "INBOUND_TAKEN",
            "INBOUND_BOOKED",
        )
        daily = add_rate(
            daily,
            "TRIAGE_SET_RATE",
            "STRATEGY_CALL_BOOKED",
            "INBOUND_TAKEN",
        )
        daily = add_rate(
            daily,
            "OFFER_RATE",
            "OFFERS_PRESENTED",
            "STRATEGY_CALL_TAKEN",
        )
        daily = add_rate(
            daily,
            "SALE_RATE",
            "TOTAL_SALES",
            "STRATEGY_CALL_TAKEN",
        )

        line_chart(
            daily,
            "TRIAGE_DATE",
            [
                "INBOUND_BOOKED",
                "INBOUND_TAKEN",
                "STRATEGY_CALL_BOOKED",
                "TOTAL_SALES",
            ],
            "Daily inbound funnel",
        )

        display_dataframe(daily.sort_values("TRIAGE_DATE", ascending=False))

    with detail_tab:
        inbound_detail_columns = [
            "TRIAGE_DATE",
            "SETTER",
            "SETTER_EMAIL",
            "INBOUND_BOOKED",
            "INBOUND_TAKEN",
            "SHOW_RATE",
            "TRIAGE_SET_RATE",
            "STRATEGY_CALL_BOOKED",
            "STRATEGY_CALL_TAKEN",
            "OFFERS_PRESENTED",
            "OFFER_RATE",
            "TOTAL_SALES",
            "SALE_RATE",
            "AVERAGE_ORDER_VALUE",
        ]

        detail = df[inbound_detail_columns].sort_values(
            ["TRIAGE_DATE", "SETTER"],
            ascending=[False, True],
        )

        display_dataframe(
            detail,
            column_config={
                "TRIAGE_DATE": st.column_config.DateColumn(
                    "TRIAGE_DATE",
                    format="YYYY-MM-DD",
                ),
                "SHOW_RATE": st.column_config.NumberColumn(
                    "SHOW_RATE",
                    format="%.2f%%",
                ),
                "TRIAGE_SET_RATE": st.column_config.NumberColumn(
                    "TRIAGE_SET_RATE",
                    format="%.2f%%",
                ),
                "OFFER_RATE": st.column_config.NumberColumn(
                    "OFFER_RATE",
                    format="%.2f%%",
                ),
                "SALE_RATE": st.column_config.NumberColumn(
                    "SALE_RATE",
                    format="%.2f%%",
                ),
                "AVERAGE_ORDER_VALUE": st.column_config.NumberColumn(
                    "AVERAGE_ORDER_VALUE",
                    format="$%.2f",
                ),
            },
            height=600,
        )

        download_csv(
            detail,
            "inbound_setter_detail.csv",
            "download_inbound_detail",
        )


# =============================================================================
# OUTBOUND SETTER
# =============================================================================

elif page == "Outbound Setter":
    st.header("Outbound Setter Performance")

    setter_options = sorted(
        outbound_filtered["SETTER"]
        .fillna("UNMAPPED SETTER")
        .astype(str)
        .unique()
        .tolist()
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

    metric_row_1 = st.columns(6)

    metric_row_1[0].metric(
        "Outbound dials",
        whole(total(df, "OUTBOUND_DIALS")),
    )
    metric_row_1[1].metric(
        "Leads touched",
        whole(total(df, "TOTAL_LEADS_TOUCHED")),
    )
    metric_row_1[2].metric(
        "Connections",
        whole(total(df, "OUTBOUND_TAKEN")),
    )
    metric_row_1[3].metric(
        "Connect rate",
        pct(weighted_rate(df, "OUTBOUND_TAKEN", "OUTBOUND_DIALS")),
    )
    metric_row_1[4].metric(
        "Strategy calls booked",
        whole(total(df, "STRATEGY_CALL_BOOKED")),
    )
    metric_row_1[5].metric(
        "Set rate",
        pct(weighted_rate(
            df,
            "STRATEGY_CALL_BOOKED",
            "OUTBOUND_TAKEN",
        )),
    )

    metric_row_2 = st.columns(7)

    metric_row_2[0].metric(
        "Strategy calls taken",
        whole(total(df, "STRATEGY_CALL_TAKEN")),
    )
    metric_row_2[1].metric(
        "Offers",
        whole(total(df, "OFFERS_PRESENTED")),
    )
    metric_row_2[2].metric(
        "Offer rate",
        pct(weighted_rate(
            df,
            "OFFERS_PRESENTED",
            "STRATEGY_CALL_TAKEN",
        )),
    )
    metric_row_2[3].metric(
        "Sales",
        whole(total(df, "TOTAL_SALES")),
    )
    metric_row_2[4].metric(
        "Sale rate",
        pct(weighted_rate(
            df,
            "TOTAL_SALES",
            "STRATEGY_CALL_TAKEN",
        )),
    )
    metric_row_2[5].metric(
        "Contract value",
        money(total(df, "TOTAL_CONTRACT_VALUE")),
    )
    metric_row_2[6].metric(
        "Cash collected",
        money(total(df, "TOTAL_CASH_COLLECTED")),
    )

    summary_tab, funnel_tab, trend_tab, detail_tab = st.tabs(
        [
            "Setter Summary",
            "Conversion Funnel",
            "Daily Trend",
            "Detailed Report",
        ]
    )

    with summary_tab:
        summary = (
            df.groupby(
                ["SETTER", "SETTER_EMAIL"],
                as_index=False,
                dropna=False,
            )
            .agg(
                OUTBOUND_DIALS=("OUTBOUND_DIALS", "sum"),
                TOTAL_LEADS_TOUCHED=("TOTAL_LEADS_TOUCHED", "sum"),
                OUTBOUND_TAKEN=("OUTBOUND_TAKEN", "sum"),
                STRATEGY_CALL_BOOKED=("STRATEGY_CALL_BOOKED", "sum"),
                STRATEGY_CALL_TAKEN=("STRATEGY_CALL_TAKEN", "sum"),
                OFFERS_PRESENTED=("OFFERS_PRESENTED", "sum"),
                TOTAL_SALES=("TOTAL_SALES", "sum"),
                TOTAL_CONTRACT_VALUE=("TOTAL_CONTRACT_VALUE", "sum"),
                TOTAL_CASH_COLLECTED=("TOTAL_CASH_COLLECTED", "sum"),
            )
        )

        summary = add_rate(
            summary,
            "CONNECT_RATE",
            "OUTBOUND_TAKEN",
            "OUTBOUND_DIALS",
        )
        summary = add_rate(
            summary,
            "SET_RATE",
            "STRATEGY_CALL_BOOKED",
            "OUTBOUND_TAKEN",
        )
        summary = add_rate(
            summary,
            "OFFER_RATE",
            "OFFERS_PRESENTED",
            "STRATEGY_CALL_TAKEN",
        )
        summary = add_rate(
            summary,
            "SALE_RATE",
            "TOTAL_SALES",
            "STRATEGY_CALL_TAKEN",
        )
        summary = add_average(
            summary,
            "AVERAGE_ORDER_VALUE",
            "TOTAL_CONTRACT_VALUE",
            "TOTAL_SALES",
        )

        chart_left, chart_right = st.columns(2)

        with chart_left:
            bar_chart(
                summary.sort_values(
                    "OUTBOUND_DIALS",
                    ascending=False,
                ).head(15),
                "SETTER",
                "OUTBOUND_DIALS",
                "Top setters by outbound dials",
            )

        with chart_right:
            bar_chart(
                summary.sort_values(
                    "TOTAL_SALES",
                    ascending=False,
                ).head(15),
                "SETTER",
                "TOTAL_SALES",
                "Top setters by sales",
            )

        display_dataframe(
            summary.sort_values(
                ["TOTAL_SALES", "TOTAL_CONTRACT_VALUE"],
                ascending=False,
            ),
            column_config={
                "TOTAL_CONTRACT_VALUE": st.column_config.NumberColumn(
                    "TOTAL_CONTRACT_VALUE",
                    format="$%.2f",
                ),
                "TOTAL_CASH_COLLECTED": st.column_config.NumberColumn(
                    "TOTAL_CASH_COLLECTED",
                    format="$%.2f",
                ),
                "AVERAGE_ORDER_VALUE": st.column_config.NumberColumn(
                    "AVERAGE_ORDER_VALUE",
                    format="$%.2f",
                ),
            },
        )

        download_csv(
            summary,
            "outbound_setter_summary.csv",
            "download_outbound_summary",
        )

    with funnel_tab:
        funnel = pd.DataFrame(
            {
                "STAGE": [
                    "Outbound Dials",
                    "Connections",
                    "Strategy Calls Booked",
                    "Strategy Calls Taken",
                    "Offers",
                    "Sales",
                ],
                "COUNT": [
                    total(df, "OUTBOUND_DIALS"),
                    total(df, "OUTBOUND_TAKEN"),
                    total(df, "STRATEGY_CALL_BOOKED"),
                    total(df, "STRATEGY_CALL_TAKEN"),
                    total(df, "OFFERS_PRESENTED"),
                    total(df, "TOTAL_SALES"),
                ],
            }
        )

        initial_count = funnel["COUNT"].iloc[0] if not funnel.empty else 0

        funnel["PERCENT_OF_DIALS"] = funnel["COUNT"].apply(
            lambda value: safe_divide(value, initial_count)
        )

        st.bar_chart(
            funnel.set_index("STAGE")[["COUNT"]],
            use_container_width=True,
        )

        display_dataframe(funnel, height=320)

    with trend_tab:
        daily = (
            df.groupby("OUTBOUND_DATE", as_index=False)
            .agg(
                OUTBOUND_DIALS=("OUTBOUND_DIALS", "sum"),
                OUTBOUND_TAKEN=("OUTBOUND_TAKEN", "sum"),
                STRATEGY_CALL_BOOKED=("STRATEGY_CALL_BOOKED", "sum"),
                STRATEGY_CALL_TAKEN=("STRATEGY_CALL_TAKEN", "sum"),
                OFFERS_PRESENTED=("OFFERS_PRESENTED", "sum"),
                TOTAL_SALES=("TOTAL_SALES", "sum"),
                TOTAL_CONTRACT_VALUE=("TOTAL_CONTRACT_VALUE", "sum"),
                TOTAL_CASH_COLLECTED=("TOTAL_CASH_COLLECTED", "sum"),
            )
        )

        line_chart(
            daily,
            "OUTBOUND_DATE",
            [
                "OUTBOUND_DIALS",
                "OUTBOUND_TAKEN",
                "STRATEGY_CALL_BOOKED",
                "TOTAL_SALES",
            ],
            "Daily outbound funnel",
        )

        display_dataframe(daily.sort_values("OUTBOUND_DATE", ascending=False))

    with detail_tab:
        outbound_detail_columns = [
            "OUTBOUND_DATE",
            "REPORTING_WEEK",
            "SETTER",
            "SETTER_EMAIL",
            "OUTBOUND_DIALS",
            "TOTAL_LEADS_TOUCHED",
            "OUTBOUND_TAKEN",
            "CONNECT_RATE",
            "STRATEGY_CALL_BOOKED",
            "SET_RATE",
            "STRATEGY_CALL_TAKEN",
            "OFFERS_PRESENTED",
            "OFFER_RATE",
            "TOTAL_SALES",
            "SALE_RATE",
            "AVERAGE_ORDER_VALUE",
            "TOTAL_CONTRACT_VALUE",
            "TOTAL_CASH_COLLECTED",
        ]

        detail = df[outbound_detail_columns].sort_values(
            ["OUTBOUND_DATE", "SETTER"],
            ascending=[False, True],
        )

        display_dataframe(
            detail,
            column_config={
                "OUTBOUND_DATE": st.column_config.DateColumn(
                    "OUTBOUND_DATE",
                    format="YYYY-MM-DD",
                ),
                "AVERAGE_ORDER_VALUE": st.column_config.NumberColumn(
                    "AVERAGE_ORDER_VALUE",
                    format="$%.2f",
                ),
                "TOTAL_CONTRACT_VALUE": st.column_config.NumberColumn(
                    "TOTAL_CONTRACT_VALUE",
                    format="$%.2f",
                ),
                "TOTAL_CASH_COLLECTED": st.column_config.NumberColumn(
                    "TOTAL_CASH_COLLECTED",
                    format="$%.2f",
                ),
            },
            height=600,
        )

        download_csv(
            detail,
            "outbound_setter_detail.csv",
            "download_outbound_detail",
        )


# =============================================================================
# CLOSER PERFORMANCE
# =============================================================================

elif page == "Closer Performance":
    st.header("Closer Performance")

    closer_options = sorted(
        closer_filtered["CLOSER"]
        .fillna("UNMAPPED CLOSER")
        .astype(str)
        .unique()
        .tolist()
    )

    selected_closers = st.multiselect(
        "Closer",
        closer_options,
        default=closer_options,
    )

    df = filter_values(
        closer_filtered,
        "CLOSER",
        selected_closers,
    )

    metric_row_1 = st.columns(6)

    metric_row_1[0].metric(
        "Strategy calls",
        whole(total(df, "STRATEGY_CALLS")),
    )
    metric_row_1[1].metric(
        "Calls taken",
        whole(total(df, "STRATEGY_CALL_TAKEN")),
    )
    metric_row_1[2].metric(
        "Show rate",
        pct(weighted_rate(
            df,
            "STRATEGY_CALL_TAKEN",
            "STRATEGY_CALLS",
        )),
    )
    metric_row_1[3].metric(
        "Offers",
        whole(total(df, "OFFERS_PRESENTED")),
    )
    metric_row_1[4].metric(
        "Offer rate",
        pct(weighted_rate(
            df,
            "OFFERS_PRESENTED",
            "STRATEGY_CALL_TAKEN",
        )),
    )
    metric_row_1[5].metric(
        "Sales",
        whole(total(df, "TOTAL_SALES")),
    )

    metric_row_2 = st.columns(6)

    metric_row_2[0].metric(
        "Sale rate",
        pct(weighted_rate(
            df,
            "TOTAL_SALES",
            "STRATEGY_CALL_TAKEN",
        )),
    )
    metric_row_2[1].metric(
        "Offer-to-sale rate",
        pct(weighted_rate(
            df,
            "TOTAL_SALES",
            "OFFERS_PRESENTED",
        )),
    )
    metric_row_2[2].metric(
        "Contract value",
        money(total(df, "TOTAL_CONTRACT_VALUE")),
    )
    metric_row_2[3].metric(
        "Cash collected",
        money(total(df, "TOTAL_CASH_COLLECTED")),
    )
    metric_row_2[4].metric(
        "Average contract",
        money(
            0
            if total(df, "TOTAL_SALES") == 0
            else total(df, "TOTAL_CONTRACT_VALUE")
            / total(df, "TOTAL_SALES")
        ),
    )
    metric_row_2[5].metric(
        "Average cash",
        money(
            0
            if total(df, "TOTAL_SALES") == 0
            else total(df, "TOTAL_CASH_COLLECTED")
            / total(df, "TOTAL_SALES")
        ),
    )

    summary_tab, weekly_tab, detail_tab = st.tabs(
        ["Closer Summary", "Weekly Trend", "Detailed Report"]
    )

    with summary_tab:
        summary = (
            df.groupby(
                ["CLOSER", "CLOSER_EMAIL"],
                as_index=False,
                dropna=False,
            )
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
            "OFFER_RATE",
            "OFFERS_PRESENTED",
            "STRATEGY_CALL_TAKEN",
        )
        summary = add_rate(
            summary,
            "SALE_RATE",
            "TOTAL_SALES",
            "STRATEGY_CALL_TAKEN",
        )
        summary = add_rate(
            summary,
            "OFFER_TO_SALE_RATE",
            "TOTAL_SALES",
            "OFFERS_PRESENTED",
        )
        summary = add_average(
            summary,
            "AVERAGE_CONTRACT_VALUE",
            "TOTAL_CONTRACT_VALUE",
            "TOTAL_SALES",
        )
        summary = add_average(
            summary,
            "AVERAGE_CASH_COLLECTED",
            "TOTAL_CASH_COLLECTED",
            "TOTAL_SALES",
        )

        chart_left, chart_right = st.columns(2)

        with chart_left:
            bar_chart(
                summary.sort_values(
                    "TOTAL_SALES",
                    ascending=False,
                ).head(15),
                "CLOSER",
                "TOTAL_SALES",
                "Sales by closer",
            )

        with chart_right:
            bar_chart(
                summary.sort_values(
                    "TOTAL_CASH_COLLECTED",
                    ascending=False,
                ).head(15),
                "CLOSER",
                "TOTAL_CASH_COLLECTED",
                "Cash collected by closer",
            )

        display_dataframe(
            summary.sort_values(
                ["TOTAL_SALES", "TOTAL_CASH_COLLECTED"],
                ascending=False,
            ),
            column_config={
                "TOTAL_CONTRACT_VALUE": st.column_config.NumberColumn(
                    "TOTAL_CONTRACT_VALUE",
                    format="$%.2f",
                ),
                "TOTAL_CASH_COLLECTED": st.column_config.NumberColumn(
                    "TOTAL_CASH_COLLECTED",
                    format="$%.2f",
                ),
                "AVERAGE_CONTRACT_VALUE": st.column_config.NumberColumn(
                    "AVERAGE_CONTRACT_VALUE",
                    format="$%.2f",
                ),
                "AVERAGE_CASH_COLLECTED": st.column_config.NumberColumn(
                    "AVERAGE_CASH_COLLECTED",
                    format="$%.2f",
                ),
            },
        )

        download_csv(
            summary,
            "closer_summary.csv",
            "download_closer_summary",
        )

    with weekly_tab:
        weekly = (
            df.groupby("REPORTING_WEEK", as_index=False)
            .agg(
                STRATEGY_CALLS=("STRATEGY_CALLS", "sum"),
                STRATEGY_CALL_TAKEN=("STRATEGY_CALL_TAKEN", "sum"),
                OFFERS_PRESENTED=("OFFERS_PRESENTED", "sum"),
                TOTAL_SALES=("TOTAL_SALES", "sum"),
                TOTAL_CONTRACT_VALUE=("TOTAL_CONTRACT_VALUE", "sum"),
                TOTAL_CASH_COLLECTED=("TOTAL_CASH_COLLECTED", "sum"),
            )
            .sort_values("REPORTING_WEEK")
        )

        st.line_chart(
            weekly.set_index("REPORTING_WEEK")[
                [
                    "STRATEGY_CALLS",
                    "STRATEGY_CALL_TAKEN",
                    "OFFERS_PRESENTED",
                    "TOTAL_SALES",
                ]
            ],
            use_container_width=True,
        )

        display_dataframe(weekly.sort_values("REPORTING_WEEK", ascending=False))

    with detail_tab:
        closer_detail_columns = [
            "STRATEGY_DATE",
            "REPORTING_WEEK",
            "CLOSER",
            "CLOSER_EMAIL",
            "STRATEGY_CALLS",
            "STRATEGY_CALL_TAKEN",
            "SHOW_RATE",
            "OFFERS_PRESENTED",
            "OFFER_RATE",
            "TOTAL_SALES",
            "SALE_RATE",
            "OFFER_TO_SALE_RATE",
            "TOTAL_CONTRACT_VALUE",
            "TOTAL_CASH_COLLECTED",
            "AVERAGE_CONTRACT_VALUE",
            "AVERAGE_CASH_COLLECTED",
        ]

        detail = df[closer_detail_columns].sort_values(
            ["STRATEGY_DATE", "CLOSER"],
            ascending=[False, True],
        )

        display_dataframe(
            detail,
            column_config={
                "STRATEGY_DATE": st.column_config.DateColumn(
                    "STRATEGY_DATE",
                    format="YYYY-MM-DD",
                ),
                "TOTAL_CONTRACT_VALUE": st.column_config.NumberColumn(
                    "TOTAL_CONTRACT_VALUE",
                    format="$%.2f",
                ),
                "TOTAL_CASH_COLLECTED": st.column_config.NumberColumn(
                    "TOTAL_CASH_COLLECTED",
                    format="$%.2f",
                ),
                "AVERAGE_CONTRACT_VALUE": st.column_config.NumberColumn(
                    "AVERAGE_CONTRACT_VALUE",
                    format="$%.2f",
                ),
                "AVERAGE_CASH_COLLECTED": st.column_config.NumberColumn(
                    "AVERAGE_CASH_COLLECTED",
                    format="$%.2f",
                ),
            },
            height=600,
        )

        download_csv(
            detail,
            "closer_detail.csv",
            "download_closer_detail",
        )


# =============================================================================
# OBJECTIONS
# =============================================================================

elif page == "Objections":
    st.header("Objections Faced")

    closer_options = sorted(
        objections_filtered["CLOSER_NAME"]
        .fillna("UNMAPPED CLOSER")
        .astype(str)
        .unique()
        .tolist()
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

    objection_columns = {
        "Money": ("MONEY_COUNT", "MONEY%"),
        "Fear": ("FEAR_COUNT", "FEAR%"),
        "Hung Up": ("HUNG_UP_COUNT", "HUNG UP%"),
        "Logistical": ("LOGISTICAL_COUNT", "LOGISTICAL%"),
        "No Objection": ("NO_OBJ_COUNT", "NO OBJ%"),
        "Other Coaches": ("OTHER_COACHES_COUNT", "OTHER COACHES%"),
        "Partner": ("PARTNER_COUNT", "PARTNER%"),
        "Think About It": ("THINK_ABT_IT_COUNT", "THINK ABT IT%"),
        "Time": ("TIME_COUNT", "TIME%"),
        "Trust": ("TRUST_COUNT", "TRUST%"),
        "Value": ("VALUE_COUNT", "VALUE%"),
        "Not Looking": (
            "NOT_LOOKING_COUNT",
            "WSN'T LKNG FR WHT WE OFFRD%",
        ),
    }

    objection_totals = pd.DataFrame(
        {
            "OBJECTION": list(objection_columns.keys()),
            "COUNT": [
                total(df, count_column)
                for count_column, _ in objection_columns.values()
            ],
        }
    ).sort_values("COUNT", ascending=False)

    total_calls = total(df, "TOTAL_CALLS")
    objection_totals["PERCENT_OF_CALLS"] = objection_totals["COUNT"].apply(
        lambda value: safe_divide(value, total_calls)
    )

    metric_columns = st.columns(4)

    metric_columns[0].metric(
        "Total calls",
        whole(total_calls),
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
    metric_columns[3].metric(
        "Top objection rate",
        (
            pct(objection_totals.iloc[0]["PERCENT_OF_CALLS"])
            if not objection_totals.empty
            else "0.00%"
        ),
    )

    distribution_tab, closer_tab, trend_tab, detail_tab = st.tabs(
        [
            "Distribution",
            "By Closer",
            "Daily Trend",
            "Detailed Report",
        ]
    )

    with distribution_tab:
        bar_chart(
            objection_totals,
            "OBJECTION",
            "COUNT",
            "Objection frequency",
        )

        display_dataframe(
            objection_totals,
            column_config={
                "PERCENT_OF_CALLS": st.column_config.NumberColumn(
                    "PERCENT_OF_CALLS",
                    format="%.2f%%",
                ),
            },
            height=430,
        )

    with closer_tab:
        count_columns = [
            count_column
            for count_column, _ in objection_columns.values()
        ]

        by_closer = (
            df.groupby(
                ["CLOSER_NAME", "CLOSER_EMAIL"],
                as_index=False,
                dropna=False,
            )
            .agg(
                TOTAL_CALLS=("TOTAL_CALLS", "sum"),
                **{
                    column: (column, "sum")
                    for column in count_columns
                },
            )
        )

        for label, (count_column, _) in objection_columns.items():
            by_closer[f"{label.upper()}_PCT"] = (
                100.0
                * numeric_series(by_closer, count_column)
                / numeric_series(by_closer, "TOTAL_CALLS").replace(0, pd.NA)
            ).fillna(0.0).round(2)

        display_dataframe(by_closer, height=600)

        download_csv(
            by_closer,
            "objections_by_closer.csv",
            "download_objections_by_closer",
        )

    with trend_tab:
        daily = (
            df.groupby("ACTIVITY_DATE", as_index=False)
            .agg(
                TOTAL_CALLS=("TOTAL_CALLS", "sum"),
                MONEY_COUNT=("MONEY_COUNT", "sum"),
                FEAR_COUNT=("FEAR_COUNT", "sum"),
                LOGISTICAL_COUNT=("LOGISTICAL_COUNT", "sum"),
                THINK_ABT_IT_COUNT=("THINK_ABT_IT_COUNT", "sum"),
                TIME_COUNT=("TIME_COUNT", "sum"),
                TRUST_COUNT=("TRUST_COUNT", "sum"),
            )
        )

        line_chart(
            daily,
            "ACTIVITY_DATE",
            [
                "MONEY_COUNT",
                "FEAR_COUNT",
                "LOGISTICAL_COUNT",
                "THINK_ABT_IT_COUNT",
                "TIME_COUNT",
                "TRUST_COUNT",
            ],
            "Daily objection trend",
        )

        display_dataframe(daily.sort_values("ACTIVITY_DATE", ascending=False))

    with detail_tab:
        objection_detail_columns = [
            "CLOSER_NAME",
            "CLOSER_EMAIL",
            "ACTIVITY_DATE",
            "TOTAL_CALLS",
            "MONEY_COUNT",
            "FEAR_COUNT",
            "HUNG_UP_COUNT",
            "LOGISTICAL_COUNT",
            "NO_OBJ_COUNT",
            "OTHER_COACHES_COUNT",
            "PARTNER_COUNT",
            "THINK_ABT_IT_COUNT",
            "TIME_COUNT",
            "TRUST_COUNT",
            "VALUE_COUNT",
            "NOT_LOOKING_COUNT",
            "MONEY%",
            "FEAR%",
            "HUNG UP%",
            "LOGISTICAL%",
            "NO OBJ%",
            "OTHER COACHES%",
            "PARTNER%",
            "THINK ABT IT%",
            "TIME%",
            "TRUST%",
            "VALUE%",
            "WSN'T LKNG FR WHT WE OFFRD%",
        ]

        detail = df[objection_detail_columns].sort_values(
            ["ACTIVITY_DATE", "CLOSER_NAME"],
            ascending=[False, True],
        )

        display_dataframe(
            detail,
            column_config={
                "ACTIVITY_DATE": st.column_config.DateColumn(
                    "ACTIVITY_DATE",
                    format="YYYY-MM-DD",
                ),
            },
            height=650,
        )

        download_csv(
            detail,
            "objections_detail.csv",
            "download_objections_detail",
        )


# =============================================================================
# DATA QUALITY
# =============================================================================

elif page == "Data Quality":
    st.header("Data Quality")

    checks = []

    inbound_booked = total(inbound, "INBOUND_BOOKED")
    inbound_taken = total(inbound, "INBOUND_TAKEN")
    inbound_strategy_booked = total(inbound, "STRATEGY_CALL_BOOKED")
    inbound_strategy_taken = total(inbound, "STRATEGY_CALL_TAKEN")
    inbound_offers = total(inbound, "OFFERS_PRESENTED")
    inbound_sales = total(inbound, "TOTAL_SALES")

    checks.extend(
        [
            {
                "CHECK": "Inbound calls taken do not exceed inbound calls booked",
                "STATUS": "PASS" if inbound_taken <= inbound_booked else "REVIEW",
                "DETAIL": f"{whole(inbound_taken)} taken / {whole(inbound_booked)} booked",
            },
            {
                "CHECK": "Inbound strategy calls booked do not exceed inbound calls taken",
                "STATUS": "PASS" if inbound_strategy_booked <= inbound_taken else "REVIEW",
                "DETAIL": f"{whole(inbound_strategy_booked)} booked / {whole(inbound_taken)} taken",
            },
            {
                "CHECK": "Inbound strategy calls taken do not exceed strategy calls booked",
                "STATUS": "PASS" if inbound_strategy_taken <= inbound_strategy_booked else "REVIEW",
                "DETAIL": f"{whole(inbound_strategy_taken)} taken / {whole(inbound_strategy_booked)} booked",
            },
            {
                "CHECK": "Inbound offers do not exceed strategy calls taken",
                "STATUS": "PASS" if inbound_offers <= inbound_strategy_taken else "REVIEW",
                "DETAIL": f"{whole(inbound_offers)} offers / {whole(inbound_strategy_taken)} calls taken",
            },
            {
                "CHECK": "Inbound sales do not exceed strategy calls taken",
                "STATUS": "PASS" if inbound_sales <= inbound_strategy_taken else "REVIEW",
                "DETAIL": f"{whole(inbound_sales)} sales / {whole(inbound_strategy_taken)} calls taken",
            },
        ]
    )

    outbound_dials = total(outbound, "OUTBOUND_DIALS")
    outbound_leads = total(outbound, "TOTAL_LEADS_TOUCHED")
    outbound_taken = total(outbound, "OUTBOUND_TAKEN")
    outbound_booked = total(outbound, "STRATEGY_CALL_BOOKED")
    outbound_strategy_taken = total(outbound, "STRATEGY_CALL_TAKEN")
    outbound_offers = total(outbound, "OFFERS_PRESENTED")
    outbound_sales = total(outbound, "TOTAL_SALES")

    checks.extend(
        [
            {
                "CHECK": "Outbound leads touched do not exceed outbound dials",
                "STATUS": "PASS" if outbound_leads <= outbound_dials else "REVIEW",
                "DETAIL": f"{whole(outbound_leads)} leads / {whole(outbound_dials)} dials",
            },
            {
                "CHECK": "Outbound connections do not exceed outbound dials",
                "STATUS": "PASS" if outbound_taken <= outbound_dials else "REVIEW",
                "DETAIL": f"{whole(outbound_taken)} connections / {whole(outbound_dials)} dials",
            },
            {
                "CHECK": "Outbound strategy calls booked do not exceed connections",
                "STATUS": "PASS" if outbound_booked <= outbound_taken else "REVIEW",
                "DETAIL": f"{whole(outbound_booked)} booked / {whole(outbound_taken)} connections",
            },
            {
                "CHECK": "Outbound strategy calls taken do not exceed calls booked",
                "STATUS": "PASS" if outbound_strategy_taken <= outbound_booked else "REVIEW",
                "DETAIL": f"{whole(outbound_strategy_taken)} taken / {whole(outbound_booked)} booked",
            },
            {
                "CHECK": "Outbound offers do not exceed strategy calls taken",
                "STATUS": "PASS" if outbound_offers <= outbound_strategy_taken else "REVIEW",
                "DETAIL": f"{whole(outbound_offers)} offers / {whole(outbound_strategy_taken)} calls taken",
            },
            {
                "CHECK": "Outbound sales do not exceed strategy calls taken",
                "STATUS": "PASS" if outbound_sales <= outbound_strategy_taken else "REVIEW",
                "DETAIL": f"{whole(outbound_sales)} sales / {whole(outbound_strategy_taken)} calls taken",
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
                "STATUS": "PASS" if closer_taken <= closer_calls else "REVIEW",
                "DETAIL": f"{whole(closer_taken)} taken / {whole(closer_calls)} calls",
            },
            {
                "CHECK": "Closer offers do not exceed calls taken",
                "STATUS": "PASS" if closer_offers <= closer_taken else "REVIEW",
                "DETAIL": f"{whole(closer_offers)} offers / {whole(closer_taken)} calls taken",
            },
            {
                "CHECK": "Closer sales do not exceed calls taken",
                "STATUS": "PASS" if closer_sales <= closer_taken else "REVIEW",
                "DETAIL": f"{whole(closer_sales)} sales / {whole(closer_taken)} calls taken",
            },
        ]
    )

    checks_df = pd.DataFrame(checks)
    passed_checks = int((checks_df["STATUS"] == "PASS").sum())

    st.metric(
        "Checks passed",
        f"{passed_checks}/{len(checks_df)}",
    )

    display_dataframe(checks_df, height=520)

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
                len(inbound),
                len(outbound),
                len(closer),
                len(objections),
            ],
            "LATEST_BUSINESS_DATE": [
                inbound["TRIAGE_DATE"].max(),
                outbound["OUTBOUND_DATE"].max(),
                closer["STRATEGY_DATE"].max(),
                objections["ACTIVITY_DATE"].max(),
            ],
        }
    )

    display_dataframe(row_counts, height=280)

    st.subheader("Schema validation")

    schema_validation = pd.DataFrame(
        {
            "VIEW": list(REQUIRED_COLUMNS.keys()),
            "EXPECTED_COLUMNS": [
                len(columns)
                for columns in REQUIRED_COLUMNS.values()
            ],
            "LOADED_COLUMNS": [
                len(inbound.columns),
                len(outbound.columns),
                len(closer.columns),
                len(objections.columns),
            ],
            "STATUS": ["PASS", "PASS", "PASS", "PASS"],
        }
    )

    display_dataframe(schema_validation, height=280)

    with st.expander("Show loaded report columns"):
        st.write(
            {
                "INBOUND_SETTER_REPORT": inbound.columns.tolist(),
                "OUTBOUND_SETTER_REPORT": outbound.columns.tolist(),
                "CLOSER_REPORT": closer.columns.tolist(),
                "OBJECTIONS_FACED_REPORT": objections.columns.tolist(),
            }
        )
