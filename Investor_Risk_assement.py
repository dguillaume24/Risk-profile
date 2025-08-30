# app.py
import sys
from pathlib import Path
from typing import Dict, Tuple

import pandas as pd
import plotly.express as px
import streamlit as st

# ----------------------------
# Config & constants
# ----------------------------
st.set_page_config(page_title="Risk profile", layout="wide")

DATA_DIR = Path(".")
QUESTION_7_CSV = DATA_DIR / "question_7.csv"
RISK_MATRIX_CSV = DATA_DIR / "Risk_profile_matrix.csv"
PORTFOLIO_TYPE_CSV = DATA_DIR / "Portfolio_type.csv"


# ----------------------------
# Utilities
# ----------------------------
@st.cache_data
def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        st.error(f"Required data file not found: `{path}`")
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception as e:
        st.error(f"Could not read `{path.name}`: {e}")
        return pd.DataFrame()


def bar_chart_display(df: pd.DataFrame, category: str, y_value: str) -> None:
    """Display a simple sorted bar chart with totals."""
    if df.empty or category not in df.columns or y_value not in df.columns:
        st.warning("Nothing to plot.")
        return
    grouped = (
        df.groupby(category, as_index=False)[y_value]
        .sum(numeric_only=True)
        .round(2)
        .sort_values(by=y_value, ascending=True)
    )
    fig = px.bar(grouped, x=category, y=y_value, color=category, text=y_value)
    fig.update_layout(showlegend=False, margin=dict(t=10, r=10, b=10, l=10))
    fig.update_traces(texttemplate="%{text}", textposition="outside")
    st.plotly_chart(fig, use_container_width=True)


def score_from_radio(prompt: str, options_to_points: Dict[str, int], key: str) -> int:
    """Render a radio and return the corresponding score based on the selected label."""
    labels = list(options_to_points.keys())
    choice = st.radio(prompt, labels, index=0, key=key)
    return options_to_points.get(choice, 0)


# ----------------------------
# Questionnaire sections
# ----------------------------
def render_time_horizon() -> Tuple[int, Dict[str, int]]:
    st.subheader("Risk profile")
    st.write("### Time horizon")

    q1 = {
        "Less than 3 years": 1,
        "3–5 years": 3,
        "6–10 years": 7,
        "11 years or more": 10,
    }
    q2 = {
        "Less than 2 years": 0,
        "2–5 years": 1,
        "6–10 years": 4,
        "11 years or more": 8,
    }

    scores = {}
    scores["question_1"] = score_from_radio(
        "I plan to begin withdrawing money from my investments in:", q1, "q1"
    )
    scores["question_2"] = score_from_radio(
        "Once I begin withdrawing funds from my investments, I plan to spend all of the funds in:",
        q2,
        "q2",
    )

    time_horizon_score = scores["question_1"] + scores["question_2"]
    st.markdown(f"**Time horizon score:** {time_horizon_score}")
    return time_horizon_score, scores


def render_risk_tolerance() -> Tuple[int, Dict[str, int]]:
    st.write("### Risk tolerance")

    q3 = {"None": 1, "Limited": 3, "Good": 7, "Extensive": 10}
    q4 = {
        "Take lower than average risks expecting to earn lower than average returns": 0,
        "Take average risks expecting to earn average returns": 4,
        "Take above average risks expecting to earn above average returns": 8,
    }
    q5 = {
        "Bonds and/or bond funds": 3,
        "Stocks and/or stock funds": 6,
        "International securities and/or international funds": 8,
    }
    q6 = {
        "Sell all of my shares": 0,
        "Sell some of my shares": 2,
        "Do nothing": 5,
        "Buy more shares": 8,
    }

    scores = {}
    scores["question_3"] = score_from_radio(
        "I would describe my knowledge of investments as:", q3, "q3"
    )
    scores["question_4"] = score_from_radio(
        "What amount of financial risk are you willing to take when you invest?", q4, "q4"
    )
    scores["question_5"] = score_from_radio(
        "Select the investments you currently own or have owned:", q5, "q5"
    )
    scores["question_6"] = score_from_radio(
        (
            "Imagine that in the past three months, the overall stock market lost 25% of its value. "
            "An individual stock investment you own also lost 25% of its value. What would you do?"
        ),
        q6,
        "q6",
    )

    # Question 7: plans table
    df_q7 = load_csv(QUESTION_7_CSV)
    q7_points = 0
    if not df_q7.empty and {"Plan", "Points"}.issubset(df_q7.columns):
        st.write(
            "We’ve outlined the most likely best-case and worst-case annual returns of five hypothetical "
            "investment plans. Which range of possible outcomes is most acceptable to you? "
            "The figures are hypothetical and do not represent the performance of any particular investment."
        )
        col1, col2 = st.columns([0.18, 0.82])
        with col1:
            plan_choice = st.radio("", list(df_q7["Plan"]), index=0, key="q7")
        with col2:
            st.dataframe(df_q7.iloc[:, :-1], hide_index=True, use_container_width=True)
        # Get points for the selected plan
        match = df_q7.loc[df_q7["Plan"] == plan_choice, "Points"]
        if not match.empty:
            q7_points = int(match.iloc[0])
    else:
        st.info("Question 7 table is unavailable; scoring continues without it.")

    risk_tolerance_score = (
        scores["question_3"]
        + scores["question_4"]
        + scores["question_5"]
        + scores["question_6"]
        + q7_points
    )

    # Cap at 40 as per original logic
    risk_tolerance_score = min(risk_tolerance_score, 40)
    st.markdown(f"**Risk tolerance score:** {risk_tolerance_score}")

    return risk_tolerance_score, scores


# ----------------------------
# Portfolio mapping & display
# ----------------------------
def show_portfolio(time_horizon_score: int, risk_tolerance_score: int) -> None:
    df_risk_matrix = load_csv(RISK_MATRIX_CSV)
    df_portfolio = load_csv(PORTFOLIO_TYPE_CSV)

    if df_risk_matrix.empty or df_portfolio.empty:
        st.stop()

    # Ensure expected columns exist
    if "Time_horizon_score" not in df_risk_matrix.columns:
        st.error("`Risk_profile_matrix.csv` missing 'Time_horizon_score' column.")
        st.stop()

    # Risk tolerance score is used as a string column name in the matrix
    col_name = str(risk_tolerance_score)
    if col_name not in df_risk_matrix.columns:
        st.warning(
            f"No portfolio mapping found for risk tolerance score '{col_name}'."
        )
        st.stop()

    row = df_risk_matrix.loc[df_risk_matrix["Time_horizon_score"] == time_horizon_score]
    if row.empty:
        st.warning(
            f"No portfolio mapping for time horizon score '{time_horizon_score}'."
        )
        st.stop()

    portfolio_type = str(row[col_name].iloc[0]).strip().lower()
    st.subheader(portfolio_type.capitalize())

    # Normalize portfolio type names for join
    df_portfolio = df_portfolio.copy()
    if "type_name" not in df_portfolio.columns:
        st.error("`Portfolio_type.csv` missing 'type_name' column.")
        st.stop()

    df_portfolio["type_name"] = df_portfolio["type_name"].str.lower()
    filtered = df_portfolio[df_portfolio["type_name"] == portfolio_type]
    if filtered.empty:
        st.warning(f"Portfolio details not found for type '{portfolio_type}'.")
        st.stop()

    # Description
    if "investor_type" in filtered.columns:
        desc = str(filtered["investor_type"].iloc[0])
        st.markdown(f"**{portfolio_type.capitalize()} profile:** {desc}")

    # Typical returns table
    returns_cols = ["average_annual_return", "best_year", "worst_year"]
    if all(c in filtered.columns for c in returns_cols):
        returns = (
            filtered[returns_cols]
            .rename(columns=lambda c: " ".join(c.split("_")).capitalize())
            .T
        )
        colname = returns.columns[0]
        st.data_editor(
            returns,
            column_config={
                str(colname): st.column_config.NumberColumn(
                    "Revenue %",
                    format="%.1f %%",
                    width="medium",
                )
            },
            hide_index=False,
        )

    # Composition + chart
    comp_cols = [
        "large_cap_equity",
        "small_cap_equity",
        "international_equity",
        "fixed_income",
        "cash_investments",
    ]
    if all(c in filtered.columns for c in comp_cols):
        comp = (
            filtered[comp_cols]
            .rename(columns=lambda c: " ".join(c.split("_")).capitalize())
            .T.rename(columns={filtered.index[0]: "Weight"})
        )
        comp["Weight"] = pd.to_numeric(comp["Weight"], errors="coerce").fillna(0).astype(int)
        comp = comp.sort_values(by="Weight", ascending=False)
        st.write(
            f"Based on your risk profile — **{portfolio_type.capitalize()}** — the suggested portfolio is:"
        )
        comp_reset = comp.reset_index().rename(columns={"index": "Asset class"})
        bar_chart_display(comp_reset, "Asset class", "Weight")

        with st.expander("Definitions"):
            st.markdown(
                """
- **Large-cap**: companies with market capitalization > $10B.  
- **Small-cap**: companies with market capitalization about $250M–$2B.  
- **International equities**: stocks purchased outside the U.S. market.  
- **Fixed income**: securities paying fixed interest/dividends until maturity.  
- **Cash investments**: short-term obligations (usually < 90 days) offering lower returns.
                """
            )


# ----------------------------
# App
# ----------------------------
def main() -> None:
    st.title("Risk profile assessment")
    st.write("# Investor profile questionnaire")

    st.markdown(
        """
Your investing strategy should reflect the kind of investor you are—your personal investor profile. This quiz will help you
determine your profile and then match it to an investment strategy that’s designed for investors like you. The quiz measures two key factors:

**YOUR TIME HORIZON**  
When will you begin withdrawing money from your account and at what rate? If it’s many years away, there may be
more time to weather the market’s inevitable ups and downs and you may be comfortable with a portfolio that has a
greater potential for appreciation and a higher level of risk.

**YOUR RISK TOLERANCE**  
How do you feel about risk? Some investments fluctuate more dramatically in value than others but may have the
potential for higher returns. It’s important to select investments that fit within your level of tolerance for this risk.
"""
    )

    time_horizon_score, _ = render_time_horizon()

    if time_horizon_score < 3:
        st.info(
            """
A score of less than 3 indicates a very short investment time horizon. For such a short time horizon, a relatively low-risk
portfolio of **40% short-term bonds** (average maturity ≤ 5 years) and **60% cash investments** is suggested, as stock investments
may be significantly more volatile in the short term.
"""
        )
        return

    risk_tolerance_score, _ = render_risk_tolerance()
    show_portfolio(time_horizon_score, risk_tolerance_score)


if __name__ == "__main__":
    # Allow running as a module or script
    try:
        main()
    except Exception as e:
        st.error(f"Unexpected error: {e}")
        # Also log to stderr for debugging in hosted environments
        print(f"Unexpected error: {e}", file=sys.stderr)
