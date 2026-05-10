// ===== RESIFIX API HANDLER =====
const API_BASE = 'http://127.0.0.1:5000/api';

// ===== SESSION HELPERS =====
function getUser() {
  const u = localStorage.getItem('resifix_user');
  return u ? JSON.parse(u) : null;
}

function setUser(user) {
  localStorage.setItem('resifix_user', JSON.stringify(user));
}

function logout() {
  localStorage.removeItem('resifix_user');
  window.location.href = '../login.html';
}

function requireAuth(allowedRoles) {
  const user = getUser();
  if (!user) { window.location.href = '../login.html'; return null; }
  if (allowedRoles && !allowedRoles.includes(user.role)) {
    window.location.href = '../login.html'; return null;
  }
  return user;
}

function requireAuthRoot(allowedRoles) {
  const user = getUser();
  if (!user) { window.location.href = 'login.html'; return null; }
  if (allowedRoles && !allowedRoles.includes(user.role)) {
    window.location.href = 'login.html'; return null;
  }
  return user;
}

// ===== API CALLS =====
async function apiPost(endpoint, data) {
  try {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return await res.json();
  } catch (e) {
    return { success: false, message: 'Cannot connect to server. Make sure the backend is running.' };
  }
}

async function apiGet(endpoint) {
  try {
    const res = await fetch(`${API_BASE}${endpoint}`);
    return await res.json();
  } catch (e) {
    return { success: false, message: 'Cannot connect to server.' };
  }
}

async function apiPut(endpoint, data) {
  try {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return await res.json();
  } catch (e) {
    return { success: false, message: 'Cannot connect to server.' };
  }
}

async function apiPostForm(endpoint, formData) {
  try {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      method: 'POST',
      body: formData
    });
    return await res.json();
  } catch (e) {
    return { success: false, message: 'Cannot connect to server.' };
  }
}

// ===== AUTH =====
async function register(data) { return await apiPost('/register', data); }
async function login(email, password) {
  return await apiPost('/login', { email, password });
}

// ===== ISSUES =====
async function submitIssue(formData) {
  return await apiPostForm('/issues/submit', formData);
}

async function getIssues(role, userId, block) {
  let url = `/issues?role=${role}`;
  if (userId) url += `&user_id=${userId}`;
  if (block) url += `&block=${encodeURIComponent(block)}`;
  return await apiGet(url);
}

async function updateIssueStatus(issueId, status) {
  return await apiPut(`/issues/${issueId}/status`, { status });
}

// ===== PROPOSALS =====
async function generateProposals(block) {
  return await apiPost('/proposals/generate', { block });
}

async function getProposals(block) {
  let url = '/proposals';
  if (block) url += `?block=${encodeURIComponent(block)}`;
  return await apiGet(url);
}

async function voteOnProposal(proposalId, studentId, voteType, comment) {
  return await apiPost(`/proposals/${proposalId}/vote`, {
    student_id: studentId,
    vote_type: voteType,
    comment: comment
  });
}

async function reviseProposal(proposalId) {
  return await apiPost(`/proposals/${proposalId}/revise`, {});
}

// ===== NOTIFICATIONS =====
async function getNotifications(userId) {
  return await apiGet(`/notifications/${userId}`);
}

// ===== REPORTS =====
async function getWeeklyReport() {
  return await apiGet('/reports/weekly');
}

// ===== UI HELPERS =====
function getPriorityBadge(priority) {
  const map = {
    'Critical': 'badge-critical',
    'High': 'badge-high',
    'Medium': 'badge-medium',
    'Low': 'badge-low'
  };
  return `<span class="badge ${map[priority] || 'badge-low'}">${priority}</span>`;
}

function getStatusBadge(status) {
  const map = {
    'Open': 'badge-open',
    'In Progress': 'badge-progress',
    'Resolved': 'badge-resolved'
  };
  return `<span class="badge ${map[status] || 'badge-open'}">${status}</span>`;
}

function getTypeBadge(type) {
  const map = {
    'Electrical': 'badge-electrical',
    'Plumbing': 'badge-plumbing',
    'Structural': 'badge-structural',
    'Hygiene & Safety': 'badge-hygiene',
    'Administrative': 'badge-admin'
  };
  return `<span class="badge ${map[type] || 'badge-admin'}">${type}</span>`;
}

function showAlert(id, message, type) {
  const el = document.getElementById(id);
  if (!el) return;
  el.className = `alert alert-${type} show`;
  el.textContent = message;
  setTimeout(() => { el.className = 'alert'; }, 4000);
}

function formatDate(dateStr) {
  if (!dateStr) return 'N/A';
  return new Date(dateStr).toLocaleDateString('en-ZA', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
}

function setTopbarUser(user) {
  const el = document.getElementById('topbar-user-name');
  const av = document.getElementById('topbar-avatar');
  if (el) el.textContent = `${user.full_name} — ${user.block || user.role}`;
  if (av) av.textContent = user.full_name.charAt(0).toUpperCase();
}

async function loadNotifCount(userId) {
  const res = await getNotifications(userId);
  if (res.success && res.unread_count > 0) {
    const el = document.getElementById('notif-count');
    if (el) {
      el.textContent = res.unread_count;
      el.style.display = 'inline';
    }
  }
}
