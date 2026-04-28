// popup.js - Improved version

let pageData = null;

const chatContainer = document.getElementById('chat-container');
const messageForm = document.getElementById('message-form');
const messageInput = document.getElementById('message-input');
const pageTitleEl = document.getElementById('page-title');

// Escape HTML (prevents XSS)
function escapeHTML(str) {
    return str.replace(/[&<>"']/g, (tag) => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    }[tag]));
}

function addMessage(sender, text) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender === 'user' ? 'user' : 'ai'}`;

    const safeText = escapeHTML(text);

    messageDiv.innerHTML = safeText
        .replace(/\n/g, '<br>')
        .replace(/```([\s\S]*?)```/g,
            '<pre style="background:#18181b;padding:10px;border-radius:8px;overflow:auto;margin-top:8px;font-size:13px;">$1</pre>'
        );

    chatContainer.appendChild(messageDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;

    // Save history
    saveChat();
}

function saveChat() {
    chrome.storage.local.set({
        chatHistory: chatContainer.innerHTML
    });
}

function loadChat() {
    chrome.storage.local.get(['chatHistory'], (res) => {
        if (res.chatHistory) {
            chatContainer.innerHTML = res.chatHistory;
        }
    });
}

function showLoading() {
    const id = 'loading-' + Date.now();
    const el = document.createElement('div');
    el.id = id;
    el.innerText = "Thinking...";
    chatContainer.appendChild(el);
    return id;
}

function removeLoading(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

// Load page data
function loadPageData() {
    chrome.runtime.sendMessage({ action: 'getPageData' }, (response) => {
        if (!response || response.error) {
            addMessage('AI', '⚠️ Failed to read page.');
            return;
        }

        pageData = response;
        pageTitleEl.textContent = pageData.title.slice(0, 30);

        addMessage('AI', `Page loaded: ${pageData.title}`);
    });
}

// Send message
messageForm.addEventListener('submit', (e) => {
    e.preventDefault();

    const question = messageInput.value.trim();
    if (!question || !pageData) return;

    addMessage('user', question);
    messageInput.value = '';

    const loadingId = showLoading();

    // Timeout protection
    const timeout = setTimeout(() => {
        removeLoading(loadingId);
        addMessage('AI', '⏳ Request timed out.');
    }, 10000);

    chrome.runtime.sendMessage({
        action: 'askQuestion',
        question,
        ...pageData
    }, (response) => {
        clearTimeout(timeout);
        removeLoading(loadingId);

        if (!response) {
            addMessage('AI', '❌ Error communicating.');
            return;
        }

        if (response.error) {
            addMessage('AI', response.error);
        } else {
            addMessage('AI', response.answer || 'No response.');
        }
    });
});

// Init
document.addEventListener('DOMContentLoaded', () => {
    loadChat();
    loadPageData();
});