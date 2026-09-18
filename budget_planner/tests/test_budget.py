"""
tests/test_budget.py — pytest unit tests for budget.py business logic.
Run with: pytest tests/ -v   (from the budget_planner/ directory)
"""

from __future__ import annotations

import datetime
import os
import tempfile

import pytest

# ---------------------------------------------------------------------------
# Ensure budget.py is importable when running from the project root
# ---------------------------------------------------------------------------
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from budget import (  # noqa: E402
    CATEGORIES,
    BudgetPlanner,
    Expense,
    InvalidBudgetError,
    InvalidExpenseError,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TODAY = datetime.date.today()
YESTERDAY = TODAY - datetime.timedelta(days=1)
TOMORROW = TODAY + datetime.timedelta(days=1)


def make_planner() -> BudgetPlanner:
    """Return a BudgetPlanner backed by temporary files so tests are isolated."""
    tmp = tempfile.mkdtemp()
    return BudgetPlanner(
        data_file=os.path.join(tmp, "expenses.csv"),
        budget_file=os.path.join(tmp, "budget.csv"),
    )


# ---------------------------------------------------------------------------
# Expense dataclass
# ---------------------------------------------------------------------------


class TestExpense:
    def test_to_dict_and_back(self) -> None:
        exp = Expense(
            amount=42.5,
            category="Food",
            description="Lunch",
            date=YESTERDAY,
        )
        row = exp.to_dict()
        restored = Expense.from_dict(row)
        assert restored.amount == exp.amount
        assert restored.category == exp.category
        assert restored.description == exp.description
        assert restored.date == exp.date

    def test_to_dict_keys(self) -> None:
        exp = Expense(10.0, "Travel", "Bus", TODAY)
        assert set(exp.to_dict().keys()) == {"amount", "category", "description", "date"}

    def test_from_dict_invalid_amount_raises(self) -> None:
        with pytest.raises(ValueError):
            Expense.from_dict(
                {"amount": "not_a_number", "category": "Food", "description": "x", "date": str(TODAY)}
            )


# ---------------------------------------------------------------------------
# BudgetPlanner.set_budget
# ---------------------------------------------------------------------------


class TestSetBudget:
    def test_valid_budget_stored(self) -> None:
        p = make_planner()
        p.set_budget(1000.0)
        assert p.monthly_budget == 1000.0

    def test_budget_zero_raises(self) -> None:
        p = make_planner()
        with pytest.raises(InvalidBudgetError):
            p.set_budget(0)

    def test_budget_negative_raises(self) -> None:
        p = make_planner()
        with pytest.raises(InvalidBudgetError):
            p.set_budget(-50)

    def test_budget_replaces_previous(self) -> None:
        p = make_planner()
        p.set_budget(500)
        p.set_budget(1200)
        assert p.monthly_budget == 1200.0

    def test_budget_bool_raises(self) -> None:
        # bool is a subclass of int; True == 1 but should not be accepted
        p = make_planner()
        with pytest.raises(InvalidBudgetError):
            p.set_budget(True)  # type: ignore[arg-type]

    def test_integer_budget_accepted(self) -> None:
        p = make_planner()
        p.set_budget(750)
        assert p.monthly_budget == 750.0


# ---------------------------------------------------------------------------
# BudgetPlanner.add_expense
# ---------------------------------------------------------------------------


class TestAddExpense:
    def test_valid_expense_stored(self) -> None:
        p = make_planner()
        p.set_budget(500)
        exp = p.add_expense(20.0, "Food", "Groceries", TODAY)
        assert len(p.get_all_expenses()) == 1
        assert exp.amount == 20.0
        assert exp.category == "Food"

    def test_multiple_expenses_stored(self) -> None:
        p = make_planner()
        p.set_budget(1000)
        p.add_expense(50, "Food", "Dinner", TODAY)
        p.add_expense(100, "Travel", "Flight", YESTERDAY)
        assert len(p.get_all_expenses()) == 2

    def test_zero_amount_raises(self) -> None:
        p = make_planner()
        p.set_budget(500)
        with pytest.raises(InvalidExpenseError):
            p.add_expense(0, "Food", "test", TODAY)

    def test_negative_amount_raises(self) -> None:
        p = make_planner()
        p.set_budget(500)
        with pytest.raises(InvalidExpenseError):
            p.add_expense(-10, "Food", "test", TODAY)

    def test_invalid_category_raises(self) -> None:
        p = make_planner()
        p.set_budget(500)
        with pytest.raises(InvalidExpenseError):
            p.add_expense(10, "Gambling", "test", TODAY)

    def test_empty_description_raises(self) -> None:
        p = make_planner()
        p.set_budget(500)
        with pytest.raises(InvalidExpenseError):
            p.add_expense(10, "Food", "", TODAY)

    def test_whitespace_only_description_raises(self) -> None:
        p = make_planner()
        p.set_budget(500)
        with pytest.raises(InvalidExpenseError):
            p.add_expense(10, "Food", "   ", TODAY)

    def test_description_stripped(self) -> None:
        p = make_planner()
        p.set_budget(500)
        exp = p.add_expense(10, "Food", "  Lunch  ", TODAY)
        assert exp.description == "Lunch"

    def test_future_date_raises(self) -> None:
        p = make_planner()
        p.set_budget(500)
        with pytest.raises(InvalidExpenseError):
            p.add_expense(10, "Food", "test", TOMORROW)

    def test_today_date_accepted(self) -> None:
        p = make_planner()
        p.set_budget(500)
        exp = p.add_expense(15, "Shopping", "Shirt", TODAY)
        assert exp.date == TODAY

    def test_yesterday_date_accepted(self) -> None:
        p = make_planner()
        p.set_budget(500)
        exp = p.add_expense(25, "Education", "Book", YESTERDAY)
        assert exp.date == YESTERDAY

    def test_description_too_long_raises(self) -> None:
        p = make_planner()
        p.set_budget(500)
        with pytest.raises(InvalidExpenseError):
            p.add_expense(10, "Food", "x" * 101, TODAY)

    def test_all_categories_accepted(self) -> None:
        p = make_planner()
        p.set_budget(1000)
        for cat in CATEGORIES:
            p.add_expense(1.0, cat, f"{cat} item", TODAY)
        assert len(p.get_all_expenses()) == len(CATEGORIES)


# ---------------------------------------------------------------------------
# Calculations
# ---------------------------------------------------------------------------


class TestCalculations:
    def test_total_spent_empty(self) -> None:
        p = make_planner()
        assert p.get_total_spent() == 0.0

    def test_total_spent_single(self) -> None:
        p = make_planner()
        p.set_budget(500)
        p.add_expense(75.5, "Food", "Dinner", TODAY)
        assert p.get_total_spent() == 75.5

    def test_total_spent_multiple(self) -> None:
        p = make_planner()
        p.set_budget(500)
        p.add_expense(100, "Food", "Groceries", TODAY)
        p.add_expense(50, "Travel", "Bus", TODAY)
        p.add_expense(30, "Shopping", "Socks", TODAY)
        assert p.get_total_spent() == 180.0

    def test_remaining_budget_positive(self) -> None:
        p = make_planner()
        p.set_budget(500)
        p.add_expense(100, "Food", "Dinner", TODAY)
        assert p.get_remaining_budget() == 400.0

    def test_remaining_budget_zero(self) -> None:
        p = make_planner()
        p.set_budget(100)
        p.add_expense(100, "Food", "Dinner", TODAY)
        assert p.get_remaining_budget() == 0.0

    def test_remaining_budget_negative_overspend(self) -> None:
        p = make_planner()
        p.set_budget(50)
        p.add_expense(80, "Shopping", "Jacket", TODAY)
        assert p.get_remaining_budget() == -30.0

    def test_remaining_budget_no_budget_set(self) -> None:
        p = make_planner()
        # budget is 0.0 by default
        p.add_expense  # not called — just checking baseline
        assert p.get_remaining_budget() == 0.0


# ---------------------------------------------------------------------------
# Category breakdown
# ---------------------------------------------------------------------------


class TestCategoryBreakdown:
    def test_empty_returns_empty_dict(self) -> None:
        p = make_planner()
        assert p.get_expenses_by_category() == {}

    def test_single_category(self) -> None:
        p = make_planner()
        p.set_budget(500)
        p.add_expense(50, "Food", "Lunch", TODAY)
        p.add_expense(30, "Food", "Dinner", TODAY)
        result = p.get_expenses_by_category()
        assert result == {"Food": 80.0}

    def test_multiple_categories(self) -> None:
        p = make_planner()
        p.set_budget(1000)
        p.add_expense(100, "Food", "Groceries", TODAY)
        p.add_expense(200, "Travel", "Flight", YESTERDAY)
        p.add_expense(50, "Food", "Snacks", TODAY)
        result = p.get_expenses_by_category()
        assert result["Food"] == 150.0
        assert result["Travel"] == 200.0
        assert "Shopping" not in result

    def test_all_four_categories(self) -> None:
        p = make_planner()
        p.set_budget(1000)
        for cat in CATEGORIES:
            p.add_expense(25.0, cat, f"{cat} item", TODAY)
        result = p.get_expenses_by_category()
        assert set(result.keys()) == set(CATEGORIES)
        assert all(v == 25.0 for v in result.values())


# ---------------------------------------------------------------------------
# Delete expense
# ---------------------------------------------------------------------------


class TestDeleteExpense:
    def test_delete_reduces_list(self) -> None:
        p = make_planner()
        p.set_budget(500)
        p.add_expense(10, "Food", "Coffee", TODAY)
        p.add_expense(20, "Travel", "Bus", TODAY)
        p.delete_expense(0)
        assert len(p.get_all_expenses()) == 1

    def test_delete_correct_item(self) -> None:
        p = make_planner()
        p.set_budget(500)
        p.add_expense(10, "Food", "Coffee", TODAY)
        p.add_expense(20, "Travel", "Bus", TODAY)
        p.delete_expense(0)
        remaining = p.get_all_expenses()
        assert remaining[0].description == "Bus"

    def test_delete_invalid_index_raises(self) -> None:
        p = make_planner()
        p.set_budget(500)
        with pytest.raises(IndexError):
            p.delete_expense(0)

    def test_delete_negative_index_raises(self) -> None:
        p = make_planner()
        p.set_budget(500)
        p.add_expense(10, "Food", "Coffee", TODAY)
        with pytest.raises(IndexError):
            p.delete_expense(-1)


# ---------------------------------------------------------------------------
# Persistence (CSV round-trip)
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_budget_persists_across_instances(self) -> None:
        tmp = tempfile.mkdtemp()
        df = os.path.join(tmp, "e.csv")
        bf = os.path.join(tmp, "b.csv")

        p1 = BudgetPlanner(data_file=df, budget_file=bf)
        p1.set_budget(800)

        p2 = BudgetPlanner(data_file=df, budget_file=bf)
        assert p2.monthly_budget == 800.0

    def test_expenses_persist_across_instances(self) -> None:
        tmp = tempfile.mkdtemp()
        df = os.path.join(tmp, "e.csv")
        bf = os.path.join(tmp, "b.csv")

        p1 = BudgetPlanner(data_file=df, budget_file=bf)
        p1.set_budget(500)
        p1.add_expense(99.99, "Shopping", "Shoes", YESTERDAY)

        p2 = BudgetPlanner(data_file=df, budget_file=bf)
        loaded = p2.get_all_expenses()
        assert len(loaded) == 1
        assert loaded[0].amount == 99.99
        assert loaded[0].category == "Shopping"
        assert loaded[0].description == "Shoes"
        assert loaded[0].date == YESTERDAY

    def test_no_data_files_starts_clean(self) -> None:
        tmp = tempfile.mkdtemp()
        p = BudgetPlanner(
            data_file=os.path.join(tmp, "missing_e.csv"),
            budget_file=os.path.join(tmp, "missing_b.csv"),
        )
        assert p.monthly_budget == 0.0
        assert p.get_all_expenses() == []
