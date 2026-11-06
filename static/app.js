// Nomo Web Interface - Vanilla JS

document.addEventListener("DOMContentLoaded", () => {
    const chatForm = document.getElementById("chat-form");
    const promptInput = document.getElementById("prompt-input");
    const sendBtn = document.getElementById("send-btn");
    const chatMessages = document.getElementById("chat-messages");
    
    // Output panel tabs and views
    const tabTable = document.getElementById("tab-table");
    const tabRaw = document.getElementById("tab-raw");
    const tableView = document.getElementById("json-table-view");
    const rawView = document.getElementById("json-raw-view");
    
    // Output content elements
    const tablePlaceholder = document.getElementById("table-placeholder");
    const tableResults = document.getElementById("table-results");
    const jsonTableBody = document.getElementById("json-table-body");
    const jsonRawCode = document.getElementById("json-raw-code");
    const copyJsonBtn = document.getElementById("copy-json-btn");
    const jsonStatusIndicator = document.getElementById("json-status-indicator");

    let currentJsonResponse = null;

    // Tab switching
    tabTable.addEventListener("click", () => {
        tabTable.classList.add("active");
        tabRaw.classList.remove("active");
        tableView.classList.remove("hidden");
        rawView.classList.add("hidden");
    });

    tabRaw.addEventListener("click", () => {
        tabRaw.classList.add("active");
        tabTable.classList.remove("active");
        rawView.classList.remove("hidden");
        tableView.classList.add("hidden");
    });

    // Copy JSON to clipboard
    copyJsonBtn.addEventListener("click", () => {
        if (!currentJsonResponse) return;
        const jsonText = JSON.stringify(currentJsonResponse, null, 2);
        navigator.clipboard.writeText(jsonText).then(() => {
            const originalText = copyJsonBtn.textContent;
            copyJsonBtn.textContent = "Copied!";
            setTimeout(() => {
                copyJsonBtn.textContent = originalText;
            }, 1800);
        });
    });

    // Quick prompt chips
    document.querySelectorAll(".chip").forEach(chip => {
        chip.addEventListener("click", () => {
            const prompt = chip.getAttribute("data-prompt");
            if (prompt) {
                promptInput.value = prompt;
                promptInput.focus();
            }
        });
    });

    // Submit prompt on Enter (Shift+Enter for newline)
    promptInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            chatForm.dispatchEvent(new Event("submit"));
        }
    });

    // Form submit handler
    chatForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const promptText = promptInput.value.trim();
        if (!promptText) return;

        // 1. Add user message to chat window
        appendMessage("user", promptText);
        promptInput.value = "";
        setLoading(true);

        try {
            // 2. Send prompt to FastAPI backend
            const response = await fetch("/api/prompt", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ prompt: promptText })
            });

            if (!response.ok) {
                throw new Error(`Server returned status ${response.status}`);
            }

            const data = await response.json();
            currentJsonResponse = data;

            // 3. Add assistant message to chat window
            const replyText = data.reply || data.message || "Prompt received.";
            appendMessage("assistant", replyText);

            // 4. Render response as JSON Table in the Output Panel
            renderJsonTable(data);

        } catch (error) {
            console.error("Error submitting prompt:", error);
            appendMessage("assistant", `Error: Could not connect to server. (${error.message})`);
        } finally {
            setLoading(false);
        }
    });

    function setLoading(isLoading) {
        sendBtn.disabled = isLoading;
        promptInput.disabled = isLoading;
        if (isLoading) {
            sendBtn.innerHTML = `<span>Thinking...</span>`;
        } else {
            sendBtn.innerHTML = `
                <span>Send</span>
                <svg class="send-icon" viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
                    <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
                </svg>
            `;
            promptInput.focus();
        }
    }

    function appendMessage(sender, text) {
        const msgDiv = document.createElement("div");
        msgDiv.className = `message ${sender}-message`;

        const senderDiv = document.createElement("div");
        senderDiv.className = "message-sender";
        senderDiv.textContent = sender === "user" ? "You" : "Nomo AI";
        msgDiv.appendChild(senderDiv);

        const contentDiv = document.createElement("div");
        contentDiv.className = "message-content";
        contentDiv.textContent = text;
        msgDiv.appendChild(contentDiv);

        chatMessages.appendChild(msgDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function renderJsonTable(data) {
        // Show table container and hide empty placeholder
        tablePlaceholder.classList.add("hidden");
        tableResults.classList.remove("hidden");

        // Clear existing table rows
        jsonTableBody.innerHTML = "";

        // Populate table with keys, types, and values from the JSON response
        Object.keys(data).forEach(key => {
            const val = data[key];
            const type = val === null ? "null" : Array.isArray(val) ? "array" : typeof val;
            let displayVal = "";

            if (val === null) {
                displayVal = `<span class="type-tag">null</span>`;
            } else if (type === "object") {
                displayVal = `<pre style="margin:0; font-family:var(--font-mono); font-size:0.78rem;">${escapeHtml(JSON.stringify(val, null, 2))}</pre>`;
            } else if (type === "array") {
                displayVal = `<span class="table-badge">${val.length} items</span> <pre style="margin:4px 0 0; font-family:var(--font-mono); font-size:0.78rem;">${escapeHtml(JSON.stringify(val, null, 2))}</pre>`;
            } else if (key === "status") {
                const badgeClass = val === "success" ? "success" : "warning";
                displayVal = `<span class="table-badge ${badgeClass}">${escapeHtml(String(val))}</span>`;
            } else {
                displayVal = `<code>${escapeHtml(String(val))}</code>`;
            }

            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td><strong>${escapeHtml(key)}</strong></td>
                <td><span class="type-tag">${type}</span></td>
                <td>${displayVal}</td>
            `;
            jsonTableBody.appendChild(tr);
        });

        // Update Raw JSON view
        jsonRawCode.textContent = JSON.stringify(data, null, 2);
        jsonStatusIndicator.textContent = `Response received (${new Date().toLocaleTimeString()})`;
    }

    function escapeHtml(str) {
        if (typeof str !== "string") return String(str);
        return str
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
});
