"""
End-to-end tests for the Expense Tracker UI.

These tests run against a real (local) server started by the `live_server`
fixture in conftest.py. The VLM is mocked, so no API key is needed.

Run with:
    uv run pytest tests/test_e2e.py
"""

from unittest.mock import patch as mock_patch

import httpx
import pytest
from playwright.sync_api import Page, expect

from conftest import FAKE_RECEIPT, TEST_IMAGE


@pytest.fixture(autouse=True)
def clean_expenses(live_server):
    """Delete all expenses after each test so the next one starts fresh."""
    yield
    for expense in httpx.get(f"{live_server}/api/expenses").json():
        httpx.delete(f"{live_server}/api/expenses/{expense['id']}")


# ─── Tests ────────────────────────────────────────────────────────────────────

def test_page_loads(page: Page, live_server: str):
    """The page renders with the upload area and an empty-state message."""
    page.goto(live_server)
    expect(page).to_have_title("Expense Tracker")
    expect(page.locator("#upload-area")).to_be_visible()
    expect(page.locator("#empty-row")).to_be_visible()


def test_upload_shows_success_message(page: Page, live_server: str, receipt_file):
    """After uploading a receipt, the success alert shows the merchant name."""
    page.goto(live_server)
    page.locator("#file-input").set_input_files(str(receipt_file))

    expect(page.locator("#upload-result")).to_be_visible(timeout=10_000)
    assert FAKE_RECEIPT["merchant"] in page.locator("#result-text").inner_text()


def test_expense_appears_in_table(page: Page, live_server: str, receipt_file):
    """After upload the empty state disappears and the expense row is rendered."""
    page.goto(live_server)
    page.locator("#file-input").set_input_files(str(receipt_file))

    expect(page.locator("#empty-row")).to_be_hidden(timeout=10_000)

    row = page.locator("#expenses-body tr:not(#empty-row)").first
    expect(row).to_contain_text(FAKE_RECEIPT["merchant"])
    expect(row).to_contain_text(FAKE_RECEIPT["category"])


def test_total_badge_updates_after_upload(page: Page, live_server: str, receipt_file):
    """The total badge in the header should reflect the uploaded amount."""
    page.goto(live_server)
    page.locator("#file-input").set_input_files(str(receipt_file))

    expect(page.locator("#empty-row")).to_be_hidden(timeout=10_000)
    # Badge should no longer show €0,00
    assert page.locator("#total-badge").inner_text() != "€0,00"


def test_delete_expense_from_ui(page: Page, live_server: str, receipt_file):
    """Clicking delete and confirming the dialog removes the expense row."""
    page.goto(live_server)
    page.locator("#file-input").set_input_files(str(receipt_file))
    expect(page.locator("#empty-row")).to_be_hidden(timeout=10_000)

    # Intercept the confirm() dialog and accept it
    page.on("dialog", lambda d: d.accept())
    page.locator("#expenses-body button[data-id]").first.click()

    expect(page.locator("#empty-row")).to_be_visible(timeout=5_000)


def test_category_filter(page: Page, live_server: str, receipt_file):
    """
    With two expenses of different categories, the filter shows only the
    matching rows and hides the others.
    """
    # Upload a Groceries expense via the UI
    page.goto(live_server)
    page.locator("#file-input").set_input_files(str(receipt_file))
    expect(page.locator("#empty-row")).to_be_hidden(timeout=10_000)

    # Upload a Transport expense via the API, temporarily overriding the mock
    transport_receipt = {**FAKE_RECEIPT, "category": "Transport"}
    with mock_patch("main.analyze_receipt", return_value=transport_receipt):
        httpx.post(
            f"{live_server}/api/upload",
            files={"file": ("receipt.png", TEST_IMAGE, "image/png")},
        )

    # Reload so the second expense appears in the table
    page.reload()
    expect(page.locator("#expenses-body tr:not(#empty-row)")).to_have_count(2)

    # Filter to Groceries — only the Groceries row is shown
    page.select_option("#category-filter", "Groceries")
    expect(page.locator("#expenses-body tr:not(#empty-row)")).to_have_count(1)

    # Filter to Transport — only the Transport row is shown
    page.select_option("#category-filter", "Transport")
    expect(page.locator("#expenses-body tr:not(#empty-row)")).to_have_count(1)
