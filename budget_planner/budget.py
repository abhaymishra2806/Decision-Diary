"""
budget.py — Core business logic for the Personal Budget Planner.
No Streamlit imports here; this module is UI-agnostic.
"""

from __future__ import annotations

import csv
import datetime
import os
from dataclasses import dataclass, field
from typing import Dict, List

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CATEGORIES: List[str] = ["Food", "Travel", "Shopping", "Education"]
DATA_FILE: str = "expenses.csv"
BUDGET_FILE: str = "budget.csv"

CSV_FIELDNAMES: List[str] = ["amount", "category", "description", "date"]


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------


@dataclass
class Expense:
    """Represents a single expense entry."""

    amount: float
    category: str
    description: str
    date: datetime.date

    def to_dict(self) -> Dict[str, str]:
        """Serialise to a plain dict suitable for CSV writing."""
        return {
            "amount": str(self.amount),
            "category": self.category,
            "description": self.description,
            "date": self.date.isoformat(),
        }

    @staticmethod
    def from_dict(row: Dict[str, str]) -> "Expense":
        """Deserialise from a CSV row dict."""
        return Expense(
            amount=float(row["amount"]),
            category=row["category"],
            description=row["description"],
            date=datetime.date.fromisoformat(row["date"]),
        )


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class InvalidBudgetError(ValueError):
    """Raised when a budget value is invalid."""


class InvalidExpenseError(ValueError):
    """Raised when an expense field is invalid."""


# ---------------------------------------------------------------------------
# BudgetPlanner
# ---------------------------------------------------------------------------


class BudgetPlanner:
    """
    Manages the monthly budget and all expense entries.

    Persistence is handled via two CSV files:
      - budget.csv  : stores the single monthly budget value
      - expenses.csv: stores every expense row
    """

    def __init__(
        self,
        data_file: str = DATA_FILE,
        budget_file: str = BUDGET_FILE,
    ) -> None:
        self._data_file = data_file
        self._budget_file = budget_file
        self._monthly_budget: float = 0.0
        self._expenses: List[Expense] = []

        self._load_budget()
        self._load_expenses()

    # ------------------------------------------------------------------
    # Budget
    # ------------------------------------------------------------------

    def set_budget(self, amount: float) -> None:
        """Set (or replace) the monthly budget. Raises InvalidBudgetError if ≤ 0."""
        if not isinstance(amount, (int, float)) or isinstance(amount, bool):
            raise InvalidBudgetError("Budget must be a number.")
        if amount <= 0:
            raise InvalidBudgetError("Budget must be greater than zero.")
        self._monthly_budget = float(amount)
        self._save_budget()

    @property
    def monthly_budget(self) -> float:
        return self._monthly_budget

    # ------------------------------------------------------------------
    # Expenses
    # ------------------------------------------------------------------

    def add_expense(
        self,
        amount: float,
        category: str,
        description: str,
        date: datetime.date,
    ) -> Expense:
        """
        Validate inputs, create an Expense, persist it, and return it.
        Raises InvalidExpenseError on any validation failure.
        """
        if not isinstance(amount, (int, float)) or isinstance(amount, bool):
            raise InvalidExpenseError("Expense amount must be a number.")
        if amount <= 0:
            raise InvalidExpenseError("Expense amount must be greater than zero.")
        if category not in CATEGORIES:
            raise InvalidExpenseError(
                f"Category must be one of: {', '.join(CATEGORIES)}."
            )
        cleaned = description.strip()
        if not cleaned:
            raise InvalidExpenseError("Description cannot be empty.")
        if len(cleaned) > 100:
            raise InvalidExpenseError("Description must be 100 characters or fewer.")
        if date > datetime.date.today():
            raise InvalidExpenseError("Expense date cannot be in the future.")

        expense = Expense(
            amount=float(amount),
            category=category,
            description=cleaned,
            date=date,
        )
        self._expenses.append(expense)
        self._save_expenses()
        return expense

    def get_all_expenses(self) -> List[Expense]:
        """Return a shallow copy of all expenses."""
        return list(self._expenses)

    def delete_expense(self, index: int) -> None:
        """Remove the expense at the given list index and persist."""
        if index < 0 or index >= len(self._expenses):
            raise IndexError("Expense index out of range.")
        self._expenses.pop(index)
        self._save_expenses()

    # ------------------------------------------------------------------
    # Calculations
    # ------------------------------------------------------------------

    def get_total_spent(self) -> float:
        """Sum of all expense amounts."""
        return round(sum(e.amount for e in self._expenses), 2)

    def get_remaining_budget(self) -> float:
        """Remaining budget (can be negative when overspending)."""
        return round(self._monthly_budget - self.get_total_spent(), 2)

    def get_expenses_by_category(self) -> Dict[str, float]:
        """Return total spending keyed by category, only for categories with spending."""
        totals: Dict[str, float] = {}
        for expense in self._expenses:
            totals[expense.category] = round(
                totals.get(expense.category, 0.0) + expense.amount, 2
            )
        return totals

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _save_budget(self) -> None:
        with open(self._budget_file, "w", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["monthly_budget"])
            writer.writerow([self._monthly_budget])

    def _load_budget(self) -> None:
        if not os.path.exists(self._budget_file):
            return
        with open(self._budget_file, newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                try:
                    self._monthly_budget = float(row["monthly_budget"])
                except (KeyError, ValueError):
                    self._monthly_budget = 0.0
                break  # only one row expected

    def _save_expenses(self) -> None:
        with open(self._data_file, "w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=CSV_FIELDNAMES)
            writer.writeheader()
            for expense in self._expenses:
                writer.writerow(expense.to_dict())

    def _load_expenses(self) -> None:
        if not os.path.exists(self._data_file):
            return
        with open(self._data_file, newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                try:
                    self._expenses.append(Expense.from_dict(row))
                except (KeyError, ValueError):
                    continue  # skip corrupted rows silently
