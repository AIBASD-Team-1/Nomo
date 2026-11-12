// Nomo Web Interface - Vanilla JS

const COPY_FEEDBACK_DURATION_MS = 1800;

document.addEventListener("DOMContentLoaded", () => {
    // Chat elements
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

    // Tab switching with simple control flow
    function switchTab(activeTab) {
        const isTable = activeTab === "table";
        tabTable.classList.toggle("active", isTable);
        tabRaw.classList.toggle("active", !isTable);
        tableView.classList.toggle("hidden", !isTable);
        rawView.classList.toggle("hidden", isTable);
    }

    tabTable.addEventListener("click", () => switchTab("table"));
    tabRaw.addEventListener("click", () => switchTab("raw"));

    // Copy JSON to clipboard
    copyJsonBtn.addEventListener("click", () => {
        if (!currentJsonResponse) return;
        const jsonText = JSON.stringify(currentJsonResponse, null, 2);
        navigator.clipboard.writeText(jsonText).then(() => {
            const originalText = copyJsonBtn.textContent;
            copyJsonBtn.textContent = "Copied!";
            setTimeout(() => {
                copyJsonBtn.textContent = originalText;
            }, COPY_FEEDBACK_DURATION_MS);
        });
    });

    // Quick prompt chips
    document.querySelectorAll(".chip").forEach((chip) => {
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

        appendMessage("user", promptText);
        promptInput.value = "";
        setLoading(true);

        try {
            const response = await fetch("/api/prompt", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ prompt: promptText }),
            });

            if (!response.ok) {
                throw new Error(`Server returned status ${response.status}`);
            }

            const data = await response.json();
            currentJsonResponse = data;

            const replyText = data.reply || data.message || "Prompt received.";
            appendMessage("assistant", replyText);

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

    function getValueType(value) {
        if (value === null) return "null";
        if (Array.isArray(value)) return "array";
        return typeof value;
    }

    function formatValueDisplay(key, val, type) {
        if (val === null) {
            return `<span class="type-tag">null</span>`;
        }
        if (type === "object") {
            const formatted = escapeHtml(JSON.stringify(val, null, 2));
            return `<pre class="table-code-block">${formatted}</pre>`;
        }
        if (type === "array") {
            const formatted = escapeHtml(JSON.stringify(val, null, 2));
            return `<span class="table-badge">${val.length} items</span> <pre class="table-code-block with-margin">${formatted}</pre>`;
        }
        if (key === "status") {
            const badgeClass = val === "success" ? "success" : "warning";
            return `<span class="table-badge ${badgeClass}">${escapeHtml(String(val))}</span>`;
        }
        return `<code>${escapeHtml(String(val))}</code>`;
    }

    function createTableRow(key, val) {
        const type = getValueType(val);
        const displayVal = formatValueDisplay(key, val, type);

        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td><strong>${escapeHtml(key)}</strong></td>
            <td><span class="type-tag">${type}</span></td>
            <td>${displayVal}</td>
        `;
        return tr;
    }

    function renderJsonTable(data) {
        tablePlaceholder.classList.add("hidden");
        tableResults.classList.remove("hidden");

        jsonTableBody.innerHTML = "";

        Object.keys(data).forEach((key) => {
            const row = createTableRow(key, data[key]);
            jsonTableBody.appendChild(row);
        });

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
