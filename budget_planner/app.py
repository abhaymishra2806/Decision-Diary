"""
app.py — Streamlit UI for the Personal Budget Planner.
All business logic lives in budget.py; this file only handles display.
"""

from __future__ import annotations

import datetime

import streamlit as st

from budget import CATEGORIES, BudgetPlanner, InvalidBudgetError, InvalidExpenseError

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Personal Budget Planner",
    page_icon="💰",
    layout="centered",
)

# ---------------------------------------------------------------------------
# Session state — one BudgetPlanner instance shared across reruns
# ---------------------------------------------------------------------------


def _get_planner() -> BudgetPlanner:
    if "planner" not in st.session_state:
        st.session_state["planner"] = BudgetPlanner()
    return st.session_state["planner"]  # type: ignore[return-value]


planner = _get_planner()

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.title("💰 Personal Budget Planner")
st.caption("Track your monthly expenses and stay on top of your budget.")
st.divider()

# ---------------------------------------------------------------------------
# Section 1 — Set Monthly Budget
# ---------------------------------------------------------------------------


def render_budget_input(p: BudgetPlanner) -> None:
    st.subheader("📋 Monthly Budget")

    current = p.monthly_budget
    if current > 0:
        st.info(f"Current budget: **${current:,.2f}**")

    with st.form("budget_form", clear_on_submit=True):
        amount = st.number_input(
            "Set / Update Monthly Budget ($)",
            min_value=0.01,
            step=50.0,
            format="%.2f",
            value=current if current > 0 else 500.0,
        )
        submitted = st.form_submit_button("💾 Save Budget")

    if submitted:
        try:
            p.set_budget(amount)
            st.success(f"Budget set to **${amount:,.2f}**")
            st.rerun()
        except InvalidBudgetError as exc:
            st.error(str(exc))


render_budget_input(planner)
st.divider()

# ---------------------------------------------------------------------------
# Section 2 — Add Expense
# ---------------------------------------------------------------------------


def render_add_expense_form(p: BudgetPlanner) -> None:
    st.subheader("➕ Add Expense")

    if p.monthly_budget <= 0:
        st.warning("⚠️ Please set a monthly budget before adding expenses.")
        return

    with st.form("expense_form", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            exp_amount = st.number_input(
                "Amount ($)",
                min_value=0.01,
                step=1.0,
                format="%.2f",
            )
            exp_category = st.selectbox("Category", CATEGORIES)

        with col2:
            exp_date = st.date_input(
                "Date",
                value=datetime.date.today(),
                max_value=datetime.date.today(),
            )
            exp_description = st.text_input(
                "Description",
                max_chars=100,
                placeholder="e.g. Lunch at restaurant",
            )

        submitted = st.form_submit_button("➕ Add Expense")

    if submitted:
        try:
            p.add_expense(
                amount=exp_amount,
                category=exp_category,
                description=exp_description,
                date=exp_date,
            )
            st.success(
                f"Expense of **${exp_amount:,.2f}** added under **{exp_category}**."
            )
            st.rerun()
        except InvalidExpenseError as exc:
            st.error(str(exc))


render_add_expense_form(planner)
st.divider()

# ---------------------------------------------------------------------------
# Section 3 — Summary
# ---------------------------------------------------------------------------


def render_summary(p: BudgetPlanner) -> None:
    st.subheader("📊 Summary")

    if p.monthly_budget <= 0:
        st.info("Set a budget above to see your summary.")
        return

    total_spent = p.get_total_spent()
    remaining = p.get_remaining_budget()
    pct_used = (total_spent / p.monthly_budget * 100) if p.monthly_budget > 0 else 0.0

    col1, col2, col3 = st.columns(3)
    col1.metric("Monthly Budget", f"${p.monthly_budget:,.2f}")
    col2.metric("Total Spent", f"${total_spent:,.2f}")

    if remaining >= 0:
        col3.metric("Remaining", f"${remaining:,.2f}", delta=f"${remaining:,.2f}")
    else:
        col3.metric(
            "Remaining",
            f"-${abs(remaining):,.2f}",
            delta=f"-${abs(remaining):,.2f}",
            delta_color="inverse",
        )

    st.progress(min(pct_used / 100, 1.0))
    if pct_used > 100:
        st.error(
            f"⚠️ You have exceeded your budget by **${abs(remaining):,.2f}** "
            f"({pct_used:.1f}% used)."
        )
    else:
        st.caption(f"{pct_used:.1f}% of budget used.")


render_summary(planner)
st.divider()

# ---------------------------------------------------------------------------
# Section 4 — Category-wise Spending
# ---------------------------------------------------------------------------


def render_category_chart(p: BudgetPlanner) -> None:
    st.subheader("🗂️ Spending by Category")

    by_cat = p.get_expenses_by_category()
    if not by_cat:
        st.info("No expenses recorded yet.")
        return

    # Build a simple dict for st.bar_chart
    chart_data = {"Category": list(by_cat.keys()), "Amount ($)": list(by_cat.values())}

    import pandas as pd  # lightweight; already pulled in by streamlit

    df_chart = pd.DataFrame(chart_data).set_index("Category")
    st.bar_chart(df_chart, color="#3b82d4")

    # Table breakdown
    rows = [
        {"Category": cat, "Spent ($)": f"${amt:,.2f}"}
        for cat, amt in sorted(by_cat.items(), key=lambda x: x[1], reverse=True)
    ]
    st.table(rows)


render_category_chart(planner)
st.divider()

# ---------------------------------------------------------------------------
# Section 5 — All Expenses Table
# ---------------------------------------------------------------------------


def render_expense_table(p: BudgetPlanner) -> None:
    st.subheader("🧾 All Expenses")

    expenses = p.get_all_expenses()
    if not expenses:
        st.info("No expenses recorded yet.")
        return

    import pandas as pd

    rows = [
        {
            "#": i + 1,
            "Date": e.date.strftime("%d %b %Y"),
            "Category": e.category,
            "Description": e.description,
            "Amount ($)": f"${e.amount:,.2f}",
        }
        for i, e in enumerate(expenses)
    ]
    df = pd.DataFrame(rows).set_index("#")
    st.dataframe(df, use_container_width=True)

    # Delete an expense
    with st.expander("🗑️ Delete an Expense"):
        idx = st.number_input(
            "Expense # to delete (see table above)",
            min_value=1,
            max_value=len(expenses),
            step=1,
        )
        if st.button("Delete Selected Expense"):
            try:
                p.delete_expense(int(idx) - 1)
                st.success(f"Expense #{idx} deleted.")
                st.rerun()
            except IndexError as exc:
                st.error(str(exc))

    # CSV Download
    import io

    csv_buf = io.StringIO()
    import csv

    writer = csv.DictWriter(
        csv_buf, fieldnames=["Date", "Category", "Description", "Amount ($)"]
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "Date": row["Date"],
                "Category": row["Category"],
                "Description": row["Description"],
                "Amount ($)": row["Amount ($)"],
            }
        )
    st.download_button(
        label="⬇️ Download as CSV",
        data=csv_buf.getvalue(),
        file_name="expenses_export.csv",
        mime="text/csv",
    )


render_expense_table(planner)
