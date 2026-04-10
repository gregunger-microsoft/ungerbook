(function () {
    "use strict";

    // --- State ---
    let ws = null;
    let personalities = [];
    let selectedIds = new Set();
    let sessionActive = false;
    let streamBuffers = {};
    let autoScroll = true;
    let paused = false;

    // --- DOM refs ---
    const setupPanel = document.getElementById("setup-panel");
    const chatPanel = document.getElementById("chat-panel");
    const historyPanel = document.getElementById("history-panel");
    const sidebarHistory = document.getElementById("session-history");
    const moderatorPanel = document.getElementById("moderator-panel");

    const topicInput = document.getElementById("topic-input");
    const personalitySelector = document.getElementById("personality-selector");
    const startBtn = document.getElementById("start-btn");
    const endBtn = document.getElementById("end-btn");
    const pauseBtn = document.getElementById("pause-btn");
    const autoscrollBtn = document.getElementById("autoscroll-btn");
    const exportBtn = document.getElementById("export-btn");
    const chatTopic = document.getElementById("chat-topic");
    const chatMessages = document.getElementById("chat-messages");
    const messageInput = document.getElementById("message-input");
    const sendBtn = document.getElementById("send-btn");
    const thinkingIndicator = document.getElementById("thinking-indicator");
    const thinkingNames = document.getElementById("thinking-names");
    const personalityToggles = document.getElementById("personality-toggles");
    const sessionList = document.getElementById("session-list");

    const historyBackBtn = document.getElementById("history-back-btn");
    const historyTopic = document.getElementById("history-topic");
    const historyMessages = document.getElementById("history-messages");

    // --- Initialize ---
    async function init() {
        await loadPersonalities();
        await loadSessionHistory();
    }

    async function loadPersonalities() {
        const res = await fetch("/api/personalities");
        personalities = await res.json();
        renderPersonalitySelector();
    }

    async function loadSessionHistory() {
        const res = await fetch("/api/sessions");
        const sessions = await res.json();
        renderSessionHistory(sessions);
    }

    // --- Personality Selector ---
    function renderPersonalitySelector() {
        personalitySelector.innerHTML = "";
        personalities.forEach(p => {
            const card = document.createElement("div");
            card.className = "personality-card";
            card.dataset.id = p.id;
            card.innerHTML = `
                <div class="card-header">
                    <span class="card-avatar" style="background:${p.avatar_color}"></span>
                    <span class="card-name">${p.name}</span>
                </div>
                <span class="card-role">${p.role}</span>
            `;
            card.addEventListener("click", () => togglePersonality(p.id, card));
            personalitySelector.appendChild(card);
        });
    }

    function togglePersonality(id, card) {
        if (selectedIds.has(id)) {
            selectedIds.delete(id);
            card.classList.remove("selected");
        } else {
            if (selectedIds.size >= 10) return;
            selectedIds.add(id);
            card.classList.add("selected");
        }
        startBtn.disabled = selectedIds.size === 0 || !topicInput.value.trim();
    }

    topicInput.addEventListener("input", () => {
        startBtn.disabled = selectedIds.size === 0 || !topicInput.value.trim();
    });

    // --- Sample topic chips ---
    document.querySelectorAll(".topic-chip").forEach(chip => {
        chip.addEventListener("click", () => {
            topicInput.value = chip.dataset.topic;
            topicInput.dispatchEvent(new Event("input"));
        });
    });

    // --- Session Management ---
    startBtn.addEventListener("click", () => {
        const topic = topicInput.value.trim();
        if (!topic || selectedIds.size === 0) return;
        connectWebSocket(topic, Array.from(selectedIds));
    });

    endBtn.addEventListener("click", () => {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: "end_session" }));
        }
    });

    // --- Pause / Resume ---
    pauseBtn.addEventListener("click", () => {
        paused = !paused;
        if (paused) {
            pauseBtn.textContent = "Resume AI";
            pauseBtn.classList.add("paused");
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: "pause" }));
            }
        } else {
            pauseBtn.textContent = "Pause AI";
            pauseBtn.classList.remove("paused");
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: "resume" }));
            }
        }
    });

    // --- Auto-scroll toggle ---
    autoscrollBtn.addEventListener("click", () => {
        autoScroll = !autoScroll;
        autoscrollBtn.textContent = autoScroll ? "Auto-scroll: ON" : "Auto-scroll: OFF";
        autoscrollBtn.classList.toggle("active", autoScroll);
    });

    // --- Export conversation ---
    exportBtn.addEventListener("click", () => {
        const topic = chatTopic.textContent || "Conversation";
        const msgs = chatMessages.querySelectorAll(".chat-message");
        if (msgs.length === 0) return;

        let rows = "";
        msgs.forEach(msg => {
            const isHuman = msg.classList.contains("human");
            const name = msg.querySelector(".msg-sender")?.textContent || "Unknown";
            const content = msg.querySelector(".msg-content")?.textContent || "";
            const time = msg.querySelector(".msg-time")?.textContent || "";
            const avatarEl = msg.querySelector(".msg-avatar");
            const color = avatarEl ? avatarEl.style.background : "#7f8c8d";
            const align = isHuman ? "right" : "left";
            const bgColor = isHuman ? "#0f3460" : "#16213e";

            rows += `
            <div style="display:flex;gap:12px;max-width:80%;margin-bottom:16px;${isHuman ? 'margin-left:auto;flex-direction:row-reverse;' : ''}">
                <div style="width:36px;height:36px;border-radius:50%;background:${color};display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;color:#fff;flex-shrink:0;">${avatarEl ? avatarEl.textContent : '?'}</div>
                <div style="background:${bgColor};border:1px solid #0f3460;border-radius:12px;padding:10px 16px;">
                    <div style="font-size:12px;font-weight:600;color:${color};margin-bottom:4px;">${escapeHtml(name)}</div>
                    <div style="font-size:14px;line-height:1.5;color:#e0e0e0;">${escapeHtml(content)}</div>
                    <div style="font-size:10px;color:#555;margin-top:4px;text-align:right;">${time}</div>
                </div>
            </div>`;
        });

        const now = new Date().toLocaleString();
        const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Ungerbook Export - ${escapeHtml(topic)}</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a2e; color: #e0e0e0; margin: 0; padding: 0; }
  .header { background: #16213e; padding: 24px 40px; border-bottom: 2px solid #e94560; }
  .header h1 { color: #e94560; font-size: 1.4rem; margin: 0 0 4px; }
  .header .topic { font-size: 1.1rem; color: #e0e0e0; margin: 0 0 4px; }
  .header .meta { font-size: 0.75rem; color: #666; }
  .messages { padding: 30px 40px; }
</style>
</head>
<body>
<div class="header">
  <h1>Ungerbook</h1>
  <p class="topic">${escapeHtml(topic)}</p>
  <p class="meta">Exported on ${now} &middot; ${msgs.length} messages</p>
</div>
<div class="messages">
${rows}
</div>
</body>
</html>`;

        const blob = new Blob([html], { type: "text/html" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `ungerbook-${topic.replace(/[^a-zA-Z0-9]/g, '-').substring(0, 50)}.html`;
        a.click();
        URL.revokeObjectURL(url);
    });

    function connectWebSocket(topic, personalityIds) {
        const protocol = location.protocol === "https:" ? "wss:" : "ws:";
        ws = new WebSocket(`${protocol}//${location.host}/ws`);

        ws.onopen = () => {
            ws.send(JSON.stringify({
                type: "start_session",
                topic: topic,
                personalities: personalityIds,
            }));
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            handleServerMessage(data);
        };

        ws.onclose = () => {
            if (sessionActive) {
                showSetup();
            }
        };

        ws.onerror = (err) => {
            console.error("WebSocket error:", err);
        };
    }

    function handleServerMessage(data) {
        switch (data.type) {
            case "session_started":
                showChat(data.topic);
                break;
            case "session_ended":
                showSetup();
                loadSessionHistory();
                break;
            case "message":
                appendMessage(data);
                hideThinking();
                break;
            case "thinking":
                showThinking(data.personality_ids);
                break;
            case "stream_start":
                startStreamMessage(data);
                break;
            case "stream_chunk":
                appendStreamChunk(data);
                break;
            case "stream_end":
                endStreamMessage(data);
                break;
            case "muted":
                updateToggle(data.personality_id, false);
                break;
            case "unmuted":
                updateToggle(data.personality_id, true);
                break;
            case "error":
                console.error("Server error:", data.message);
                break;
        }
    }

    // --- Panel Switching ---
    function showChat(topic) {
        sessionActive = true;
        setupPanel.style.display = "none";
        historyPanel.style.display = "none";
        chatPanel.style.display = "flex";
        moderatorPanel.style.display = "block";
        paused = false;
        pauseBtn.textContent = "Pause AI";
        pauseBtn.classList.remove("paused");
        chatTopic.textContent = topic;
        chatMessages.innerHTML = "";
        renderModeratorPanel();
    }

    function showSetup() {
        sessionActive = false;
        chatPanel.style.display = "none";
        historyPanel.style.display = "none";
        moderatorPanel.style.display = "none";
        setupPanel.style.display = "block";
        selectedIds.clear();
        topicInput.value = "";
        startBtn.disabled = true;
        document.querySelectorAll(".personality-card.selected").forEach(c => c.classList.remove("selected"));
        if (ws) {
            ws.close();
            ws = null;
        }
    }

    function showHistory(sessionId, topic) {
        setupPanel.style.display = "none";
        chatPanel.style.display = "none";
        historyPanel.style.display = "flex";
        moderatorPanel.style.display = "none";
        historyTopic.textContent = topic;
        loadHistoryMessages(sessionId);
    }

    historyBackBtn.addEventListener("click", () => {
        historyPanel.style.display = "none";
        if (sessionActive) {
            chatPanel.style.display = "flex";
            moderatorPanel.style.display = "block";
        } else {
            setupPanel.style.display = "block";
        }
    });

    // --- Chat Messages ---
    function appendMessage(data) {
        const isHuman = data.sender_id === "human";
        const div = document.createElement("div");
        div.className = `chat-message ${isHuman ? "human" : "ai"}`;

        const initials = data.sender_name.split(" ").map(w => w[0]).join("").substring(0, 2);
        const time = new Date(data.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
        const roleSpan = data.role && data.role !== "Human" ? `<span class="msg-role">${data.role}</span>` : "";

        div.innerHTML = `
            <div class="msg-avatar" style="background:${data.avatar_color}">${initials}</div>
            <div class="msg-body">
                <div class="msg-sender" style="color:${data.avatar_color}">${data.sender_name}${roleSpan}</div>
                <div class="msg-content">${escapeHtml(data.content)}</div>
                <div class="msg-time">${time}</div>
            </div>
        `;
        chatMessages.appendChild(div);
        scrollToBottom();
    }

    // --- Streaming ---
    function startStreamMessage(data) {
        const div = document.createElement("div");
        div.className = "chat-message ai";
        div.id = `stream-${data.msg_id}`;

        const initials = data.sender_name.split(" ").map(w => w[0]).join("").substring(0, 2);

        div.innerHTML = `
            <div class="msg-avatar" style="background:${data.avatar_color}">${initials}</div>
            <div class="msg-body">
                <div class="msg-sender" style="color:${data.avatar_color}">${data.sender_name}</div>
                <div class="msg-content" id="stream-content-${data.msg_id}"></div>
                <div class="msg-time"></div>
            </div>
        `;
        chatMessages.appendChild(div);
        streamBuffers[data.msg_id] = "";
        hideThinking();
    }

    function appendStreamChunk(data) {
        const el = document.getElementById(`stream-content-${data.msg_id}`);
        if (el) {
            streamBuffers[data.msg_id] = (streamBuffers[data.msg_id] || "") + data.content;
            el.textContent = streamBuffers[data.msg_id];
            scrollToBottom();
        }
    }

    function endStreamMessage(data) {
        delete streamBuffers[data.msg_id];
        const div = document.getElementById(`stream-${data.msg_id}`);
        if (div) {
            const timeEl = div.querySelector(".msg-time");
            if (timeEl) {
                timeEl.textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
            }
        }
    }

    // --- Thinking Indicator ---
    function showThinking(personalityIds) {
        const names = personalityIds
            .map(id => personalities.find(p => p.id === id))
            .filter(Boolean)
            .map(p => p.name);
        if (names.length === 0) return;
        thinkingNames.textContent = names.join(", ") + (names.length === 1 ? " is" : " are") + " thinking";
        thinkingIndicator.style.display = "flex";
    }

    function hideThinking() {
        thinkingIndicator.style.display = "none";
    }

    // --- Send message ---
    sendBtn.addEventListener("click", sendMessage);
    messageInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    function sendMessage() {
        const content = messageInput.value.trim();
        if (!content || !ws || ws.readyState !== WebSocket.OPEN) return;
        ws.send(JSON.stringify({ type: "message", content: content }));
        messageInput.value = "";
    }

    // --- Moderator Panel ---
    function renderModeratorPanel() {
        personalityToggles.innerHTML = "";
        selectedIds.forEach(id => {
            const p = personalities.find(x => x.id === id);
            if (!p) return;
            const toggle = document.createElement("div");
            toggle.className = "personality-toggle";
            toggle.innerHTML = `
                <div class="toggle-info">
                    <span class="toggle-avatar" style="background:${p.avatar_color}"></span>
                    <span class="toggle-name">${p.name}</span>
                </div>
                <label class="toggle-switch">
                    <input type="checkbox" checked data-pid="${p.id}">
                    <span class="toggle-slider"></span>
                </label>
            `;
            const checkbox = toggle.querySelector("input");
            checkbox.addEventListener("change", () => {
                const type = checkbox.checked ? "unmute" : "mute";
                ws.send(JSON.stringify({ type: type, personality_id: p.id }));
            });
            personalityToggles.appendChild(toggle);
        });
    }

    function updateToggle(personalityId, active) {
        const checkbox = personalityToggles.querySelector(`input[data-pid="${personalityId}"]`);
        if (checkbox) checkbox.checked = active;
    }

    // --- Session History ---
    function renderSessionHistory(sessions) {
        sessionList.innerHTML = "";
        if (sessions.length === 0) {
            sessionList.innerHTML = '<div class="no-sessions">No past sessions</div>';
            return;
        }
        sessions.forEach(s => {
            const div = document.createElement("div");
            div.className = "session-item";
            const date = new Date(s.created_at).toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" });
            div.innerHTML = `
                <div class="session-topic">${escapeHtml(s.topic)}</div>
                <div class="session-date">${date}</div>
                <button class="session-delete" title="Delete session">✕</button>
            `;
            div.addEventListener("click", (e) => {
                if (e.target.classList.contains("session-delete")) return;
                showHistory(s.id, s.topic);
            });
            div.querySelector(".session-delete").addEventListener("click", async (e) => {
                e.stopPropagation();
                await fetch(`/api/sessions/${encodeURIComponent(s.id)}`, { method: "DELETE" });
                div.remove();
                if (sessionList.children.length === 0) {
                    sessionList.innerHTML = '<div class="no-sessions">No past sessions</div>';
                }
            });
            sessionList.appendChild(div);
        });
    }

    async function loadHistoryMessages(sessionId) {
        historyMessages.innerHTML = "";
        const res = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/messages`);
        const messages = await res.json();
        messages.forEach(m => {
            const isHuman = m.sender_id === "human";
            const div = document.createElement("div");
            div.className = `chat-message ${isHuman ? "human" : "ai"}`;
            const initials = m.sender_name.split(" ").map(w => w[0]).join("").substring(0, 2);
            const time = new Date(m.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
            const roleSpan = m.role && m.role !== "Human" ? `<span class="msg-role">${m.role}</span>` : "";
            div.innerHTML = `
                <div class="msg-avatar" style="background:${m.avatar_color}">${initials}</div>
                <div class="msg-body">
                    <div class="msg-sender" style="color:${m.avatar_color}">${m.sender_name}${roleSpan}</div>
                    <div class="msg-content">${escapeHtml(m.content)}</div>
                    <div class="msg-time">${time}</div>
                </div>
            `;
            historyMessages.appendChild(div);
        });
    }

    // --- Utility ---
    function scrollToBottom() {
        if (autoScroll) {
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
    }

    function escapeHtml(text) {
        const div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
    }

    // --- Boot ---
    init();
})();
