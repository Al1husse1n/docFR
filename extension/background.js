// background.js - Service Worker (Manifest V3)
// Handles all communication + backend API call

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    // 1. Get page data from content script
    if (message.action === 'getPageData') {
        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
            if (!tabs || tabs.length === 0) {
                sendResponse({ error: 'No active tab found' });
                return;
            }

            const tabId = tabs[0].id;

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
        
        return true;
    }

    // 2. Send question + page data to your FastAPI backend
    if (message.action === 'askQuestion') {
        const {
            messages,
            url,
            title,
            content,
            headings,
            code_blocks,
            links,
            is_docs,
            is_openapi,
            is_json_hidden,
            found_hidden_json_url,
            openapi_schema,
            schema_source,
            endpoints,
            examples
        } = message;

        // POST to your local FastAPI endpoint
        fetch('http://localhost:8000/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify({
                messages,
                url,
                title,
                content,
                headings,
                code_blocks,
                links,
                is_docs,
                is_openapi,
                is_json_hidden,
                found_hidden_json_url,  // Only populated for Swagger UI pages
                openapi_schema,          // Only populated for raw JSON files
                schema_source,
                endpoints,
                examples
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

        return true;
    }
});