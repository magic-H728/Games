// ============ 通用工具函数 ============

const TOKEN_KEY = 'hide_and_seek_token';
const ROLE_KEY = 'hide_and_seek_role';
const PLAYER_ID_KEY = 'hide_and_seek_player_id';
const GAME_PLAYER_ID_KEY = 'hide_and_seek_game_player_id';

// Token management
function getToken() {
    return localStorage.getItem(TOKEN_KEY);
}

function setToken(token, role, playerId, gamePlayerId) {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(ROLE_KEY, role);
    if (playerId) localStorage.setItem(PLAYER_ID_KEY, playerId);
    if (gamePlayerId) localStorage.setItem(GAME_PLAYER_ID_KEY, gamePlayerId);
}

function clearToken() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(ROLE_KEY);
    localStorage.removeItem(PLAYER_ID_KEY);
    localStorage.removeItem(GAME_PLAYER_ID_KEY);
}

function getRole() {
    return localStorage.getItem(ROLE_KEY);
}

// API request helper
async function api(url, options = {}) {
    const token = getToken();
    const headers = {
        'Content-Type': 'application/json',
        ...(options.headers || {})
    };
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(url, {
        ...options,
        headers
    });

    if (response.status === 401) {
        clearToken();
        const role = getRole();
        window.location.href = role === 'STAFF' ? '/staff/login' : '/player/login';
        return null;
    }

    return response;
}

async function apiGet(url) {
    const response = await api(url);
    if (!response) return null;
    if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: '请求失败' }));
        throw new Error(err.detail || '请求失败');
    }
    return response.json();
}

async function apiPost(url, data = {}) {
    const response = await api(url, {
        method: 'POST',
        body: JSON.stringify(data)
    });
    if (!response) return null;
    if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: '请求失败' }));
        throw new Error(err.detail || '请求失败');
    }
    return response.json();
}

async function apiPut(url, data = {}) {
    const response = await api(url, {
        method: 'PUT',
        body: JSON.stringify(data)
    });
    if (!response) return null;
    if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: '请求失败' }));
        throw new Error(err.detail || '请求失败');
    }
    return response.json();
}

async function apiDelete(url) {
    const response = await api(url, {
        method: 'DELETE'
    });
    if (!response) return null;
    if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: '请求失败' }));
        throw new Error(err.detail || '请求失败');
    }
    return response.json();
}

// Toast notification
function showToast(message, type = 'info') {
    const existing = document.querySelector('.toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.style.cssText = `
        position: fixed;
        top: 20px;
        left: 50%;
        transform: translateX(-50%);
        padding: 12px 24px;
        border-radius: 10px;
        font-size: 14px;
        font-weight: 600;
        z-index: 9999;
        animation: slideDown 0.3s ease;
        max-width: 90%;
        text-align: center;
    `;

    if (type === 'success') {
        toast.style.background = '#d4edda';
        toast.style.color = '#155724';
    } else if (type === 'error') {
        toast.style.background = '#f8d7da';
        toast.style.color = '#721c24';
    } else if (type === 'warning') {
        toast.style.background = '#fff3cd';
        toast.style.color = '#856404';
    } else {
        toast.style.background = '#cce5ff';
        toast.style.color = '#004085';
    }

    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => toast.remove(), 3000);
}

// Confirm dialog
function showConfirm(title, message) {
    return new Promise((resolve) => {
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        overlay.innerHTML = `
            <div class="modal">
                <div class="modal-title">${title}</div>
                <p style="font-size: 14px; color: #666; line-height: 1.6;">${message}</p>
                <div class="modal-actions">
                    <button class="btn btn-sm" style="background: #f0f0f0; color: #666;" id="confirm-cancel">取消</button>
                    <button class="btn btn-sm btn-primary" id="confirm-ok">确认</button>
                </div>
            </div>
        `;
        document.body.appendChild(overlay);

        overlay.querySelector('#confirm-cancel').onclick = () => {
            overlay.remove();
            resolve(false);
        };
        overlay.querySelector('#confirm-ok').onclick = () => {
            overlay.remove();
            resolve(true);
        };
    });
}

// Status display helpers
function getStatusBadge(status) {
    const map = {
        'WAITING': '<span class="badge badge-waiting">等待中</span>',
        'ALIVE': '<span class="badge badge-alive">🟢 存活</span>',
        'DEAD': '<span class="badge badge-dead">🔴 已阵亡</span>',
        'PROTECTED': '<span class="badge badge-protected">🛡️ 保护中</span>',
        'OFFLINE': '<span class="badge badge-waiting">⚪ 离线</span>'
    };
    return map[status] || status;
}

function getRoleBadge(role) {
    if (role === 'CAT') return '<span class="badge badge-cat">🐱 猫</span>';
    if (role === 'MOUSE') return '<span class="badge badge-mouse">🐭 鼠</span>';
    return '<span class="badge badge-waiting">未分配</span>';
}

function formatTime(seconds) {
    if (!seconds || seconds <= 0) return '0分0秒';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}分${secs}秒`;
}

function formatDateTime(isoString) {
    if (!isoString) return '-';
    const d = new Date(isoString);
    return d.toLocaleString('zh-CN');
}

// Add CSS animation
const style = document.createElement('style');
style.textContent = `
    @keyframes slideDown {
        from { transform: translateX(-50%) translateY(-20px); opacity: 0; }
        to { transform: translateX(-50%) translateY(0); opacity: 1; }
    }
`;
document.head.appendChild(style);
