// content.js - Advanced extractor with Swagger/OpenAPI detection

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.action === 'extractData') {

        const waitForPage = () => {
            return new Promise((resolve) => {
                if (document.readyState === "complete") {
                    resolve();
                } else {
                    window.addEventListener("load", () => resolve());
                }
            });
        };

        // 🧠 Detect if page is documentation
        const detectDocs = (text, url) => {
            const keywords = ["api", "endpoint", "request", "response", "curl", "json"];
            const score = keywords.filter(k => text.toLowerCase().includes(k)).length;

            return score >= 3 || url.includes("docs");
        };

        // 🧠 Detect Swagger/OpenAPI presence
        const detectSwagger = () => {
            const html = document.documentElement.innerHTML.toLowerCase();

            return (
                html.includes("swagger") ||
                html.includes("openapi") ||
                html.includes("swaggeruibundle")
            );
        };

        // 🔥 Extract OpenAPI URL (even if hidden)
        const extractOpenAPIUrl = () => {
            let foundUrl = null;

            // 1️⃣ Try script tags (BEST METHOD)
            const scripts = Array.from(document.querySelectorAll("script"));

            for (const script of scripts) {
                const text = script.innerText;

                // Match: url: "..."
                let match = text.match(/url:\s*["']([^"']+)["']/);
                if (match) {
                    foundUrl = match[1];
                    break;
                }

                // Match: configUrl: "..."
                match = text.match(/configUrl:\s*["']([^"']+)["']/);
                if (match) {
                    foundUrl = match[1];
                    break;
                }
            }

            // 2️⃣ Try global Swagger config
            try {
                if (window.ui && window.ui.getConfigs) {
                    const config = window.ui.getConfigs();
                    if (config?.url) {
                        foundUrl = config.url;
                    }
                }
            } catch (e) {}

            // 3️⃣ Try anchor links
            if (!foundUrl) {
                const links = Array.from(document.querySelectorAll("a"));
                const link = links.find(a =>
                    a.href.includes("openapi") ||
                    a.href.includes("swagger") ||
                    a.href.includes("api-docs")
                );

                if (link) {
                    foundUrl = link.href;
                }
            }

            // 4️⃣ Normalize relative URLs
            if (foundUrl) {
                try {
                    foundUrl = new URL(foundUrl, window.location.origin).href;
                } catch (e) {}
            }

            return foundUrl;
        };

        const extractData = async () => {
            await waitForPage();

            const url = window.location.href;
            const title = document.title || 'Untitled Page';

            let mainContentEl =
                document.querySelector('main') ||
                document.querySelector('article') ||
                document.body;

            let content = mainContentEl.innerText || '';

            content = content.replace(/\s+/g, ' ').trim();

            const MAX_CONTENT_LENGTH = 5000;
            if (content.length > MAX_CONTENT_LENGTH) {
                content = content.slice(0, MAX_CONTENT_LENGTH) + '...';
            }

            let links = Array.from(document.querySelectorAll('a[href]'))
                .map(a => a.href)
                .filter(href =>
                    href &&
                    (href.startsWith('http://') || href.startsWith('https://'))
                );

            links = [...new Set(links)].slice(0, 100);

            const headings = Array.from(document.querySelectorAll('h1, h2, h3'))
                .map(h => h.innerText.trim())
                .filter(Boolean)
                .slice(0, 20);

            // 🔥 Extract code blocks (NEW)
            const code_blocks = Array.from(document.querySelectorAll('code, pre'))
                .map(c => c.innerText.trim())
                .filter(Boolean)
                .slice(0, 20);

            // 🧠 Detection
            const is_docs = detectDocs(content, url);
            const is_openapi = detectSwagger();

            // 🔥 Try to extract hidden JSON URL
            let found_hidden_json_url = null;
            let is_json_hidden = false;

            if (is_openapi) {
                found_hidden_json_url = extractOpenAPIUrl();

                if (found_hidden_json_url) {
                    is_json_hidden = true;
                }
            }

            // Final structured response (aligned with your AgentState)
            const data = {
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
                openapi_url: found_hidden_json_url || null,

                endpoints: [], // backend fills
                examples: []   // backend fills
            };

            sendResponse(data);
        };

        extractData();
        return true;
    }
});