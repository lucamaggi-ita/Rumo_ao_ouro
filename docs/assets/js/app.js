/* ─── app.js — Rumo ao Ouro ──────────────────────────────────────────────────
   Funcionalidades:
   - Dark / light mode  (persistido em localStorage)
   - Mochila panel      (ferramentas organizadas por capítulo)
   - Modo Treino        (fecha/abre todas as soluções)
   - Progresso          (marca capítulos lidos em localStorage)
   - Filtro de ferramentas (nas páginas mochila.html e no painel)
─────────────────────────────────────────────────────────────────────────────── */

// ─── Tema ──────────────────────────────────────────────────────────────────────
function toggleTheme() {
  const root = document.documentElement;
  const isDark = root.getAttribute("data-theme") === "dark";
  const next = isDark ? "light" : "dark";
  root.setAttribute("data-theme", next);
  localStorage.setItem("ruo-theme", next);
  const btn = document.getElementById("btn-theme");
  if (btn) btn.textContent = next === "dark" ? "☀" : "🌙";
}

function applyTheme() {
  const saved = localStorage.getItem("ruo-theme") || "light";
  document.documentElement.setAttribute("data-theme", saved);
  const btn = document.getElementById("btn-theme");
  if (btn) btn.textContent = saved === "dark" ? "☀" : "🌙";
}

// ─── Sidebar (mobile toggle) ──────────────────────────────────────────────────
let sidebarOpen = false;

function toggleSidebar() {
  const sidebar  = document.getElementById("sidebar");
  const overlay  = document.getElementById("sidebar-overlay");
  if (!sidebar) return;
  sidebarOpen = !sidebarOpen;
  sidebar.classList.toggle("sidebar-open", sidebarOpen);
  if (overlay) overlay.classList.toggle("visible", sidebarOpen);
}

// ─── Mochila panel ────────────────────────────────────────────────────────────
let mochilaOpen = false;

function toggleMochila() {
  const panel   = document.getElementById("mochila-panel");
  const overlay = document.getElementById("mochila-overlay");
  if (!panel) return;
  mochilaOpen = !mochilaOpen;
  panel.classList.toggle("open", mochilaOpen);
  panel.setAttribute("aria-hidden", String(!mochilaOpen));
  if (overlay) overlay.classList.toggle("visible", mochilaOpen);
  const btn = document.getElementById("btn-mochila");
  if (btn) btn.classList.toggle("active", mochilaOpen);
  if (mochilaOpen) {
    const search = document.getElementById("mochila-search");
    if (search) setTimeout(() => search.focus(), 80);
  }
}

function renderMochilaPanel(currentChapter) {
  const list = document.getElementById("mochila-list");
  if (!list || typeof MOCHILA_DATA === "undefined") return;

  const progress = getProgress();
  const maxUnlocked = getMaxUnlockedChapter(progress, currentChapter);

  // Agrupar ferramentas por capítulo
  const groups = {};
  for (const [num, info] of Object.entries(MOCHILA_DATA)) {
    const cap = info.chapter;
    if (!groups[cap]) groups[cap] = [];
    groups[cap].push({ num: parseInt(num), desc: info.desc });
  }

  let html = "";
  for (const cap of Object.keys(groups).map(Number).sort((a,b)=>a-b)) {
    const tools = groups[cap].sort((a,b) => a.num - b.num);
    const unlocked = cap <= maxUnlocked;
    const label = cap === currentChapter ? `Cap. ${cap} — atual` : `Cap. ${cap}`;
    html += `<div class="mochila-group-title">${label}</div>`;
    for (const t of tools) {
      const cls = unlocked ? "" : " locked";
      const href = unlocked
        ? `cap${String(cap).padStart(2,"0")}.html#f${t.num}`
        : "#";
      html += `<a class="mochila-tool${cls}" href="${href}" title="Ferramenta ${t.num}">
        <span class="t-n">${t.num}</span>
        <span class="t-d">${escHtml(t.desc)}</span>
      </a>`;
    }
  }
  list.innerHTML = html || "<p style='padding:1rem;color:var(--text-muted)'>Sem dados.</p>";
}

function filterMochila(query) {
  const q = query.toLowerCase().trim();
  const items = document.querySelectorAll("#mochila-list .mochila-tool");
  items.forEach(el => {
    const match = !q || el.textContent.toLowerCase().includes(q);
    el.style.display = match ? "" : "none";
  });
  // Mostrar/ocultar títulos de grupo
  const groups = document.querySelectorAll(".mochila-group-title");
  groups.forEach(g => {
    let sib = g.nextElementSibling;
    let anyVisible = false;
    while (sib && !sib.classList.contains("mochila-group-title")) {
      if (sib.style.display !== "none") anyVisible = true;
      sib = sib.nextElementSibling;
    }
    g.style.display = anyVisible ? "" : "none";
  });
}

// ─── Modo Treino ──────────────────────────────────────────────────────────────
let treinoAtivo = false;

function toggleTreino() {
  treinoAtivo = !treinoAtivo;
  document.body.classList.toggle("treino-ativo", treinoAtivo);
  const btn = document.getElementById("btn-treino");
  if (btn) btn.classList.toggle("active", treinoAtivo);

  // Fechar todas as soluções quando modo treino ativo,
  // abrir todas quando modo treino desativado
  const details = document.querySelectorAll("details.solucao");
  details.forEach(d => {
    d.open = !treinoAtivo;
  });

  localStorage.setItem("ruo-treino", String(treinoAtivo));
}

function applyTreino() {
  const saved = localStorage.getItem("ruo-treino") === "true";
  if (saved) {
    treinoAtivo = false; // toggleTreino irá ativar
    toggleTreino();
  }
}

// ─── Progresso ────────────────────────────────────────────────────────────────
function getProgress() {
  try {
    return JSON.parse(localStorage.getItem("ruo-progress") || "{}");
  } catch { return {}; }
}

function markRead(capNum) {
  const p = getProgress();
  p[capNum] = "lido";
  localStorage.setItem("ruo-progress", JSON.stringify(p));
}

function getMaxUnlockedChapter(progress, currentChapter) {
  const read = Object.keys(progress).map(Number).filter(n => progress[n] === "lido");
  const maxRead = read.length > 0 ? Math.max(...read) : 0;
  return Math.max(maxRead, currentChapter);
}

// Marca capítulo como lido quando o usuário chega ao final da página
function setupReadTracking(capNum) {
  const target = document.querySelector(".chapter-nav");
  if (!target) return;
  const obs = new IntersectionObserver(entries => {
    if (entries[0].isIntersecting) {
      markRead(capNum);
      obs.disconnect();
    }
  }, { threshold: 0.5 });
  obs.observe(target);
}

// ─── Página de capítulo ───────────────────────────────────────────────────────
function initChapter(capNum) {
  applyTheme();
  applyTreino();
  renderMochilaPanel(capNum);
  setupReadTracking(capNum);

  // Abrir soluções por defeito (modo treino desativado = soluções abertas)
  if (!treinoAtivo) {
    document.querySelectorAll("details.solucao").forEach(d => { d.open = true; });
  }
}

// ─── Página índice ────────────────────────────────────────────────────────────
function initIndex() {
  applyTheme();
  const progress = getProgress();
  for (const [cap, estado] of Object.entries(progress)) {
    const item = document.getElementById(`idx-${cap}`);
    if (item && estado === "lido") item.classList.add("lido");
  }
}

// ─── Página Mochila (mochila.html) ───────────────────────────────────────────
function initMochilaPage() {
  applyTheme();
}

function filterTools(query) {
  const q = query.toLowerCase().trim();
  const items = document.querySelectorAll(".tool-item");
  items.forEach(el => {
    const match = !q || el.textContent.toLowerCase().includes(q);
    el.classList.toggle("hidden", !match);
  });
  // Ocultar seções sem ferramentas visíveis
  const secs = document.querySelectorAll(".mochila-sec");
  secs.forEach(sec => {
    const visible = sec.querySelectorAll(".tool-item:not(.hidden)").length > 0;
    sec.style.display = visible ? "" : "none";
  });
}

// ─── Util ─────────────────────────────────────────────────────────────────────
function escHtml(str) {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ─── Atalhos de teclado ────────────────────────────────────────────────────────
document.addEventListener("keydown", e => {
  if (e.key === "Escape" && sidebarOpen) toggleSidebar();
  if (e.key === "Escape" && mochilaOpen) toggleMochila();
  // Seta esq/dir para navegar entre capítulos
  if (e.altKey) {
    if (e.key === "ArrowLeft") {
      const prev = document.querySelector(".nav-prev");
      if (prev) prev.click();
    } else if (e.key === "ArrowRight") {
      const next = document.querySelector(".nav-next");
      if (next) next.click();
    }
  }
});

// Aplicar tema imediatamente (antes do DOMContentLoaded) para evitar flash
applyTheme();
