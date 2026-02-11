/**
 * 🏛️ Project Parliament - フロントエンド
 * WebSocket通信 + UI制御
 */

// ============================================================
// WebSocket 接続
// ============================================================
const socket = io();

// ============================================================
// 状態管理
// ============================================================
let selectedFiles = [];
let onlineCount = 0;
const TOTAL_AI = 11;

// ============================================================
// DOM要素の参照
// ============================================================
const elements = {
    chatArea: document.getElementById("chatArea"),
    headerDate: document.getElementById("headerDate"),
    chatDateLabel: document.getElementById("chatDateLabel"),
    statusChip: document.getElementById("statusChip"),
    statusText: document.getElementById("statusText"),
    onlineBadge: document.getElementById("onlineBadge"),
    // フェーズ
    phaseActivate: document.getElementById("phaseActivate"),
    phaseUpload: document.getElementById("phaseUpload"),
    phaseRunning: document.getElementById("phaseRunning"),
    phaseComplete: document.getElementById("phaseComplete"),
    // ボタン
    btnActivateAll: document.getElementById("btnActivateAll"),
    btnSelectFiles: document.getElementById("btnSelectFiles"),
    btnStart: document.getElementById("btnStart"),
    btnStop: document.getElementById("btnStop"),
    btnNewSession: document.getElementById("btnNewSession"),
    // ファイル
    chartInput: document.getElementById("chartInput"),
    previewStrip: document.getElementById("previewStrip"),
    fileCount: document.getElementById("fileCount"),
    // タイピング
    typingWho: document.getElementById("typingWho"),
    // 右パネル
    rpanelBadge: document.getElementById("rpanelBadge"),
    rpanelBody: document.getElementById("rpanelBody"),
};

// ============================================================
// 初期化
// ============================================================
function init() {
    // 日付表示
    const now = new Date();
    const options = { year: "numeric", month: "long", day: "numeric", weekday: "long" };
    const dateStr = now.toLocaleDateString("ja-JP", options);
    elements.headerDate.textContent = dateStr;

    const shortDate = `${now.getMonth() + 1}月${now.getDate()}日`;
    elements.chatDateLabel.textContent = shortDate;

    // イベントリスナー登録
    elements.btnActivateAll.addEventListener("click", activateAllAI);
    elements.btnSelectFiles.addEventListener("click", () => elements.chartInput.click());
    elements.chartInput.addEventListener("change", handleFileSelect);
    elements.btnStart.addEventListener("click", startDiscussion);
    elements.btnStop.addEventListener("click", stopDiscussion);
    elements.btnNewSession.addEventListener("click", stopDiscussion);
}

// ============================================================
// フェーズ表示切替
// ============================================================
function showPhase(phase) {
    // 全フェーズを非表示
    elements.phaseActivate.style.display = "none";
    elements.phaseUpload.style.display = "none";
    elements.phaseRunning.style.display = "none";
    elements.phaseComplete.style.display = "none";

    // 該当フェーズを表示
    switch (phase) {
        case "idle":
            elements.phaseActivate.style.display = "";
            setStatus("waiting", "AI起動待ち");
            break;
        case "activated":
            elements.phaseUpload.style.display = "";
            setStatus("standby", "スタンバイ");
            break;
        case "discussing":
            elements.phaseRunning.style.display = "";
            setStatus("discussing", "議論中");
            break;
        case "voting":
            elements.phaseRunning.style.display = "";
            setStatus("voting", "投票中");
            break;
        case "reviewing":
            elements.phaseRunning.style.display = "";
            setStatus("reviewing", "ブラッシュアップ中");
            break;
        case "complete":
            elements.phaseComplete.style.display = "";
            setStatus("complete", "完了");
            break;
    }
}

function setStatus(dataStatus, text) {
    elements.statusChip.setAttribute("data-status", dataStatus);
    elements.statusText.textContent = text;
}

// ============================================================
// AI起動
// ============================================================
function activateAllAI() {
    elements.btnActivateAll.disabled = true;
    elements.btnActivateAll.innerHTML =
        '<span class="cb-icon">⏳</span> 起動中...';
    socket.emit("activate_all_ai");
}

// ============================================================
// ファイル選択
// ============================================================
function handleFileSelect(event) {
    const files = Array.from(event.target.files);
    selectedFiles = selectedFiles.concat(files);
    updatePreviewStrip();
    updateStartButton();
}

function updatePreviewStrip() {
    elements.previewStrip.innerHTML = "";

    selectedFiles.forEach((file, index) => {
        const wrap = document.createElement("div");
        wrap.className = "thumb-wrap";

        const img = document.createElement("img");
        img.src = URL.createObjectURL(file);
        img.alt = file.name;

        const removeBtn = document.createElement("button");
        removeBtn.className = "thumb-remove";
        removeBtn.textContent = "✕";
        removeBtn.addEventListener("click", () => {
            selectedFiles.splice(index, 1);
            updatePreviewStrip();
            updateStartButton();
        });

        wrap.appendChild(img);
        wrap.appendChild(removeBtn);
        elements.previewStrip.appendChild(wrap);
    });

    // ファイル数バッジ
    if (selectedFiles.length > 0) {
        elements.fileCount.style.display = "";
        elements.fileCount.textContent = selectedFiles.length;
    } else {
        elements.fileCount.style.display = "none";
    }
}

function updateStartButton() {
    elements.btnStart.disabled = selectedFiles.length === 0;
}

// ============================================================
// 議論開始
// ============================================================
function startDiscussion() {
    if (selectedFiles.length === 0) return;

    socket.emit("start_discussion", {
        image_count: selectedFiles.length,
    });

    // Phase 3以降: ここで画像データもサーバーに送信する
    // TODO: 画像のBase64エンコードと送信
}

// ============================================================
// 議論停止
// ============================================================
function stopDiscussion() {
    socket.emit("stop_discussion");
    selectedFiles = [];
    onlineCount = 0;
    updateOnlineBadge();
}

// ============================================================
// オンラインバッジ更新
// ============================================================
function updateOnlineBadge() {
    const dot = elements.onlineBadge.querySelector(".online-dot");
    elements.onlineBadge.innerHTML = "";

    const newDot = document.createElement("span");
    newDot.className = "online-dot";
    if (onlineCount > 0) newDot.classList.add("active");

    elements.onlineBadge.appendChild(newDot);
    elements.onlineBadge.appendChild(
        document.createTextNode(` ${onlineCount} / ${TOTAL_AI}`)
    );
}

// ============================================================
// チャットメッセージ追加
// ============================================================
function addMessage(msg) {
    const chatArea = elements.chatArea;

    if (msg.type === "system") {
        // システムメッセージ
        const bubble = document.createElement("div");
        bubble.className = "system-bubble";
        bubble.innerHTML = `
            <div class="system-inner">
                <span class="sys-icon">📢</span>
                <span class="sys-text">${msg.content}</span>
            </div>
        `;
        chatArea.appendChild(bubble);

    } else if (msg.type === "ai_message") {
        // AIメッセージ
        const row = document.createElement("div");
        row.className = "msg-row ai";

        const time = new Date(msg.timestamp).toLocaleTimeString("ja-JP", {
            hour: "2-digit",
            minute: "2-digit",
        });

        row.innerHTML = `
            <div class="msg-avatar" style="background:${msg.avatar_color}">
                ${msg.icon}
            </div>
            <div class="msg-body">
                <div class="msg-header">
                    <span class="msg-name">${msg.ai_name}</span>
                    <span class="msg-time">${time}</span>
                </div>
                <div class="msg-bubble">${escapeHtml(msg.content)}</div>
            </div>
        `;
        chatArea.appendChild(row);

    } else if (msg.type === "proposal") {
        // 稟議書メッセージ
        const row = document.createElement("div");
        row.className = "msg-row ai";

        const time = new Date(msg.timestamp).toLocaleTimeString("ja-JP", {
            hour: "2-digit",
            minute: "2-digit",
        });

        row.innerHTML = `
            <div class="msg-avatar" style="background:${msg.avatar_color}">
                ${msg.icon}
            </div>
            <div class="msg-body">
                <div class="msg-header">
                    <span class="msg-name">${msg.ai_name}</span>
                    <span class="msg-time">${time}</span>
                </div>
                <div class="msg-bubble proposal-bubble">
                    <span class="proposal-tag">📋 稟議書</span>
                    ${escapeHtml(msg.content)}
                </div>
            </div>
        `;
        chatArea.appendChild(row);
    }

    // 自動スクロール
    chatArea.scrollTop = chatArea.scrollHeight;
}

// ============================================================
// ユーティリティ
// ============================================================
function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

// ============================================================
// WebSocket イベントハンドラ
// ============================================================

// AI接続状態変更
socket.on("ai_status_change", (data) => {
    const indicator = document.getElementById(`indicator-${data.ai_id}`);
    if (!indicator) return;

    // CSSクラス更新
    indicator.className = "status-indicator";
    indicator.classList.add(data.status);

    // オンライン数更新
    if (data.status === "online") {
        onlineCount++;
        updateOnlineBadge();
    }
});

// 新しいメッセージ
socket.on("new_message", (msg) => {
    addMessage(msg);
});

// フェーズ変更
socket.on("phase_change", (data) => {
    showPhase(data.phase);
});

// リセット
socket.on("reset", () => {
    // チャットエリアをクリア（ウェルカムメッセージは残す）
    const chatArea = elements.chatArea;
    const children = Array.from(chatArea.children);
    children.forEach((child, i) => {
        if (i > 1) child.remove(); // 日付区切り＋ウェルカムは残す
    });

    // インジケーターをリセット
    document.querySelectorAll(".status-indicator").forEach((el) => {
        el.className = "status-indicator offline";
    });

    // フェーズを初期化
    showPhase("idle");
    onlineCount = 0;
    updateOnlineBadge();

    // 起動ボタンを復元
    elements.btnActivateAll.disabled = false;
    elements.btnActivateAll.innerHTML =
        '<span class="cb-icon">⚡</span> 全AIを起動';
});

// 接続状態
socket.on("connect", () => {
    console.log("[WS] サーバーに接続しました");
});

socket.on("disconnect", () => {
    console.log("[WS] サーバーから切断されました");
});

// ============================================================
// 起動
// ============================================================
document.addEventListener("DOMContentLoaded", init);
