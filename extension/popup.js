// popup.js - Improved + robust version

let pageData = null;

const chatContainer = document.getElementById('chat-container');
const messageForm = document.getElementById('message-form');
const messageInput = document.getElementById('message-input');
const pageTitleEl = document.getElementById('page-title');

// 🔒 Escape HTML (prevent XSS)
function escapeHTML(str) {
    return str.replace(/[&<>"']/g, (tag) => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    }[tag]));
}

// 💬 Add message to UI
function addMessage(sender, text) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender === 'user' ? 'user' : 'ai'}`;

    const safeText = escapeHTML(text || '');

    messageDiv.innerHTML = safeText
        .replace(/\n/g, '<br>')
        .replace(/```([\s\S]*?)```/g,
            '<pre style="background:#18181b;padding:10px;border-radius:8px;overflow:auto;margin-top:8px;font-size:13px;">$1</pre>'
        );

    chatContainer.appendChild(messageDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;

    saveChat();
}

// 💾 Save chat
function saveChat() {
    chrome.storage.local.set({
        chatHistory: chatContainer.innerHTML
    });
}

// 📂 Load chat
function loadChat() {
    chrome.storage.local.get(['chatHistory'], (res) => {
        if (res.chatHistory) {
            chatContainer.innerHTML = res.chatHistory;
        }
    });
}

// ⏳ Loading indicator
function showLoading() {
    const id = 'loading-' + Date.now();
    const el = document.createElement('div');
    el.id = id;
    el.className = 'message ai';
    el.innerText = "Thinking...";
    chatContainer.appendChild(el);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    return id;
}

function removeLoading(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

// 🌐 Load page data from content.js
function loadPageData() {
    chrome.runtime.sendMessage({ action: 'getPageData' }, (response) => {
        if (!response || response.error) {
            addMessage('AI', '⚠️ Failed to read page. Try refreshing.');
            return;
        }

        // ✅ Ensure structure matches backend expectations
        pageData = {
            url: response.url || '',
            title: response.title || 'Untitled',
            content: response.content || '',
            headings: response.headings || [],
            code_blocks: response.code_blocks || [],
            links: response.links || [],
            is_docs: response.is_docs ?? false,
            is_openapi: response.is_openapi ?? false,
            is_json_hidden: response.is_json_hidden ?? false,
            found_hidden_json_url: response.found_hidden_json_url || null,
            openapi_url: response.openapi_url || null
        };

        pageTitleEl.textContent = pageData.title.slice(0, 40);

        addMessage(
            'AI',
            `Page loaded: ${pageData.title}\n\nDocs: ${pageData.is_docs} | OpenAPI: ${pageData.is_openapi}`
        );
    });
}

// 🚀 Send question
messageForm.addEventListener('submit', (e) => {
    e.preventDefault();

    const question = messageInput.value.trim();

    if (!question) {
        addMessage('AI', '⚠️ Please enter a question.');
        return;
    }

    if (!pageData) {
        addMessage('AI', '⚠️ Page data not ready. Try again.');
        return;
    }

    addMessage('user', question);
    messageInput.value = '';

    const loadingId = showLoading();

    // ⏱️ Timeout protection
    const timeout = setTimeout(() => {
        removeLoading(loadingId);
        addMessage('AI', '⏳ Request timed out. Try again.');
    }, 15000);

    chrome.runtime.sendMessage(
        {
            action: 'askQuestion',
            question,
            ...pageData
        },
        (response) => {
            clearTimeout(timeout);
            removeLoading(loadingId);

            if (!response) {
                addMessage('AI', '❌ No response from extension.');
                return;
            }

            if (response.error) {
                addMessage('AI', `❌ ${response.error}`);
            } else {
                addMessage('AI', response.answer || 'No response.');
            }
        }
    );
});

// 🧠 Init
document.addEventListener('DOMContentLoaded', () => {
    loadChat();
    loadPageData();
});