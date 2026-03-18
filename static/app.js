// ─── Constants ───────────────────────────────────────────────────────────────

const CATEGORY_COLORS = {
  "Groceries":        "#4CAF50",
  "Dining Out":       "#FF9800",
  "Transport":        "#2196F3",
  "Health & Pharmacy":"#E91E63",
  "Entertainment":    "#9C27B0",
  "Clothing":         "#00BCD4",
  "Home & Garden":    "#795548",
  "Technology":       "#607D8B",
  "Travel":           "#FF5722",
  "Other":            "#9E9E9E",
};

// ─── State ────────────────────────────────────────────────────────────────────

let allExpenses = [];
let statsChart  = null;

// ─── Init ─────────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  setupUploadArea();
  loadExpenses();
  loadStats();
  document.getElementById("category-filter").addEventListener("change", renderTable);
});

// ─── Upload area ──────────────────────────────────────────────────────────────

function setupUploadArea() {
  const area  = document.getElementById("upload-area");
  const input = document.getElementById("file-input");

  area.addEventListener("click", () => input.click());

  input.addEventListener("change", () => {
    if (input.files[0]) handleFile(input.files[0]);
  });

  area.addEventListener("dragover", (e) => {
    e.preventDefault();
    area.classList.add("dragover");
  });

  area.addEventListener("dragleave", () => area.classList.remove("dragover"));

  area.addEventListener("drop", (e) => {
    e.preventDefault();
    area.classList.remove("dragover");
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  });
}

function handleFile(file) {
  // Show image preview
  const reader = new FileReader();
  reader.onload = (e) => {
    const img = document.getElementById("preview-img");
    img.src = e.target.result;
    document.getElementById("preview-container").classList.remove("d-none");
  };
  reader.readAsDataURL(file);

  uploadFile(file);
}

async function uploadFile(file) {
  setUploadState("loading");

  const formData = new FormData();
  formData.append("file", file);

  const password = document.getElementById("upload-password").value;

  try {
    const res = await fetch("/api/upload", {
      method: "POST",
      headers: { "x-upload-password": password },
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Unknown error" }));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }

    const expense = await res.json();
    setUploadState("success", `${expense.merchant} · ${formatCurrency(expense.amount)} · ${expense.category}`);
    await loadExpenses();
    await loadStats();
  } catch (err) {
    setUploadState("error", err.message);
  }
}

function setUploadState(state, message = "") {
  const status  = document.getElementById("upload-status");
  const result  = document.getElementById("upload-result");
  const error   = document.getElementById("upload-error");

  status.classList.add("d-none");
  result.classList.add("d-none");
  error.classList.add("d-none");

  if (state === "loading") {
    status.classList.remove("d-none");
  } else if (state === "success") {
    document.getElementById("result-text").textContent = message;
    result.classList.remove("d-none");
  } else if (state === "error") {
    document.getElementById("error-text").textContent = message;
    error.classList.remove("d-none");
  }
}

// ─── Expenses list ────────────────────────────────────────────────────────────

async function loadExpenses() {
  try {
    const res = await fetch("/api/expenses");
    allExpenses = await res.json();
    populateCategoryFilter();
    renderTable();
  } catch (err) {
    console.error("Failed to load expenses:", err);
  }
}

function populateCategoryFilter() {
  const select = document.getElementById("category-filter");
  const current = select.value;
  const categories = [...new Set(allExpenses.map((e) => e.category))].sort();

  // Rebuild options
  select.innerHTML = '<option value="">All categories</option>';
  categories.forEach((cat) => {
    const opt = document.createElement("option");
    opt.value = cat;
    opt.textContent = cat;
    if (cat === current) opt.selected = true;
    select.appendChild(opt);
  });
}

function renderTable() {
  const filter   = document.getElementById("category-filter").value;
  const tbody    = document.getElementById("expenses-body");
  const emptyRow = document.getElementById("empty-row");

  const filtered = filter
    ? allExpenses.filter((e) => e.category === filter)
    : allExpenses;

  // Update total badge
  const total = filtered.reduce((sum, e) => sum + e.amount, 0);
  document.getElementById("total-badge").textContent = formatCurrency(total);

  // Clear existing rows (keep empty-row as template)
  tbody.querySelectorAll("tr:not(#empty-row)").forEach((r) => r.remove());

  if (filtered.length === 0) {
    emptyRow.classList.remove("d-none");
    return;
  }

  emptyRow.classList.add("d-none");

  filtered.forEach((expense) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>
        ${expense.image_path
          ? `<img src="/${expense.image_path}" class="receipt-thumb" alt="receipt"
               data-src="/${expense.image_path}" />`
          : `<span class="text-muted">—</span>`}
      </td>
      <td class="fw-semibold">${escapeHtml(expense.merchant || "—")}</td>
      <td class="text-muted small">${expense.date || "—"}</td>
      <td>${categoryBadge(expense.category)}</td>
      <td class="text-muted small">${escapeHtml(expense.notes || "")}</td>
      <td class="text-end fw-bold">${formatCurrency(expense.amount)}</td>
      <td>
        <button class="btn btn-sm btn-outline-danger" data-id="${expense.id}" title="Delete">
          <i class="bi bi-trash"></i>
        </button>
      </td>
    `;

    // Open image modal on thumbnail click
    const thumb = tr.querySelector(".receipt-thumb");
    if (thumb) {
      thumb.addEventListener("click", () => openImageModal(thumb.dataset.src));
    }

    // Delete button
    tr.querySelector("[data-id]").addEventListener("click", (e) => {
      deleteExpense(parseInt(e.currentTarget.dataset.id));
    });

    tbody.appendChild(tr);
  });
}

async function deleteExpense(id) {
  if (!confirm("Delete this expense?")) return;
  try {
    await fetch(`/api/expenses/${id}`, { method: "DELETE" });
    await loadExpenses();
    await loadStats();
  } catch (err) {
    alert("Could not delete expense.");
  }
}

// ─── Stats chart ──────────────────────────────────────────────────────────────

async function loadStats() {
  try {
    const res  = await fetch("/api/stats");
    const data = await res.json();
    renderStats(data);
  } catch (err) {
    console.error("Failed to load stats:", err);
  }
}

function renderStats(stats) {
  const canvas = document.getElementById("stats-chart");
  const list   = document.getElementById("stats-list");

  if (stats.length === 0) {
    list.innerHTML = '<p class="text-muted text-center">No data yet.</p>';
    if (statsChart) { statsChart.destroy(); statsChart = null; }
    return;
  }

  const labels = stats.map((s) => s.category);
  const totals = stats.map((s) => s.total);
  const colors = labels.map((l) => CATEGORY_COLORS[l] || "#9E9E9E");

  if (statsChart) statsChart.destroy();

  statsChart = new Chart(canvas, {
    type: "doughnut",
    data: {
      labels,
      datasets: [{ data: totals, backgroundColor: colors, borderWidth: 2 }],
    },
    options: {
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => ` ${formatCurrency(ctx.parsed)}`,
          },
        },
      },
    },
  });

  // Text list below chart
  list.innerHTML = stats
    .map(
      (s) => `
      <div class="d-flex justify-content-between align-items-center mb-1">
        <span>
          <span class="badge me-1" style="background:${CATEGORY_COLORS[s.category] || "#9E9E9E"}">
            &nbsp;
          </span>
          ${escapeHtml(s.category)}
          <span class="text-muted">(${s.count})</span>
        </span>
        <strong>${formatCurrency(s.total)}</strong>
      </div>`
    )
    .join("");
}

// ─── Image modal ──────────────────────────────────────────────────────────────

function openImageModal(src) {
  document.getElementById("modal-img").src = src;
  new bootstrap.Modal(document.getElementById("imageModal")).show();
}

// ─── Utilities ────────────────────────────────────────────────────────────────

function formatCurrency(amount) {
  return new Intl.NumberFormat("de-DE", {
    style: "currency",
    currency: "EUR",
  }).format(amount);
}

function categoryBadge(category) {
  const color = CATEGORY_COLORS[category] || "#9E9E9E";
  return `<span class="badge" style="background-color:${color}">${escapeHtml(category)}</span>`;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}
