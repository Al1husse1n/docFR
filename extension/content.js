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

    // 🧠 Detect if the page itself IS a raw OpenAPI JSON file
    const detectRawOpenApiJson = () => {
        // Check content type
        const contentType = document.contentType || '';
        const isJsonContentType = contentType.includes('application/json');
        
        // Check URL patterns for JSON files
        const url = window.location.href;
        const isJsonUrl = url.includes('.json') || 
                         url.includes('openapi') || 
                         url.includes('swagger');
        
        // Try to parse body as JSON
        try {
            const bodyText = document.body.innerText || '';
            const jsonContent = JSON.parse(bodyText);
            
            // Check if parsed JSON is OpenAPI/Swagger
            if (jsonContent.openapi || jsonContent.swagger || 
                (jsonContent.paths && jsonContent.info)) {
                return { isRawJson: true, content: jsonContent };
            }
        } catch (e) {
            // Not valid JSON
        }
        
        return { isRawJson: isJsonContentType && isJsonUrl, content: null };
    };

    // 🧠 Detect Swagger/OpenAPI UI (HTML pages, not raw JSON)
    const detectSwaggerUI = () => {
        const html = document.documentElement.innerHTML.toLowerCase();

        return (
            html.includes("swagger-ui") ||
            html.includes("swaggeruibundle") ||
            html.includes("redoc")
        );
    };

    // 🔥 Extract OpenAPI JSON URL from Swagger UI pages (hidden in scripts)
    const extractOpenAPIUrlFromUI = () => {
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

    // 🧠 Extract main page content (for non-JSON pages)
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
        
        // Check if this page IS a raw OpenAPI JSON file
        const { isRawJson, content: jsonContent } = detectRawOpenApiJson();
        
        let openapi_schema = null;
        let is_openapi = false;
        let is_json_hidden = false;
        let found_hidden_json_url = null;
        let schema_source = null;
        let content = '';
        let headings = [];
        let code_blocks = [];
        let links = [];
        let is_docs = false;
        
        if (isRawJson && jsonContent) {
            // Page IS a raw OpenAPI JSON file
            openapi_schema = jsonContent;
            is_openapi = true;
            is_json_hidden = false;  // NOT hidden - it's the actual JSON file
            schema_source = "raw_json_file";
            content = JSON.stringify(openapi_schema, null, 2).slice(0, 5000);
            is_docs = true;
            console.log("✅ Direct raw OpenAPI JSON file detected");
        } else {
            // Page is HTML - check if it's Swagger UI
            const has_swagger_ui = detectSwaggerUI();
            
            if (has_swagger_ui) {
                is_openapi = true;
                is_json_hidden = true;  // TRUE because it's hidden in UI, not raw JSON
                found_hidden_json_url = extractOpenAPIUrlFromUI();
                
                if (found_hidden_json_url) {
                    schema_source = "swagger_ui_with_url";
                    console.log(`✅ Swagger UI detected, found hidden JSON URL: ${found_hidden_json_url}`);
                } else {
                    schema_source = "swagger_ui_no_url";
                    console.log("⚠️ Swagger UI detected but no JSON URL found");
                }
                
                // Extract page content for context
                content = extractMainContent();
                headings = extractHeadings();
                code_blocks = extractCodeBlocks();
                links = extractLinks();
                is_docs = detectDocs(content, url);
            } else {
                // Regular webpage
                is_openapi = false;
                is_json_hidden = false;
                found_hidden_json_url = null;
                schema_source = null;
                content = extractMainContent();
                headings = extractHeadings();
                code_blocks = extractCodeBlocks();
                links = extractLinks();
                is_docs = detectDocs(content, url);
            }
        }

        // ✅ Final structured output
        const data = {
            url,
            title,
            content,
            headings: headings || [],
            code_blocks: code_blocks || [],
            links: links || [],
            is_docs: !!is_docs,
            is_openapi: !!is_openapi,
            is_json_hidden: is_json_hidden,  // TRUE when OpenAPI is found in HTML UI (not raw JSON)
            found_hidden_json_url: found_hidden_json_url || null,
            openapi_schema: openapi_schema,  // Actual JSON only for raw JSON files
            schema_source: schema_source,
            endpoints: [],
            examples: []
        };

        console.log("📤 Sending data to background:", {
            is_openapi: data.is_openapi,
            is_json_hidden: data.is_json_hidden,
            has_openapi_schema: !!data.openapi_schema,
            found_hidden_json_url: data.found_hidden_json_url,
            schema_source: data.schema_source
        });
        
        sendResponse(data);
    };

    extractData();
    return true; // required for async
});