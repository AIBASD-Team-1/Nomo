// Nomo Web Interface - Vanilla JS + Three.js CAD Viewer

const COPY_FEEDBACK_DURATION_MS = 1800;
const THEME_STORAGE_KEY = "nomo-theme";

document.addEventListener("DOMContentLoaded", () => {
    // Three.js CAD 3D View Renderer state
    let scene = null;
    let camera = null;
    let renderer = null;
    let cadGroup = null;
    let gridHelper = null;
    let axesHelper = null;
    let edgesList = [];
    let showEdges = true;

    // Orbit navigation state
    let isDragging = false;
    let isPanning = false;
    let previousPointer = { x: 0, y: 0 };
    let cameraTarget = null;
    let cameraSpherical = { radius: 1500, theta: Math.PI / 4, phi: Math.PI / 3 };

    // Theme toggle
    const themeToggle = document.getElementById("theme-toggle");

    function applyTheme(theme) {
        document.documentElement.setAttribute("data-theme", theme);
        const label = theme === "dark" ? "Switch to light mode" : "Switch to dark mode";
        themeToggle.setAttribute("aria-label", label);
        themeToggle.title = label;
        if (typeof updateThreeTheme === "function") {
            updateThreeTheme(theme);
        }
    }

    applyTheme(document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark");

    themeToggle.addEventListener("click", () => {
        const next =
            document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
        applyTheme(next);
        try {
            localStorage.setItem(THEME_STORAGE_KEY, next);
        } catch (e) {
            // Storage unavailable; theme just won't persist
        }
    });

    // Chat elements
    const chatForm = document.getElementById("chat-form");
    const promptInput = document.getElementById("prompt-input");
    const sendBtn = document.getElementById("send-btn");
    const chatMessages = document.getElementById("chat-messages");

    // Output panel tabs and views
    const tab3d = document.getElementById("tab-3d");
    const tabTable = document.getElementById("tab-table");
    const tabRaw = document.getElementById("tab-raw");
    const threeView = document.getElementById("three-view");
    const tableView = document.getElementById("json-table-view");
    const rawView = document.getElementById("json-raw-view");

    // Output content elements
    const tablePlaceholder = document.getElementById("table-placeholder");
    const tableResults = document.getElementById("table-results");
    const jsonTableBody = document.getElementById("json-table-body");
    const jsonRawCode = document.getElementById("json-raw-code");
    const copyJsonBtn = document.getElementById("copy-json-btn");
    const jsonStatusIndicator = document.getElementById("json-status-indicator");
    const downloadStlBtn = document.getElementById("download-stl-btn");
    const downloadStepBtn = document.getElementById("download-step-btn");

    // 3D View elements
    const threePlaceholder = document.getElementById("three-placeholder");
    const threeContainer = document.getElementById("three-container");
    const threeCanvasWrapper = document.getElementById("three-canvas");
    const threePartCount = document.getElementById("three-part-count");
    const resetCamBtn = document.getElementById("reset-cam-btn");
    const toggleWireframeBtn = document.getElementById("toggle-wireframe-btn");

    let currentJsonResponse = null;

    // Tab switching
    function switchTab(activeTab) {
        const is3D = activeTab === "3d";
        const isTable = activeTab === "table";
        const isRaw = activeTab === "raw";

        if (tab3d) tab3d.classList.toggle("active", is3D);
        if (tabTable) tabTable.classList.toggle("active", isTable);
        if (tabRaw) tabRaw.classList.toggle("active", isRaw);

        if (threeView) {
            threeView.classList.toggle("active", is3D);
            threeView.classList.toggle("hidden", !is3D);
        }
        if (tableView) {
            tableView.classList.toggle("active", isTable);
            tableView.classList.toggle("hidden", !isTable);
        }
        if (rawView) {
            rawView.classList.toggle("active", isRaw);
            rawView.classList.toggle("hidden", !isRaw);
        }

        if (is3D) {
            requestAnimationFrame(() => {
                handleThreeResize();
                if (renderer && scene && camera) {
                    renderer.render(scene, camera);
                }
            });
        }
    }

    if (tab3d) tab3d.addEventListener("click", () => switchTab("3d"));
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
            render3DModel(data);
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

    function updateDownloadButtons(data) {
        const hasModel = Array.isArray(data.result) && data.result.length > 0;
        if (downloadStlBtn) {
            downloadStlBtn.classList.toggle("hidden", !hasModel);
        }
        if (downloadStepBtn) {
            downloadStepBtn.classList.toggle("hidden", !hasModel);
        }
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
        updateDownloadButtons(data);
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

    // ==========================================
    // Three.js CAD 3D View Renderer
    // ==========================================
    const CAD_PALETTE = [
        0x3b82f6, // Blue
        0x10b981, // Emerald
        0xf59e0b, // Amber
        0x8b5cf6, // Violet
        0xec4899, // Pink
        0x06b6d4, // Cyan
        0x6366f1, // Indigo
    ];

    function initThree() {
        if (typeof THREE === "undefined" || !threeCanvasWrapper) {
            return;
        }
        if (renderer) {
            return;
        }

        cameraTarget = new THREE.Vector3(0, 0, 0);
        scene = new THREE.Scene();
        const currentTheme = document.documentElement.getAttribute("data-theme");
        const backgroundColor = currentTheme === "light" ? 0xf8fafc : 0x0f172a;
        scene.background = new THREE.Color(backgroundColor);

        const rect = threeCanvasWrapper.getBoundingClientRect();
        const width = Math.floor(rect.width) || threeCanvasWrapper.clientWidth || 600;
        const height = Math.floor(rect.height) || threeCanvasWrapper.clientHeight || 480;
        camera = new THREE.PerspectiveCamera(45, width / height, 1, 100000);

        try {
            renderer = new THREE.WebGLRenderer({
                antialias: true,
                powerPreference: "high-performance",
            });
        } catch (webglError) {
            console.error("WebGL error:", webglError);
            return;
        }

        renderer.setPixelRatio(window.devicePixelRatio || 1);
        renderer.setSize(width, height, true);
        threeCanvasWrapper.innerHTML = "";
        threeCanvasWrapper.appendChild(renderer.domElement);

        // Lighting
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
        scene.add(ambientLight);

        const directionalLight1 = new THREE.DirectionalLight(0xffffff, 0.85);
        directionalLight1.position.set(2000, 3500, 2500);
        scene.add(directionalLight1);

        const directionalLight2 = new THREE.DirectionalLight(0x94a3b8, 0.4);
        directionalLight2.position.set(-2000, -1500, 1500);
        scene.add(directionalLight2);

        // CAD Group (orient so CAD Z is pointing UP in Three.js)
        cadGroup = new THREE.Group();
        cadGroup.rotation.x = -Math.PI / 2;
        scene.add(cadGroup);

        // Ground Grid
        createGrid(2000, currentTheme);

        // Setup mouse / touch navigation
        setupInteraction(renderer.domElement);

        resetCameraView();

        // Animation loop
        function animate() {
            requestAnimationFrame(animate);
            if (renderer && scene && camera) {
                renderer.render(scene, camera);
            }
        }
        animate();

        window.addEventListener("resize", handleThreeResize);
    }

    function createGrid(size, theme) {
        if (!scene) return;
        if (gridHelper && scene.remove) scene.remove(gridHelper);
        if (axesHelper && scene.remove) scene.remove(axesHelper);

        const gridColor1 = theme === "light" ? 0x94a3b8 : 0x334155;
        const gridColor2 = theme === "light" ? 0xe2e8f0 : 0x1e293b;
        gridHelper = new THREE.GridHelper(size, 20, gridColor1, gridColor2);
        gridHelper.position.y = 0;
        if (scene.add) scene.add(gridHelper);

        axesHelper = new THREE.AxesHelper(size / 8);
        if (scene.add) scene.add(axesHelper);
    }

    function updateThreeTheme(theme) {
        if (!scene) return;
        const backgroundColor = theme === "light" ? 0xf8fafc : 0x0f172a;
        scene.background = new THREE.Color(backgroundColor);
        if (gridHelper) {
            const currentSize =
                gridHelper.geometry && gridHelper.geometry.parameters
                    ? gridHelper.geometry.parameters.size
                    : 2000;
            createGrid(currentSize, theme);
        }
    }

    function handleThreeResize() {
        if (!renderer || !camera || !threeCanvasWrapper) return;
        const rect = threeCanvasWrapper.getBoundingClientRect();
        const width = Math.floor(rect.width) || threeCanvasWrapper.clientWidth;
        const height = Math.floor(rect.height) || threeCanvasWrapper.clientHeight;
        if (width <= 0 || height <= 0) return;
        camera.aspect = width / height;
        camera.updateProjectionMatrix();
        renderer.setSize(width, height, true);
    }

    function updateCameraFromSpherical() {
        if (!camera || !camera.position || !cameraTarget) return;
        const x =
            cameraTarget.x +
            cameraSpherical.radius *
                Math.sin(cameraSpherical.phi) *
                Math.sin(cameraSpherical.theta);
        const y = cameraTarget.y + cameraSpherical.radius * Math.cos(cameraSpherical.phi);
        const z =
            cameraTarget.z +
            cameraSpherical.radius *
                Math.sin(cameraSpherical.phi) *
                Math.cos(cameraSpherical.theta);
        camera.position.set(x, y, z);
        camera.lookAt(cameraTarget.x, cameraTarget.y, cameraTarget.z);
    }

    function resetCameraView() {
        if (!cameraTarget) return;
        cameraSpherical.theta = Math.PI / 4;
        cameraSpherical.phi = Math.PI / 3;
        updateCameraFromSpherical();
    }

    if (resetCamBtn) {
        resetCamBtn.addEventListener("click", resetCameraView);
    }

    if (toggleWireframeBtn) {
        toggleWireframeBtn.addEventListener("click", () => {
            showEdges = !showEdges;
            edgesList.forEach((edgeMesh) => {
                edgeMesh.visible = showEdges;
            });
            toggleWireframeBtn.textContent = showEdges ? "Hide Edges" : "Show Edges";
        });
    }

    function setupInteraction(domElement) {
        domElement.addEventListener("contextmenu", (e) => e.preventDefault());

        domElement.addEventListener("mousedown", (e) => {
            isDragging = true;
            isPanning = e.button === 2 || e.shiftKey;
            previousPointer = { x: e.clientX, y: e.clientY };
        });

        window.addEventListener("mouseup", () => {
            isDragging = false;
            isPanning = false;
        });

        domElement.addEventListener("mousemove", (e) => {
            if (!isDragging) return;
            const deltaX = e.clientX - previousPointer.x;
            const deltaY = e.clientY - previousPointer.y;
            previousPointer = { x: e.clientX, y: e.clientY };

            if (isPanning) {
                // Pan along camera right and up vectors
                const panFactor = cameraSpherical.radius * 0.0012;
                const right = new THREE.Vector3();
                const up = new THREE.Vector3();
                camera.matrix.extractBasis(right, up, new THREE.Vector3());

                cameraTarget.addScaledVector(right, -deltaX * panFactor);
                cameraTarget.addScaledVector(up, deltaY * panFactor);
            } else {
                // Orbit rotation
                cameraSpherical.theta -= deltaX * 0.008;
                cameraSpherical.phi = Math.max(
                    0.05,
                    Math.min(Math.PI - 0.05, cameraSpherical.phi - deltaY * 0.008),
                );
            }
            updateCameraFromSpherical();
        });

        domElement.addEventListener(
            "wheel",
            (e) => {
                e.preventDefault();
                const zoomFactor = e.deltaY > 0 ? 1.1 : 0.9;
                cameraSpherical.radius = Math.max(
                    20,
                    Math.min(50000, cameraSpherical.radius * zoomFactor),
                );
                updateCameraFromSpherical();
            },
            { passive: false },
        );

        // Touch support
        let touchStartDist = 0;
        domElement.addEventListener("touchstart", (e) => {
            if (e.touches.length === 1) {
                isDragging = true;
                isPanning = false;
                previousPointer = { x: e.touches[0].clientX, y: e.touches[0].clientY };
            } else if (e.touches.length === 2) {
                isDragging = false;
                const dx = e.touches[0].clientX - e.touches[1].clientX;
                const dy = e.touches[0].clientY - e.touches[1].clientY;
                touchStartDist = Math.sqrt(dx * dx + dy * dy);
            }
        });

        domElement.addEventListener("touchmove", (e) => {
            if (e.touches.length === 1 && isDragging) {
                const deltaX = e.touches[0].clientX - previousPointer.x;
                const deltaY = e.touches[0].clientY - previousPointer.y;
                previousPointer = { x: e.touches[0].clientX, y: e.touches[0].clientY };
                cameraSpherical.theta -= deltaX * 0.008;
                cameraSpherical.phi = Math.max(
                    0.05,
                    Math.min(Math.PI - 0.05, cameraSpherical.phi - deltaY * 0.008),
                );
                updateCameraFromSpherical();
            } else if (e.touches.length === 2) {
                const dx = e.touches[0].clientX - e.touches[1].clientX;
                const dy = e.touches[0].clientY - e.touches[1].clientY;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (touchStartDist > 0) {
                    const ratio = touchStartDist / dist;
                    cameraSpherical.radius = Math.max(
                        20,
                        Math.min(50000, cameraSpherical.radius * ratio),
                    );
                    updateCameraFromSpherical();
                    touchStartDist = dist;
                }
            }
        });

        domElement.addEventListener("touchend", () => {
            isDragging = false;
        });
    }

    function render3DModel(data) {
        if (!scene && typeof THREE !== "undefined") {
            initThree();
        }
        if (!scene || typeof THREE === "undefined") {
            console.warn("Three.js not loaded or scene not initialized");
            return;
        }

        const instances = Array.isArray(data.result) ? data.result : [];
        if (instances.length === 0) {
            threePlaceholder.classList.remove("hidden");
            threeContainer.classList.add("hidden");
            return;
        }

        // Show 3D container, hide placeholder
        threePlaceholder.classList.add("hidden");
        threeContainer.classList.remove("hidden");

        // Clear existing geometry
        while (cadGroup.children.length > 0) {
            const child = cadGroup.children[0];
            cadGroup.remove(child);
            if (child.geometry) child.geometry.dispose();
            if (child.material) {
                if (Array.isArray(child.material)) child.material.forEach((m) => m.dispose());
                else child.material.dispose();
            }
        }
        edgesList = [];

        // Build each instance
        instances.forEach((instance, index) => {
            const template = instance.template || "box";
            const params = instance.parameters || {};
            const pos = instance.position || { x: 0, y: 0, z: 0 };
            const rot = instance.rotation || { x: 0, y: 0, z: 0 };

            let geom = null;

            if (template === "box") {
                const length = params.length || 100;
                const width = params.width || 100;
                const height = params.height || 100;
                geom = new THREE.BoxGeometry(length, width, height);
                // In Nomo: origin is centre of bottom face (length along X, width along Y, height along Z)
                geom.translate(0, 0, height / 2);
            } else if (template === "cylinder") {
                const diameter = params.diameter || 100;
                const height = params.height || 100;
                const radius = diameter / 2;
                geom = new THREE.CylinderGeometry(radius, radius, height, 32);
                // Rotate so cylinder axis is along Z and bottom is at z=0
                geom.rotateX(Math.PI / 2);
                geom.translate(0, 0, height / 2);
            } else if (template === "sphere") {
                const diameter = params.diameter || 100;
                const radius = diameter / 2;
                geom = new THREE.SphereGeometry(radius, 32, 24);
                // Lowest point at z=0, centre at z=radius
                geom.translate(0, 0, radius);
            } else {
                // Fallback box
                geom = new THREE.BoxGeometry(100, 100, 100);
                geom.translate(0, 0, 50);
            }

            const color = CAD_PALETTE[index % CAD_PALETTE.length];
            const material = new THREE.MeshStandardMaterial({
                color: color,
                metalness: 0.15,
                roughness: 0.45,
            });

            const mesh = new THREE.Mesh(geom, material);

            // Apply rotation in fixed X, then Y, then Z axis (matches Rz * Ry * Rx)
            const rx = (rot.x || 0) * (Math.PI / 180);
            const ry = (rot.y || 0) * (Math.PI / 180);
            const rz = (rot.z || 0) * (Math.PI / 180);
            const euler = new THREE.Euler(rx, ry, rz, "ZYX");
            mesh.setRotationFromEuler(euler);

            // Apply translation
            mesh.position.set(pos.x || 0, pos.y || 0, pos.z || 0);

            // CAD Edge highlights
            const edgeGeometry = new THREE.EdgesGeometry(geom, 24);
            const edgeMaterial = new THREE.LineBasicMaterial({ color: 0x0f172a, linewidth: 1.5 });
            const edgeLines = new THREE.LineSegments(edgeGeometry, edgeMaterial);
            edgeLines.visible = showEdges;
            mesh.add(edgeLines);
            edgesList.push(edgeLines);

            cadGroup.add(mesh);
        });

        // Frame camera on the model's bounding box
        cadGroup.updateMatrixWorld(true);
        const bbox = new THREE.Box3().setFromObject(cadGroup);
        const center = bbox.getCenter(new THREE.Vector3());
        const size = bbox.getSize(new THREE.Vector3());

        cameraTarget.copy(center);
        const maxDim = Math.max(size.x, size.y, size.z, 100);
        cameraSpherical.radius = maxDim * 2.5;
        cameraSpherical.theta = Math.PI / 4;
        cameraSpherical.phi = Math.PI / 3;
        updateCameraFromSpherical();

        // Update ground grid size
        const theme = document.documentElement.getAttribute("data-theme");
        const gridSize = Math.max(1000, Math.ceil((maxDim * 3.5) / 100) * 100);
        createGrid(gridSize, theme);

        if (threePartCount) {
            threePartCount.textContent = `${instances.length} part${instances.length === 1 ? "" : "s"}`;
        }

        // Switch to 3D tab so user sees the 3D model
        switchTab("3d");
        requestAnimationFrame(() => {
            handleThreeResize();
            if (renderer && scene && camera) {
                renderer.render(scene, camera);
            }
        });
        setTimeout(() => {
            handleThreeResize();
            if (renderer && scene && camera) {
                renderer.render(scene, camera);
            }
        }, 100);
    }

    // Initialize Three.js on page load
    initThree();
});
