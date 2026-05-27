/* ═══════════════════════════════════════════
   Wiki-LLM — App Logic
   ═══════════════════════════════════════════ */

// ─── State ───
let ws = null;
let isAgentBusy = false;
let currentFiles = [];
let currentKBFiles = [];
let activeFileItem = null;

// ─── DOM refs ───
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const statusDot = $('#statusDot');
const statusText = $('#statusText');
const messages = $('#messages');
const messageInput = $('#messageInput');
const sendBtn = $('#sendBtn');
const welcomeCard = $('#welcomeCard');

// Tabs
const tabBtns = $$('.tab-btn');
const tabPanels = $$('.tab-panel');
const tabIndicator = $('#tabIndicator');

// Files
const filesList = $('#filesList');
const fileSearchInput = $('#fileSearchInput');
const fileViewerName = $('#fileViewerName');
const fileViewerMeta = $('#fileViewerMeta');
const fileViewerContent = $('#fileViewerContent');
const refreshFilesBtn = $('#refreshFilesBtn');

// KB
const kbGrid = $('#kbGrid');
const kbSearchInput = $('#kbSearchInput');
const kbFileCount = $('#kbFileCount');
const kbLastUpdated = $('#kbLastUpdated');
const refreshKBBtn = $('#refreshKBBtn');
const kbModalOverlay = $('#kbModalOverlay');
const kbModalTitle = $('#kbModalTitle');
const kbModalBody = $('#kbModalBody');
const kbModalClose = $('#kbModalClose');

// ═══════════════════════════════════════════
// TAB SYSTEM
// ═══════════════════════════════════════════
const TAB_PANEL_MAP = { chat: 'panelChat', files: 'panelFiles', kb: 'panelKB' };

function initTabs() {
  updateIndicator($('.tab-btn.active'));
  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      tabBtns.forEach(b => b.classList.remove('active'));
      tabPanels.forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      const panelId = TAB_PANEL_MAP[btn.dataset.tab];
      const panel = panelId ? $(`#${panelId}`) : null;
      if (panel) panel.classList.add('active');
      updateIndicator(btn);
      // Load data on tab switch
      if (btn.dataset.tab === 'files') loadFiles();
      if (btn.dataset.tab === 'kb') loadKB();
    });
  });
}

function updateIndicator(activeBtn) {
  if (!activeBtn || !tabIndicator) return;
  tabIndicator.style.left = activeBtn.offsetLeft + 'px';
  tabIndicator.style.width = activeBtn.offsetWidth + 'px';
}

// ═══════════════════════════════════════════
// WEBSOCKET
// ═══════════════════════════════════════════
function connectWS() {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(`${proto}//${location.host}/ws`);

  ws.onopen = () => {
    statusDot.className = 'status-dot connected';
    statusText.textContent = 'Connected';
  };

  ws.onclose = () => {
    statusDot.className = 'status-dot error';
    statusText.textContent = 'Disconnected';
    setTimeout(connectWS, 3000);
  };

  ws.onerror = () => {
    statusDot.className = 'status-dot error';
    statusText.textContent = 'Error';
  };

  ws.onmessage = (e) => {
    try {
      const event = JSON.parse(e.data);
      handleEvent(event);
    } catch (err) {
      console.error('WS parse error:', err);
    }
  };
}

function handleEvent(event) {
  switch (event.type) {
    case 'thinking':
      addMessage('thinking', event.content);
      break;
    case 'tool_call':
      addMessage('tool', event.content);
      break;
    case 'tool_result':
      addMessage('tool-result', event.content);
      break;
    case 'answer':
      addMessage('agent', event.content);
      break;
    case 'error':
      if (event.content === 'RESOURCE_EXHAUSTED') {
        // Extract user input before resetting
        let lastInput = '';
        const userMsgs = $$('.msg-user .msg-bubble');
        if (userMsgs.length > 0) {
          lastInput = userMsgs[userMsgs.length - 1].textContent;
        }
        
        // Execute new session to clear thinking cards, messages, and reset WS
        newSession();
        
        // Show specific error toast
        showToast('API Quota Exceeded. Session reset.');
        
        // Restore user input
        if (lastInput) {
          messageInput.value = lastInput;
          messageInput.style.height = 'auto';
          messageInput.style.height = Math.min(messageInput.scrollHeight, 120) + 'px';
        }
      } else {
        addMessage('error', event.content);
      }
      break;
    case 'done':
      setAgentBusy(false);
      break;
  }
}

// ═══════════════════════════════════════════
// CHAT MESSAGES
// ═══════════════════════════════════════════
function addMessage(type, content) {
  if (welcomeCard) welcomeCard.style.display = 'none';

  const wrapper = document.createElement('div');
  wrapper.className = `msg msg-${type}`;

  const labels = {
    'user': 'You',
    'agent': 'Agent',
    'thinking': 'Thinking',
    'tool': 'Tool Call',
    'tool-result': 'Result',
    'error': 'Error'
  };

  const label = document.createElement('div');
  label.className = 'msg-label';
  label.textContent = labels[type] || type;

  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble';

  if (type === 'agent') {
    bubble.innerHTML = renderMarkdown(content);
  } else if (type === 'thinking') {
    bubble.innerHTML = `<div class="typing-dots"><span></span><span></span><span></span></div> ${escapeHtml(content)}`;
  } else {
    bubble.textContent = content;
  }

  wrapper.appendChild(label);
  wrapper.appendChild(bubble);
  messages.appendChild(wrapper);
  messages.scrollTop = messages.scrollHeight;
}

function sendMessage() {
  const text = messageInput.value.trim();
  if (!text || isAgentBusy || !ws || ws.readyState !== WebSocket.OPEN) return;

  addMessage('user', text);
  ws.send(JSON.stringify({ message: text }));
  messageInput.value = '';
  messageInput.style.height = 'auto';
  setAgentBusy(true);
}

function sendExample(text) {
  messageInput.value = text;
  sendMessage();
}
// Expose globally for onclick handlers
window.sendExample = sendExample;

function setAgentBusy(busy) {
  isAgentBusy = busy;
  sendBtn.disabled = busy;
}

function newSession() {
  // Clear chat messages
  messages.innerHTML = '';
  // Restore welcome card
  if (welcomeCard) {
    welcomeCard.style.display = '';
    messages.appendChild(welcomeCard);
  }
  // Close and reconnect WebSocket to reset server-side history
  if (ws) {
    ws.onclose = null; // prevent auto-reconnect loop
    ws.close();
  }
  setAgentBusy(false);
  connectWS();
  showToast('New session started');
}

// ═══════════════════════════════════════════
// WIKI FILES TAB (Read Only)
// ═══════════════════════════════════════════
async function loadFiles() {
  try {
    const res = await fetch('/api/wiki');
    const data = await res.json();
    currentFiles = data.files || [];
    renderFilesList(currentFiles);
  } catch (err) {
    filesList.innerHTML = `<div class="files-empty">Failed to load files</div>`;
  }
}

function renderFilesList(files) {
  if (!files.length) {
    filesList.innerHTML = `<div class="files-empty">No wiki files found</div>`;
    return;
  }
  filesList.innerHTML = files.map(f => `
    <div class="file-item" data-name="${escapeAttr(f.name)}" onclick="selectFile('${escapeAttr(f.name)}', this)">
      <div class="file-item-icon">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
      </div>
      <div class="file-item-info">
        <div class="file-item-name">${escapeHtml(f.name)}</div>
        <div class="file-item-meta">${formatSize(f.size_bytes)} · ${formatDate(f.modified)}</div>
      </div>
    </div>
  `).join('');
}

async function selectFile(name, el) {
  // Highlight active
  $$('.file-item').forEach(i => i.classList.remove('active'));
  if (el) el.classList.add('active');

  fileViewerName.textContent = name;
  fileViewerContent.innerHTML = `<div class="kb-loading"><div class="spinner"></div><p>Loading…</p></div>`;

  try {
    const res = await fetch(`/api/wiki/${encodeURIComponent(name)}`);
    const data = await res.json();
    fileViewerMeta.textContent = `${data.lines} lines`;
    fileViewerContent.innerHTML = renderMarkdown(data.content);
  } catch (err) {
    fileViewerContent.innerHTML = `<div class="empty-state"><p>Failed to load file</p></div>`;
  }
}
window.selectFile = selectFile;

// ═══════════════════════════════════════════
// KNOWLEDGE BASE TAB
// ═══════════════════════════════════════════
async function loadKB() {
  kbGrid.innerHTML = `<div class="kb-loading"><div class="spinner"></div><p>Loading knowledge base…</p></div>`;

  try {
    const res = await fetch('/api/wiki');
    const data = await res.json();
    currentKBFiles = data.files || [];
    kbFileCount.textContent = currentKBFiles.length;

    if (currentKBFiles.length) {
      const latest = currentKBFiles.reduce((a, b) => new Date(a.modified) > new Date(b.modified) ? a : b);
      kbLastUpdated.textContent = formatDate(latest.modified);
    }

    // Fetch previews for all files
    const previews = await Promise.all(
      currentKBFiles.map(async (f) => {
        try {
          const r = await fetch(`/api/wiki/${encodeURIComponent(f.name)}`);
          const d = await r.json();
          return { ...f, content: d.content || '' };
        } catch { return { ...f, content: '' }; }
      })
    );

    currentKBFiles = previews;
    renderKBGrid(currentKBFiles);
  } catch (err) {
    kbGrid.innerHTML = `<div class="kb-loading"><p>Failed to load knowledge base</p></div>`;
  }
}

function renderKBGrid(files) {
  if (!files.length) {
    kbGrid.innerHTML = `<div class="kb-loading"><p>No articles in knowledge base</p></div>`;
    return;
  }
  kbGrid.innerHTML = files.map(f => {
    const title = f.name.replace(/\.md$/, '').replace(/_/g, ' ');
    const preview = getPreview(f.content, 150);
    const tags = extractTags(f.content);
    return `
      <div class="kb-card" onclick="openKBArticle('${escapeAttr(f.name)}')">
        <div class="kb-card-title">${escapeHtml(title)}</div>
        <div class="kb-card-preview">${escapeHtml(preview)}</div>
        <div class="kb-card-footer">
          <span>${formatSize(f.size_bytes)}</span>
          <div class="kb-card-tags">
            ${tags.slice(0, 3).map(t => `<span class="kb-tag">${escapeHtml(t)}</span>`).join('')}
          </div>
        </div>
      </div>
    `;
  }).join('');
}

async function openKBArticle(name) {
  const cached = currentKBFiles.find(f => f.name === name);
  kbModalTitle.textContent = name.replace(/\.md$/, '').replace(/_/g, ' ');

  if (cached && cached.content) {
    kbModalBody.innerHTML = renderMarkdown(cached.content);
  } else {
    kbModalBody.innerHTML = `<div class="kb-loading"><div class="spinner"></div></div>`;
    try {
      const res = await fetch(`/api/wiki/${encodeURIComponent(name)}`);
      const data = await res.json();
      kbModalBody.innerHTML = renderMarkdown(data.content);
    } catch {
      kbModalBody.innerHTML = `<p>Failed to load article.</p>`;
    }
  }
  kbModalOverlay.classList.add('open');
}
window.openKBArticle = openKBArticle;

function closeKBModal() {
  kbModalOverlay.classList.remove('open');
}

// ═══════════════════════════════════════════
// UTILITIES
// ═══════════════════════════════════════════
function renderMarkdown(text) {
  if (!text) return '';
  try {
    if (typeof marked !== 'undefined') {
      marked.setOptions({
        highlight: function(code, lang) {
          if (typeof hljs !== 'undefined' && lang && hljs.getLanguage(lang)) {
            return hljs.highlight(code, { language: lang }).value;
          }
          return code;
        },
        breaks: true
      });
      return marked.parse(text);
    }
  } catch (e) { /* fall through */ }
  return escapeHtml(text).replace(/\n/g, '<br>');
}

function escapeHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function escapeAttr(str) {
  return str.replace(/'/g, "\\'").replace(/"/g, '&quot;');
}

function formatSize(bytes) {
  if (!bytes) return '0 B';
  if (bytes < 1024) return bytes + ' B';
  return (bytes / 1024).toFixed(1) + ' KB';
}

function formatDate(iso) {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  } catch { return iso; }
}

function getPreview(content, maxLen) {
  if (!content) return '';
  // Strip headers and markdown artifacts
  const clean = content
    .replace(/^#{1,6}\s+.*$/gm, '')
    .replace(/\*\*|__|~~|`/g, '')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/\[\[([^\]]+)\]\]/g, '$1')
    .trim();
  const lines = clean.split('\n').filter(l => l.trim().length > 10);
  const text = lines.slice(0, 5).join(' ').trim();
  return text.length > maxLen ? text.slice(0, maxLen) + '…' : text;
}

function extractTags(content) {
  if (!content) return [];
  // Try to find Tags: line
  const match = content.match(/Tags?:\s*([^\n]+)/i);
  if (match) {
    return match[1].split(/[,|;]/).map(t => t.replace(/[\[\]*#]/g, '').trim()).filter(Boolean).slice(0, 4);
  }
  // Fallback: get first heading words
  const h1 = content.match(/^#\s+(.+)/m);
  if (h1) return [h1[1].split(' ').slice(0, 2).join(' ')];
  return [];
}

function showToast(msg) {
  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.textContent = msg;
  $('#toastContainer').appendChild(toast);
  setTimeout(() => toast.remove(), 3000);
}

// ═══════════════════════════════════════════
// EVENT LISTENERS
// ═══════════════════════════════════════════
function init() {
  initTabs();
  connectWS();

  // New session button
  $('#newSessionBtn').addEventListener('click', newSession);

  // Chat input
  sendBtn.addEventListener('click', sendMessage);
  messageInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });
  messageInput.addEventListener('input', () => {
    messageInput.style.height = 'auto';
    messageInput.style.height = Math.min(messageInput.scrollHeight, 120) + 'px';
  });

  // Files tab
  refreshFilesBtn.addEventListener('click', loadFiles);
  fileSearchInput.addEventListener('input', () => {
    const q = fileSearchInput.value.toLowerCase();
    const filtered = currentFiles.filter(f => f.name.toLowerCase().includes(q));
    renderFilesList(filtered);
  });

  // KB tab
  refreshKBBtn.addEventListener('click', loadKB);
  kbSearchInput.addEventListener('input', () => {
    const q = kbSearchInput.value.toLowerCase();
    const filtered = currentKBFiles.filter(f =>
      f.name.toLowerCase().includes(q) ||
      (f.content && f.content.toLowerCase().includes(q))
    );
    renderKBGrid(filtered);
  });

  // KB Modal
  kbModalClose.addEventListener('click', closeKBModal);
  kbModalOverlay.addEventListener('click', (e) => {
    if (e.target === kbModalOverlay) closeKBModal();
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && kbModalOverlay.classList.contains('open')) closeKBModal();
  });

  // Window resize -> update tab indicator
  window.addEventListener('resize', () => updateIndicator($('.tab-btn.active')));
}

document.addEventListener('DOMContentLoaded', init);
