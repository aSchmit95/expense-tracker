import base64
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles

from config import UPLOAD_PASSWORD
from database import add_expense, delete_expense, get_expenses, get_stats, init_db
from vlm import analyze_receipt

load_dotenv()

app = FastAPI(title="Expense Tracker")

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


@app.on_event("startup")
async def startup():
    init_db()


@app.post("/api/upload")
async def upload_receipt(
    file: UploadFile = File(...),
    x_upload_password: str = Header(default=""),
):
    if UPLOAD_PASSWORD and x_upload_password != UPLOAD_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid password.")
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. Use JPEG, PNG, or WebP.",
        )

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10 MB limit
        raise HTTPException(status_code=400, detail="File too large (max 10 MB).")

    # Save file to disk
    ext = Path(file.filename or "receipt.jpg").suffix or ".jpg"
    filename = f"{uuid.uuid4()}{ext}"
    filepath = UPLOAD_DIR / filename
    filepath.write_bytes(content)

    # Analyze with VLM
    try:
        image_b64 = base64.b64encode(content).decode()
        result = analyze_receipt(image_b64)
    except Exception as exc:
        filepath.unlink(missing_ok=True)  # Clean up orphaned file
        raise HTTPException(status_code=502, detail=f"VLM analysis failed: {exc}")

    # Persist to database
    expense = add_expense(
        amount=result["amount"],
        merchant=result["merchant"],
        category=result["category"],
        date=result["date"],
        image_path=str(filepath),
        notes=result["notes"],
    )
    return expense


@app.get("/api/expenses")
def list_expenses():
    return get_expenses()


@app.delete("/api/expenses/{expense_id}")
def remove_expense(expense_id: int):
    if not delete_expense(expense_id):
        raise HTTPException(status_code=404, detail="Expense not found.")
    return {"ok": True}


@app.get("/api/stats")
def stats():
    return get_stats()


# Serve uploaded images
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Serve the frontend — must be last so API routes take priority
app.mount("/", StaticFiles(directory="static", html=True), name="static")
