/**
 * dashboard.js — Pulse / AIOps Sentinel Dashboard Web Application
 * Features: Hash Router, Chart.js Analytics, Kanban Drag & Drop, Sortable/Paginated Table, Ctrl+K Palette
 */

// State Management
const appState = {
  activeRoute: "overview",
  theme: localStorage.getItem("sentinel_theme") || "dark",
  sidebarCollapsed: localStorage.getItem("sentinel_sidebar") === "true",
  charts: {},
  table: {
    data: [],
    search: "",
    roleFilter: "all",
    sortCol: "name",
    sortAsc: true,
    page: 1,
    pageSize: 6
  },
  kanban: {
    backlog: [
      { id: "INC-101", title: "Investigate latency spike on server-01", sev: "warning", host: "server-01", time: "10m ago" },
      { id: "INC-102", title: "Review memory growth trend in worker pool", sev: "info", host: "server-03", time: "25m ago" }
    ],
    investigating: [
      { id: "INC-98", title: "Cascading 504 gateway timeout investigation", sev: "critical", host: "server-02", time: "1h ago" }
    ],
    mitigating: [
      { id: "INC-95", title: "Rate limit incoming SYN flood on port 443", sev: "critical", host: "gateway-edge", time: "2h ago" }
    ],
    resolved: [
      { id: "INC-88", title: "Disk buffer saturated on database node", sev: "warning", host: "server-03", time: "5h ago" }
    ]
  }
};

document.addEventListener("DOMContentLoaded", () => {
  if (window.lucide) window.lucide.createIcons();
  
  initTheme();
  initSidebar();
  initRouter();
  initCommandPalette();
  initOverviewCharts();
  initUserTableData();
  initKanbanDragDrop();
  initLiveTelemetrySimulation();
});

/* ──────────────────────────────────────────────────────────────
   1. Theme Management (Dark / Light)
   ────────────────────────────────────────────────────────────── */
function initTheme() {
  document.documentElement.setAttribute("data-theme", appState.theme);
  const themeToggle = document.getElementById("theme-toggle-btn");
  if (themeToggle) {
    themeToggle.addEventListener("click", () => {
      appState.theme = appState.theme === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", appState.theme);
      localStorage.setItem("sentinel_theme", appState.theme);
      showToast(`Switched to ${appState.theme} mode`, "info");
      updateChartTheme();
    });
  }
}

function updateChartTheme() {
  const isDark = appState.theme === "dark";
  const gridColor = isDark ? "rgba(255, 255, 255, 0.05)" : "rgba(0, 0, 0, 0.06)";
  const textColor = isDark ? "#64748b" : "#94a3b8";

  Object.values(appState.charts).forEach(chart => {
    if (chart && chart.options && chart.options.scales) {
      if (chart.options.scales.x) {
        chart.options.scales.x.grid.color = gridColor;
        chart.options.scales.x.ticks.color = textColor;
      }
      if (chart.options.scales.y) {
        chart.options.scales.y.grid.color = gridColor;
        chart.options.scales.y.ticks.color = textColor;
      }
      chart.update();
    }
  });
}

/* ──────────────────────────────────────────────────────────────
   2. Sidebar Collapse Toggle
   ────────────────────────────────────────────────────────────── */
function initSidebar() {
  const sidebar = document.getElementById("app-sidebar");
  const toggleBtn = document.getElementById("sidebar-toggle");

  if (appState.sidebarCollapsed && sidebar) {
    sidebar.classList.add("collapsed");
  }

  if (toggleBtn && sidebar) {
    toggleBtn.addEventListener("click", () => {
      sidebar.classList.toggle("collapsed");
      appState.sidebarCollapsed = sidebar.classList.contains("collapsed");
      localStorage.setItem("sentinel_sidebar", appState.sidebarCollapsed);
    });
  }
}

/* ──────────────────────────────────────────────────────────────
   3. Hash-Routed Dynamic Views
   ────────────────────────────────────────────────────────────── */
function initRouter() {
  function handleRoute() {
    const hash = window.location.hash.replace("#", "") || "overview";
    appState.activeRoute = hash;

    // Update active nav link
    document.querySelectorAll(".sidebar-menu .nav-item").forEach(item => {
      const link = item.querySelector("a");
      if (link && link.getAttribute("href") === `#${hash}`) {
        item.classList.add("active");
      } else {
        item.classList.remove("active");
      }
    });

    // Switch view container
    document.querySelectorAll(".page-view").forEach(view => {
      view.classList.toggle("active", view.id === `view-${hash}`);
    });

    if (hash === "users") renderUserTable();
    if (hash === "projects") renderKanbanBoard();
  }

  window.addEventListener("hashchange", handleRoute);
  handleRoute();
}

/* ──────────────────────────────────────────────────────────────
   4. Command Palette (Ctrl + K)
   ────────────────────────────────────────────────────────────── */
function initCommandPalette() {
  const backdrop = document.getElementById("command-palette-backdrop");
  const searchInput = document.getElementById("palette-search");
  const openTriggers = document.querySelectorAll(".topbar-search, [data-command-palette]");

  function openPalette() {
    backdrop.classList.add("open");
    setTimeout(() => searchInput.focus(), 50);
  }

  function closePalette() {
    backdrop.classList.remove("open");
    if (searchInput) searchInput.value = "";
  }

  openTriggers.forEach(el => el.addEventListener("click", openPalette));

  window.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      if (backdrop.classList.contains("open")) closePalette();
      else openPalette();
    }
    if (e.key === "Escape" && backdrop.classList.contains("open")) {
      closePalette();
    }
  });

  if (backdrop) {
    backdrop.addEventListener("click", (e) => {
      if (e.target === backdrop) closePalette();
    });
  }

  // Quick navigation items inside palette
  const paletteItems = document.querySelectorAll(".palette-item");
  paletteItems.forEach(item => {
    item.addEventListener("click", () => {
      const route = item.dataset.route;
      const action = item.dataset.action;
      if (route) {
        window.location.hash = route;
        closePalette();
      } else if (action === "inject_cpu") {
        closePalette();
        simulateIncident("CPU Saturation Spike", "server-01");
      } else if (action === "export_csv") {
        closePalette();
        showToast("Telemetry export generated (CSV)", "success");
      }
    });
  });
}

/* ──────────────────────────────────────────────────────────────
   5. Overview Charts & Sparklines
   ────────────────────────────────────────────────────────────── */
function initOverviewCharts() {
  // Main Telemetry Stream Line Chart
  const lineCtx = document.getElementById("chart-telemetry-main");
  if (lineCtx) {
    const labels = [];
    const cpuData = [];
    const memData = [];
    for (let i = 20; i >= 0; i--) {
      labels.push(`${i * 10}s ago`);
      cpuData.push(38 + Math.random() * 14);
      memData.push(52 + Math.random() * 8);
    }

    appState.charts.telemetry = new Chart(lineCtx.getContext("2d"), {
      type: "line",
      data: {
        labels: labels,
        datasets: [
          {
            label: "CPU Usage %",
            data: cpuData,
            borderColor: "#00f2fe",
            backgroundColor: "rgba(0, 242, 254, 0.08)",
            borderWidth: 2,
            tension: 0.35,
            fill: true
          },
          {
            label: "Memory Usage %",
            data: memData,
            borderColor: "#7928ca",
            backgroundColor: "rgba(121, 40, 202, 0.08)",
            borderWidth: 2,
            tension: 0.35,
            fill: true
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        scales: {
          x: { grid: { color: "rgba(255, 255, 255, 0.05)" }, ticks: { color: "#64748b" } },
          y: { grid: { color: "rgba(255, 255, 255, 0.05)" }, ticks: { color: "#64748b" } }
        },
        plugins: {
          legend: { labels: { color: "#94a3b8" } }
        }
      }
    });
  }

  // Doughnut Chart: Anomaly Severity Distribution
  const donutCtx = document.getElementById("chart-anomalies-donut");
  if (donutCtx) {
    appState.charts.donut = new Chart(donutCtx.getContext("2d"), {
      type: "doughnut",
      data: {
        labels: ["Normal (96.4%)", "Warning (2.8%)", "Critical (0.8%)"],
        datasets: [{
          data: [964, 28, 8],
          backgroundColor: ["#10b981", "#f59e0b", "#ef4444"],
          borderWidth: 0
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: "bottom", labels: { color: "#94a3b8" } }
        }
      }
    });
  }
}

/* ──────────────────────────────────────────────────────────────
   6. Live Mock Ingestion & Activity Feed
   ────────────────────────────────────────────────────────────── */
function initLiveTelemetrySimulation() {
  const feed = document.getElementById("live-activity-feed");
  if (!feed) return;

  const events = [
    { text: "server-01 healthy, IsolationForest score: +0.084", type: "info" },
    { text: "Auto-rebalancing telemetry buffer across cluster", type: "info" },
    { text: "Telemetry checkpoint synced to database (54 features)", type: "success" },
    { text: "Minor jitter detected on server-03 (latency: 68ms)", type: "warning" }
  ];

  setInterval(() => {
    const randomEvent = events[Math.floor(Math.random() * events.length)];
    const timeStr = new Date().toLocaleTimeString();

    const item = document.createElement("div");
    item.className = "activity-item";
    item.innerHTML = `
      <span class="activity-time">${timeStr}</span>
      <span class="activity-text">${randomEvent.text}</span>
    `;

    feed.prepend(item);
    if (feed.children.length > 6) {
      feed.removeChild(feed.lastChild);
    }

    // Push new point to line chart
    if (appState.charts.telemetry) {
      const chart = appState.charts.telemetry;
      chart.data.labels.push("now");
      chart.data.datasets[0].data.push(38 + Math.random() * 15);
      chart.data.datasets[1].data.push(52 + Math.random() * 8);

      if (chart.data.labels.length > 20) {
        chart.data.labels.shift();
        chart.data.datasets[0].data.shift();
        chart.data.datasets[1].data.shift();
      }
      chart.update("none");
    }
  }, 3500);
}

/* ──────────────────────────────────────────────────────────────
   7. Sortable, Filterable, Paginated User Table
   ────────────────────────────────────────────────────────────── */
function initUserTableData() {
  const roles = ["SRE Lead", "DevOps Engineer", "Cloud Architect", "Security Analyst", "Systems Admin"];
  const statuses = ["active", "active", "offline", "warning"];

  // Seed 25 realistic mock operator profiles
  for (let i = 1; i <= 25; i++) {
    appState.table.data.push({
      id: `USR-${1000 + i}`,
      name: ["Alex Turner", "Sarah Jenkins", "Michael Chang", "Elena Rostova", "David Kim", "Priya Patel"][i % 6] + ` #${i}`,
      email: `operator.${i}@sentinel.ops`,
      role: roles[i % roles.length],
      status: statuses[i % statuses.length],
      lastActive: `${i * 3 + 2}m ago`
    });
  }

  // Setup search & filter listeners
  const searchInput = document.getElementById("table-user-search");
  const roleSelect = document.getElementById("table-role-filter");

  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      appState.table.search = e.target.value.toLowerCase();
      appState.table.page = 1;
      renderUserTable();
    });
  }

  if (roleSelect) {
    roleSelect.addEventListener("change", (e) => {
      appState.table.roleFilter = e.target.value;
      appState.table.page = 1;
      renderUserTable();
    });
  }
}

function renderUserTable() {
  const tbody = document.getElementById("users-table-tbody");
  const paginationContainer = document.getElementById("table-pagination-controls");
  if (!tbody) return;

  // Filter
  let filtered = appState.table.data.filter(u => {
    const matchesSearch = u.name.toLowerCase().includes(appState.table.search) || u.email.toLowerCase().includes(appState.table.search);
    const matchesRole = appState.table.roleFilter === "all" || u.role === appState.table.roleFilter;
    return matchesSearch && matchesRole;
  });

  // Sort
  filtered.sort((a, b) => {
    const col = appState.table.sortCol;
    return appState.table.sortAsc ? a[col].localeCompare(b[col]) : b[col].localeCompare(a[col]);
  });

  // Paginate
  const totalPages = Math.ceil(filtered.length / appState.table.pageSize) || 1;
  const startIdx = (appState.table.page - 1) * appState.table.pageSize;
  const pagedData = filtered.slice(startIdx, startIdx + appState.table.pageSize);

  tbody.innerHTML = pagedData.map(u => `
    <tr>
      <td><code>${u.id}</code></td>
      <td><strong>${u.name}</strong></td>
      <td>${u.email}</td>
      <td><span class="user-role-tag">${u.role}</span></td>
      <td><span class="status-pill ${u.status}">${u.status}</span></td>
      <td>${u.lastActive}</td>
      <td><button class="table-action-btn" onclick="showToast('Profile opened: ${u.name}', 'info')">View</button></td>
    </tr>
  `).join("");

  // Pagination buttons
  if (paginationContainer) {
    paginationContainer.innerHTML = `
      <span>Showing ${startIdx + 1} - ${Math.min(startIdx + appState.table.pageSize, filtered.length)} of ${filtered.length}</span>
      <div class="pagination-btn-group">
        <button class="page-btn" ${appState.table.page <= 1 ? "disabled" : ""} onclick="changeUserPage(${appState.table.page - 1})">Prev</button>
        <span class="page-current">Page ${appState.table.page} of ${totalPages}</span>
        <button class="page-btn" ${appState.table.page >= totalPages ? "disabled" : ""} onclick="changeUserPage(${appState.table.page + 1})">Next</button>
      </div>
    `;
  }
}

window.changeUserPage = function (newPage) {
  appState.table.page = newPage;
  renderUserTable();
};

/* ──────────────────────────────────────────────────────────────
   8. Kanban Board Drag & Drop (HTML5 Standard)
   ────────────────────────────────────────────────────────────── */
function initKanbanDragDrop() {
  renderKanbanBoard();
}

function renderKanbanBoard() {
  const columns = ["backlog", "investigating", "mitigating", "resolved"];

  columns.forEach(col => {
    const track = document.getElementById(`kanban-track-${col}`);
    if (!track) return;

    const items = appState.kanban[col] || [];
    track.innerHTML = items.map(item => `
      <div class="kanban-card" draggable="true" data-id="${item.id}" data-col="${col}">
        <div class="kanban-card-title">${item.title}</div>
        <div class="kanban-card-meta">
          <span class="severity-badge ${item.sev}">${item.sev}</span>
          <span>${item.host}</span>
          <span>${item.time}</span>
        </div>
      </div>
    `).join("");

    // Setup drag events
    track.querySelectorAll(".kanban-card").forEach(card => {
      card.addEventListener("dragstart", (e) => {
        card.classList.add("dragging");
        e.dataTransfer.setData("text/plain", JSON.stringify({
          id: card.dataset.id,
          sourceCol: card.dataset.col
        }));
      });

      card.addEventListener("dragend", () => {
        card.classList.remove("dragging");
      });
    });

    // Dropzone listeners
    track.addEventListener("dragover", (e) => {
      e.preventDefault();
      track.classList.add("drag-over");
    });

    track.addEventListener("dragleave", () => {
      track.classList.remove("drag-over");
    });

    track.addEventListener("drop", (e) => {
      e.preventDefault();
      track.classList.remove("drag-over");
      const dragData = JSON.parse(e.dataTransfer.getData("text/plain"));
      moveKanbanCard(dragData.id, dragData.sourceCol, col);
    });
  });
}

function moveKanbanCard(cardId, fromCol, toCol) {
  if (fromCol === toCol) return;

  const cardIndex = appState.kanban[fromCol].findIndex(c => c.id === cardId);
  if (cardIndex > -1) {
    const [movedCard] = appState.kanban[fromCol].splice(cardIndex, 1);
    appState.kanban[toCol].push(movedCard);
    renderKanbanBoard();
    showToast(`Moved ${cardId} to ${toCol.toUpperCase()}`, "success");
  }
}

/* ──────────────────────────────────────────────────────────────
   9. Toast Notification System
   ────────────────────────────────────────────────────────────── */
function showToast(message, type = "info") {
  let container = document.getElementById("toast-container");
  if (!container) {
    container = document.createElement("div");
    container.id = "toast-container";
    container.className = "toast-container";
    document.body.appendChild(container);
  }

  const toast = document.createElement("div");
  toast.className = `toast-msg toast-${type}`;
  toast.innerHTML = `
    <span>${message}</span>
  `;

  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    setTimeout(() => toast.remove(), 300);
  }, 3200);
}

window.showToast = showToast;

function simulateIncident(name, host) {
  showToast(`⚠️ Anomaly Injected: ${name} on ${host}`, "warning");
  appState.kanban.investigating.unshift({
    id: `INC-${Math.floor(Math.random() * 800 + 100)}`,
    title: `${name} detected via Isolation Forest`,
    sev: "critical",
    host: host,
    time: "Just now"
  });
  renderKanbanBoard();
}
