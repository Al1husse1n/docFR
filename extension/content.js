// content.js - Robust extractor with Swagger/OpenAPI detection

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.action !== 'extractData') return;

    // ⏳ Wait for full page load (important for React apps)
    const waitForPage = () => {
        return new Promise((resolve) => {
            if (document.readyState === "complete") {
                resolve();
            } else {
                window.addEventListener("load", () => resolve(), { once: true });
            }
        });
    };

    // 🧠 Detect if page is documentation
    const detectDocs = (text, url) => {
        const keywords = [
            "api", "endpoint", "request", "response",
            "authorization", "header", "json", "curl"
        ];

        const lower = text.toLowerCase();
        const score = keywords.filter(k => lower.includes(k)).length;

        return score >= 3 || url.toLowerCase().includes("docs");
    };

    // 🧠 Detect Swagger/OpenAPI UI
    const detectSwagger = () => {
        const html = document.documentElement.innerHTML.toLowerCase();

        return (
            html.includes("swagger-ui") ||
            html.includes("swaggeruibundle") ||
            html.includes("openapi") ||
            html.includes("redoc")
        );
    };

    // 🔥 Extract OpenAPI JSON URL (hidden or embedded)
    const extractOpenAPIUrl = () => {
        let foundUrl = null;

        // 1️⃣ Scan script tags (most reliable)
        const scripts = Array.from(document.querySelectorAll("script"));

        for (const script of scripts) {
            const text = script.innerText;

            let match = text.match(/url:\s*["']([^"']+)["']/);
            if (match) {
                foundUrl = match[1];
                break;
            }

            match = text.match(/configUrl:\s*["']([^"']+)["']/);
            if (match) {
                foundUrl = match[1];
                break;
            }
        }

        // 2️⃣ Try Swagger UI global config
        try {
            if (window.ui && typeof window.ui.getConfigs === "function") {
                const config = window.ui.getConfigs();
                if (config?.url) {
                    foundUrl = config.url;
                }
            }
        } catch (e) {}

        // 3️⃣ Look for links containing schema hints
        if (!foundUrl) {
            const links = Array.from(document.querySelectorAll("a[href]"));
            const link = links.find(a =>
                a.href.includes("openapi") ||
                a.href.includes("swagger") ||
                a.href.includes("api-docs") ||
                a.href.includes(".json")
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

    // 🧠 Extract main page content
    const extractMainContent = () => {
        const main =
            document.querySelector('main') ||
            document.querySelector('article') ||
            document.body;

        let text = main.innerText || '';

        text = text.replace(/\s+/g, ' ').trim();

        // Limit for LLM safety
        const MAX_LENGTH = 5000;
        if (text.length > MAX_LENGTH) {
            text = text.slice(0, MAX_LENGTH) + '...';
        }

        return text;
    };

    // 🔗 Extract links
    const extractLinks = () => {
        let links = Array.from(document.querySelectorAll('a[href]'))
            .map(a => a.href)
            .filter(href =>
                href &&
                (href.startsWith('http://') || href.startsWith('https://'))
            );

        return [...new Set(links)].slice(0, 100);
    };

    // 🧱 Extract headings
    const extractHeadings = () => {
        return Array.from(document.querySelectorAll('h1, h2, h3'))
            .map(h => h.innerText.trim())
            .filter(Boolean)
            .slice(0, 30);
    };

    // 💻 Extract code blocks
    const extractCodeBlocks = () => {
        return Array.from(document.querySelectorAll('pre, code'))
            .map(c => c.innerText.trim())
            .filter(text => text.length > 0 && text.length < 1000)
            .slice(0, 30);
    };

    // 🚀 Main execution
    const extractData = async () => {
        await waitForPage();

        const url = window.location.href;
        const title = document.title || 'Untitled Page';

        const content = extractMainContent();
        const headings = extractHeadings();
        const code_blocks = extractCodeBlocks();
        const links = extractLinks();

        const is_docs = detectDocs(content, url);
        const is_openapi = detectSwagger();

        let found_hidden_json_url = null;
        let is_json_hidden = false;

        if (is_openapi) {
            found_hidden_json_url = extractOpenAPIUrl();

            if (found_hidden_json_url) {
                is_json_hidden = true;
            }
        }

        // ✅ Final structured output (STRICTLY aligned with backend)
        const data = {
            url,
            title,

            content,
            headings: headings || [],
            code_blocks: code_blocks || [],
            links: links || [],

            is_docs: !!is_docs,
            is_openapi: !!is_openapi,
            is_json_hidden: !!is_json_hidden,

            found_hidden_json_url: found_hidden_json_url || null,
            openapi_url: found_hidden_json_url || null,

            endpoints: [],
            examples: []
        };

        sendResponse(data);
    };

    extractData();
    return true; // required for async
});