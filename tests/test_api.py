"""
Backend integration tests for the Expense Tracker API.

Each test gets a fresh database and upload directory via the `client` fixture.
The VLM (analyze_receipt) is mocked — no real API calls are made.
"""

import pytest
from conftest import FAKE_RECEIPT, TEST_IMAGE


def upload(client, image=TEST_IMAGE):
    """Helper: POST an image to /api/upload and return the response."""
    return client.post(
        "/api/upload",
        files={"file": ("receipt.png", image, "image/png")},
    )


# ─── Expenses CRUD ────────────────────────────────────────────────────────────

class TestExpenses:

    def test_empty_initially(self, client):
        res = client.get("/api/expenses")
        assert res.status_code == 200
        assert res.json() == []

    def test_upload_returns_correct_fields(self, client):
        res = upload(client)
        assert res.status_code == 200
        data = res.json()
        assert data["merchant"] == FAKE_RECEIPT["merchant"]
        assert data["amount"]   == FAKE_RECEIPT["amount"]
        assert data["category"] == FAKE_RECEIPT["category"]
        assert data["date"]     == FAKE_RECEIPT["date"]
        assert data["id"] is not None

    def test_expense_listed_after_upload(self, client):
        upload(client)
        expenses = client.get("/api/expenses").json()
        assert len(expenses) == 1
        assert expenses[0]["merchant"] == FAKE_RECEIPT["merchant"]

    def test_multiple_uploads_all_listed(self, client):
        upload(client)
        upload(client)
        assert len(client.get("/api/expenses").json()) == 2

    def test_expenses_ordered_newest_first(self, client):
        """Most recent upload should appear first in the list."""
        upload(client)
        # Second upload returns a higher ID
        second_id = upload(client).json()["id"]
        expenses = client.get("/api/expenses").json()
        assert expenses[0]["id"] == second_id

    def test_delete_expense(self, client):
        expense_id = upload(client).json()["id"]
        res = client.delete(f"/api/expenses/{expense_id}")
        assert res.status_code == 200
        assert client.get("/api/expenses").json() == []

    def test_delete_nonexistent_returns_404(self, client):
        res = client.delete("/api/expenses/9999")
        assert res.status_code == 404

    def test_upload_rejects_invalid_mime_type(self, client):
        res = client.post(
            "/api/upload",
            files={"file": ("document.pdf", b"fake content", "application/pdf")},
        )
        assert res.status_code == 400

    def test_upload_rejects_oversized_file(self, client):
        big_file = b"x" * (10 * 1024 * 1024 + 1)  # 10 MB + 1 byte
        res = client.post(
            "/api/upload",
            files={"file": ("big.png", big_file, "image/png")},
        )
        assert res.status_code == 400

    def test_vlm_failure_returns_502(self, client, mocker):
        mocker.patch("main.analyze_receipt", side_effect=RuntimeError("API down"))
        res = upload(client)
        assert res.status_code == 502


# ─── Stats ────────────────────────────────────────────────────────────────────

class TestStats:

    def test_stats_empty_initially(self, client):
        assert client.get("/api/stats").json() == []

    def test_stats_aggregates_by_category(self, client, mocker):
        mocker.patch("main.analyze_receipt", side_effect=[
            {**FAKE_RECEIPT, "category": "Groceries", "amount": 20.0},
            {**FAKE_RECEIPT, "category": "Transport",  "amount": 10.0},
            {**FAKE_RECEIPT, "category": "Groceries",  "amount":  5.0},
        ])
        for _ in range(3):
            upload(client)

        stats = {s["category"]: s for s in client.get("/api/stats").json()}

        assert stats["Groceries"]["count"] == 2
        assert stats["Groceries"]["total"] == pytest.approx(25.0)
        assert stats["Transport"]["count"] == 1
        assert stats["Transport"]["total"] == pytest.approx(10.0)

    def test_stats_ordered_by_highest_spend(self, client, mocker):
        mocker.patch("main.analyze_receipt", side_effect=[
            {**FAKE_RECEIPT, "category": "Transport", "amount": 5.0},
            {**FAKE_RECEIPT, "category": "Groceries", "amount": 50.0},
        ])
        upload(client)
        upload(client)

        stats = client.get("/api/stats").json()
        assert stats[0]["category"] == "Groceries"  # highest spend first
