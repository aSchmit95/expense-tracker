import base64
import threading
import time
from pathlib import Path
from unittest.mock import patch as mock_patch

import pytest
from fastapi.testclient import TestClient

# Minimal 1×1 PNG — valid image bytes used as a fake receipt in all tests
TEST_IMAGE = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)

FAKE_RECEIPT = {
    "amount": 23.50,
    "merchant": "Mercadona",
    "category": "Groceries",
    "date": "2024-01-15",
    "notes": "Weekly grocery shopping",
}

E2E_PORT = 8765


# ─── Backend fixtures ─────────────────────────────────────────────────────────

@pytest.fixture()
def client(tmp_path, mocker):
    """
    FastAPI TestClient with:
    - Isolated SQLite DB in a temp directory (wiped after each test)
    - Isolated uploads directory
    - VLM mocked so no real API calls are made
    """
    mocker.patch("database.DB_PATH", str(tmp_path / "test.db"))

    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    mocker.patch("main.UPLOAD_DIR", upload_dir)

    # Patch where analyze_receipt is *used* (imported into main), not where it lives
    mocker.patch("main.analyze_receipt", return_value=FAKE_RECEIPT.copy())

    import main
    with TestClient(main.app) as c:
        yield c


# ─── E2E fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def live_server(tmp_path_factory):
    """
    Starts a real uvicorn server once per session for Playwright tests.
    VLM is mocked — no OpenRouter API key needed.
    """
    db_path = str(tmp_path_factory.mktemp("e2e_db") / "test.db")
    upload_dir = Path(tmp_path_factory.mktemp("e2e_uploads"))

    with mock_patch("database.DB_PATH", db_path), \
         mock_patch("main.UPLOAD_DIR", upload_dir), \
         mock_patch("main.analyze_receipt", return_value=FAKE_RECEIPT.copy()):

        import database
        database.init_db()

        import uvicorn
        import main
        config = uvicorn.Config(main.app, host="127.0.0.1", port=E2E_PORT, log_level="error")
        server = uvicorn.Server(config)
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()

        # Wait until the server is ready to accept requests
        import httpx
        for _ in range(30):
            try:
                httpx.get(f"http://127.0.0.1:{E2E_PORT}/api/expenses", timeout=1)
                break
            except Exception:
                time.sleep(0.1)

        yield f"http://127.0.0.1:{E2E_PORT}"

        server.should_exit = True
        time.sleep(0.2)


@pytest.fixture()
def receipt_file(tmp_path):
    """Writes TEST_IMAGE to a temp file — used by Playwright's set_input_files."""
    path = tmp_path / "receipt.png"
    path.write_bytes(TEST_IMAGE)
    return path
