// background.js - Service Worker (Manifest V3)
// Handles all communication + backend API call

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    // 1. Get page data from content script
    if (message.action === 'getPageData') { //Popup → background.js → content script → background.js → popup
        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
            if (!tabs || tabs.length === 0) {
                sendResponse({ error: 'No active tab found' });
                return;
            }

            const tabId = tabs[0].id;

            // Forward request to content script on current tab
            chrome.tabs.sendMessage(tabId, { action: 'extractData' }, (response) => {
                if (chrome.runtime.lastError || !response) {
                    sendResponse({ 
                        error: 'Content script not ready. Please refresh the page.' 
                    });
                    return;
                }
                sendResponse(response);
            });
        });
        
        return true; // Required for async sendResponse
    }

    // 2. Send question + page data to your FastAPI backend
    if (message.action === 'askQuestion') { //Popup → background.js → FastAPI → background.js → popup
        const { question, url, title, content, links } = message;

        // POST to your local FastAPI endpoint[](http://localhost:8000/ask)
        fetch('http://localhost:8000/ask', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify({
                question: question,
                url: url,
                title: title,
                content: content,
                links: links
            })
        })
        .then(async (res) => {
            if (!res.ok) {
                const text = await res.text();
                throw new Error(`Backend error ${res.status}: ${text}`);
            }
            return res.json();
        })
        .then((apiData) => {
            // Backend can return { answer: "..." } or { response: "..." } or plain text
            const answer = apiData.answer || 
                          apiData.response || 
                          apiData.message || 
                          JSON.stringify(apiData);
            
            sendResponse({ answer: answer });
        })
        .catch((err) => {
            console.error('Backend fetch error:', err);
            sendResponse({ 
                error: `Backend connection failed. Is FastAPI running on localhost:8000?<br><br>${err.message}` 
            });
        });

        return true; // Required for async sendResponse
    }
});