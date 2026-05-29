"""
Streamlit app for GA4 traffic and conversions.

Place this file in the same GitHub repo as:
GA4 API Daily Traffic and Conversions Human Readable.csv
GA4 API Monthly Traffic and Conversions Human Readable.csv

Run locally:
    streamlit run streamlit_app.py
"""

from datetime import date
from pandas.tseries.offsets import DateOffset

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from statsmodels.nonparametric.smoothers_lowess import lowess


DAILY_CSV_PATH = "GA4 API Daily Traffic and Conversions Human Readable.csv"
MONTHLY_CSV_PATH = "GA4 API Monthly Traffic and Conversions Human Readable.csv"


st.set_page_config(
    page_title="Chronicle.com GA4 Metrics",
    page_icon="📈",
    layout="wide",
)

st.markdown("""
    <style>
    .block-container {
        padding-top: 1rem;
    }
    </style>
""", unsafe_allow_html=True)

@st.cache_data(show_spinner=False)
def load_data(csv_path_or_url: str) -> pd.DataFrame:
    """Load the GA4 CSV and normalize the Date column."""
    df = pd.read_csv(csv_path_or_url)

    if "Date" not in df.columns:
        if "Month" in df.columns:
            df = df.rename(columns={"Month": "Date"})
        else:
            raise ValueError("The CSV must contain a `Date` or `Month` column.")

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values("Date")

    return df


def get_metric_columns(df: pd.DataFrame) -> list[str]:
    """Return numeric columns that can be charted."""
    metric_cols = []

    for col in df.columns:
        if col == "Date":
            continue

        converted = pd.to_numeric(df[col], errors="coerce")

        if converted.notna().any():
            metric_cols.append(col)

    return metric_cols


def smooth_metric(df: pd.DataFrame, metric: str, frac: float) -> pd.Series:
    """Apply LOWESS smoothing to one metric."""
    y = pd.to_numeric(df[metric], errors="coerce")
    x = df["Date"].map(pd.Timestamp.toordinal)

    valid = y.notna() & x.notna()

    smoothed = pd.Series(index=df.index, dtype="float64")

    if valid.sum() < 3:
        smoothed.loc[valid] = y.loc[valid]
        return smoothed

    smoothed.loc[valid] = lowess(
        y.loc[valid],
        x.loc[valid],
        frac=frac,
        return_sorted=False,
    )

    return smoothed


def is_rate_metric(metric: str) -> bool:
    """Detect metrics that should be formatted as percentages."""
    return " Rate" in metric or metric.endswith("Rate") or "DAU Per MAU" in metric


def metric_tick_format(metric: str) -> str:
    """Plotly tick format for a metric."""
    if is_rate_metric(metric):
        return ".1%"

    return ",.0f"


def build_chart(
    df: pd.DataFrame,
    metrics: list[str],
    frac: float,
    chart_mode: str,
    show_raw_values: bool,
) -> go.Figure:
    """Build a single-axis or dual-axis Plotly chart."""
    fig = go.Figure()

    smoothed_metrics = {
        metric: smooth_metric(df, metric, frac)
        for metric in metrics
    }

    if chart_mode == "Dual axis":
        left_metric, right_metric = metrics

        if show_raw_values:
            fig.add_trace(
                go.Scatter(
                    x=df["Date"],
                    y=pd.to_numeric(df[left_metric], errors="coerce"),
                    mode="lines",
                    name=f"{left_metric} raw",
                    opacity=0.25,
                    yaxis="y",
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=df["Date"],
                    y=pd.to_numeric(df[right_metric], errors="coerce"),
                    mode="lines",
                    name=f"{right_metric} raw",
                    opacity=0.25,
                    yaxis="y2",
                )
            )

        fig.add_trace(
            go.Scatter(
                x=df["Date"],
                y=smoothed_metrics[left_metric],
                mode="lines",
                name=f"{left_metric}",
                yaxis="y",
                line={"width": 3},
            )
        )
        fig.add_trace(
            go.Scatter(
                x=df["Date"],
                y=smoothed_metrics[right_metric],
                mode="lines",
                name=f"{right_metric}",
                yaxis="y2",
                line={"width": 3},
            )
        )

        fig.update_layout(
            yaxis={
                "title": left_metric,
                "tickformat": metric_tick_format(left_metric),
                "rangemode": "tozero",
            },
            yaxis2={
                "title": right_metric,
                "tickformat": metric_tick_format(right_metric),
                "overlaying": "y",
                "side": "right",
                "rangemode": "tozero",
            },
        )

    else:
        for metric in metrics:
            if show_raw_values:
                fig.add_trace(
                    go.Scatter(
                        x=df["Date"],
                        y=pd.to_numeric(df[metric], errors="coerce"),
                        mode="lines",
                        name=f"{metric} raw",
                        opacity=0.20,
                    )
                )

            fig.add_trace(
                go.Scatter(
                    x=df["Date"],
                    y=smoothed_metrics[metric],
                    mode="lines",
                    name=f"{metric}",
                    line={"width": 3},
                )
            )

        shared_rate_format = all(is_rate_metric(metric) for metric in metrics)

        fig.update_layout(
            yaxis={
                #"title": "Value",
                "tickformat": ".1%" if shared_rate_format else ",.0f",
                "rangemode": "tozero",
            },
        )

    fig.update_layout(
        #title=None,
        #xaxis_title="Date",
        hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
        margin={"l": 40, "r": 40, "t": 90, "b": 40},
        height=650,
    )

    return fig


st.title("Chronicle.com GA4 metrics")
st.caption("Select metrics, date range, smoothing, and chart axis mode from the CSV.")

with st.sidebar:
    st.header("Data")

    use_monthly_data = st.checkbox(
        "Use monthly data",
        value=False,
        help="Leave unchecked for daily data. Check to load the monthly CSV from this repo.",
    )

    data_frequency = "Monthly" if use_monthly_data else "Daily"
    default_csv_path = MONTHLY_CSV_PATH if use_monthly_data else DAILY_CSV_PATH

    csv_path_or_url = st.text_input(
        "CSV path or raw GitHub URL",
        value=default_csv_path,
        key=f"csv_path_or_url_{data_frequency.lower()}",
        help=(
            "For GitHub, use the raw CSV URL. If the CSV is in the same repo as this app, "
            "leave the default filename."
        ),
    )

try:
    data = load_data(csv_path_or_url)
except Exception as exc:
    st.error(f"Could not load CSV: {exc}")
    st.stop()

metric_columns = get_metric_columns(data)

if not metric_columns:
    st.error("No numeric metric columns were found in the CSV.")
    st.stop()

min_date = data["Date"].min().date()
max_date = data["Date"].max().date()

with st.sidebar:
    st.header("Chart controls")

    chart_mode = st.radio(
        "Axis mode",
        options=["Single axis", "Dual axis"],
        horizontal=True,
    )

    max_metrics = 2 if chart_mode == "Dual axis" else 7

    default_single_axis_metrics = [
        metric
        for metric in ["Page Views", "Active Users", "Minutes"]
        if metric in metric_columns
    ]

    default_metrics = (
        ["Account Creations", "Purchases"]
        if chart_mode == "Dual axis"
        and {"Account Creations", "Purchases"}.issubset(metric_columns)
        else default_single_axis_metrics or metric_columns[:max_metrics]
    )

    selected_metrics = st.multiselect(
        "Metrics",
        options=metric_columns,
        default=default_metrics,
        max_selections=max_metrics,
        help=(
            "Dual axis charts are limited to two metrics. "
            "Single axis charts are limited to seven metrics."
        ),
    )

    frac = st.slider(
        "Smoothing level",
        min_value=0.01,
        max_value=1.00,
        value=0.10,
        step=0.01,
        help=f"Lower values track {data_frequency.lower()} movement more closely; higher values create a smoother trend.",
    )

    default_start = max(min_date, (pd.Timestamp(max_date) - DateOffset(years=1)).date())

    start_date, end_date = st.date_input(
        "Date range",
        value=(default_start, max_date),
        min_value=min_date,
        max_value=max_date,
        help="The end date defaults to the most recent date in the CSV.",
    )

    show_raw_values = st.checkbox(
        f"Show raw {data_frequency.lower()} values behind smoothed lines",
        value=False,
    )

if chart_mode == "Dual axis" and len(selected_metrics) != 2:
    st.warning("Select exactly two metrics for a dual-axis chart.")
    st.stop()

if chart_mode == "Single axis" and not selected_metrics:
    st.warning("Select at least one metric for a single-axis chart.")
    st.stop()

filtered = data[
    (data["Date"].dt.date >= start_date)
    & (data["Date"].dt.date <= end_date)
].copy()

if filtered.empty:
    st.warning("No rows are available for the selected date range.")
    st.stop()

latest_available = data["Date"].max().strftime("%B %d, %Y").replace(" 0", " ")
st.write(
    f"Showing **{data_frequency.lower()}** data from "
    f"**{start_date.strftime('%B %d, %Y').replace(' 0', ' ')}** "
    f"through **{end_date.strftime('%B %d, %Y').replace(' 0', ' ')}**. "
    f"Latest date available: **{latest_available}**."
)

fig = build_chart(
    df=filtered,
    metrics=selected_metrics,
    frac=frac,
    chart_mode=chart_mode,
    show_raw_values=show_raw_values,
)

st.plotly_chart(fig, use_container_width=True)

with st.expander("Raw data"):
    st.dataframe(
        filtered[["Date", *selected_metrics]].sort_values("Date", ascending=False),
        use_container_width=True,
        hide_index=True,
    )
