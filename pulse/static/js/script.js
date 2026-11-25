/**
 * script.js — PULSE global frontend utilities
 * Loaded on every page via base.html
 */

/* ── Sidebar toggle (mobile) ─────────────────────────────── */
const menuToggle   = document.getElementById('menu-toggle');
const sidebar      = document.getElementById('sidebar');
const sidebarOverlay = document.getElementById('sidebar-overlay');

if (menuToggle) {
  menuToggle.addEventListener('click', toggleSidebar);
}

function toggleSidebar() {
  if (!sidebar) return;
  const isOpen = sidebar.classList.contains('open');
  if (isOpen) {
    closeSidebar();
  } else {
    sidebar.classList.add('open');
    if (sidebarOverlay) sidebarOverlay.style.display = 'block';
  }
}

function closeSidebar() {
  if (sidebar) sidebar.classList.remove('open');
  if (sidebarOverlay) sidebarOverlay.style.display = 'none';
}

/* ── Toast notifications ─────────────────────────────────── */
function showToast(message, type = 'info', duration = 3500) {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;

  // Icon
  const icons = { success: '✓', error: '✕', warning: '⚠', info: 'ℹ' };
  toast.innerHTML = `<span>${icons[type] || 'ℹ'}</span><span>${escHtml(String(message))}</span>`;

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(20px)';
    toast.style.transition = 'all .3s ease';
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

/* ── Global loader ───────────────────────────────────────── */
function showGlobalLoader(text = 'Working on it…') {
  const loader = document.getElementById('global-loader');
  const loaderText = document.getElementById('loader-text');
  if (loader) {
    if (loaderText) loaderText.textContent = text;
    loader.classList.remove('hidden');
  }
}

function hideGlobalLoader() {
  const loader = document.getElementById('global-loader');
  if (loader) loader.classList.add('hidden');
}

/* ── Modal helpers ───────────────────────────────────────── */
function openModal(id) {
  const modal = document.getElementById(id);
  if (modal) {
    modal.classList.remove('hidden');
    // Focus first input
    const firstInput = modal.querySelector('input, textarea, select');
    if (firstInput) setTimeout(() => firstInput.focus(), 100);
  }
}

function closeModal(id) {
  const modal = document.getElementById(id);
  if (modal) modal.classList.add('hidden');
}

// Close modal on overlay click
document.addEventListener('click', e => {
  if (e.target.classList.contains('modal-overlay')) {
    e.target.classList.add('hidden');
  }
});

// Close modal on Escape key
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal-overlay:not(.hidden)').forEach(m => m.classList.add('hidden'));
  }
});

/* ── HTML escape ─────────────────────────────────────────── */
function escHtml(str) {
  if (typeof str !== 'string') str = String(str ?? '');
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/* ── Date formatter ──────────────────────────────────────── */
function formatDate(dateStr) {
  if (!dateStr) return '';
  try {
    const d = new Date(dateStr);
    if (isNaN(d)) return dateStr.slice(0, 10);
    const now = new Date();
    const diffMs = now - d;
    const diffDays = Math.floor(diffMs / 86400000);
    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return `${diffDays}d ago`;
    if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`;
    return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
  } catch {
    return dateStr.slice(0, 10);
  }
}

/* ── Nav badge updater ───────────────────────────────────── */
function updateNavBadges() {
  // Update article count badge in sidebar
  fetch('/api/articles?limit=1')
    .then(r => r.json())
    .then(data => {
      const badge = document.getElementById('nav-article-count');
      if (badge && data.total !== undefined) badge.textContent = data.total;
    })
    .catch(() => {});

  fetch('/api/ideas')
    .then(r => r.json())
    .then(data => {
      const badge = document.getElementById('nav-idea-count');
      if (badge && data.ideas) badge.textContent = data.ideas.length;
    })
    .catch(() => {});

  fetch('/api/drafts')
    .then(r => r.json())
    .then(data => {
      const badge = document.getElementById('nav-draft-count');
      if (badge && data.drafts) badge.textContent = data.drafts.length;
    })
    .catch(() => {});
}

// Update badges on every page load
document.addEventListener('DOMContentLoaded', updateNavBadges);

/* ── Keyboard shortcut: Ctrl+S to save (editor page) ─────── */
document.addEventListener('keydown', e => {
  if ((e.ctrlKey || e.metaKey) && e.key === 's') {
    // Only trigger on the editor page
    const saveBtn = document.querySelector('[onclick="saveDraft()"]');
    if (saveBtn) {
      e.preventDefault();
      if (typeof saveDraft === 'function') saveDraft();
    }
  }
});
