/**
 * Project Parliament - フロントエンド
 * WebSocket通信 + UI制御 + ポジション監視 + レポート表示
 */

// ============================================================
// WebSocket 接続
// ============================================================
const socket = io();

// ============================================================
// 状態管理
// ============================================================
let onlineCount = 0;
const TOTAL_AI = 9;

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
    phaseStart: document.getElementById("phaseStart"),
    phaseRunning: document.getElementById("phaseRunning"),
    phaseComplete: document.getElementById("phaseComplete"),
    // ボタン
    btnActivateAll: document.getElementById("btnActivateAll"),
    btnStart: document.getElementById("btnStart"),
    btnStop: document.getElementById("btnStop"),
    btnNewSession: document.getElementById("btnNewSession"),
    // タイピング
    typingWho: document.getElementById("typingWho"),
    // 右パネル：稟議書
    rpanelBadge: document.getElementById("rpanelBadge"),
    rpanelBody: document.getElementById("rpanelBody"),
    // 右パネル：ポジション
    positionEmpty: document.getElementById("positionEmpty"),
    positionCard: document.getElementById("positionCard"),
    posSymbol: document.getElementById("posSymbol"),
    posStrategy: document.getElementById("posStrategy"),
    posCurrentPrice: document.getElementById("posCurrentPrice"),
    posPnl: document.getElementById("posPnl"),
    posPnlPercent: document.getElementById("posPnlPercent"),
    posPnlBox: document.getElementById("posPnlBox"),
    posTp: document.getElementById("posTp"),
    posEntry: document.getElementById("posEntry"),
    posSl: document.getElementById("posSl"),
    posRsi: document.getElementById("posRsi"),
    posVolume: document.getElementById("posVolume"),
    posTime: document.getElementById("posTime"),
    flagTrailing: document.getElementById("flagTrailing"),
    flagPartial: document.getElementById("flagPartial"),
    // 右パネル：レポート
    reportsEmpty: document.getElementById("reportsEmpty"),
    reportsList: document.getElementById("reportsList"),
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
    elements.btnStart.addEventListener("click", startDiscussion);
    elements.btnStop.addEventListener("click", stopDiscussion);
    elements.btnNewSession.addEventListener("click", stopDiscussion);

    // タブ切替
    document.querySelectorAll(".rpanel-tab").forEach((tab) => {
        tab.addEventListener("click", () => switchTab(tab.dataset.tab));
    });
}

// ============================================================
// 右パネル：タブ切替
// ============================================================
function switchTab(tabName) {
    // タブボタンの active 切替
    document.querySelectorAll(".rpanel-tab").forEach((t) => t.classList.remove("active"));
    const activeTab = document.querySelector(`.rpanel-tab[data-tab="${tabName}"]`);
    if (activeTab) activeTab.classList.add("active");

    // コンテンツの active 切替
    document.querySelectorAll(".rpanel-content").forEach((c) => c.classList.remove("active"));
    const contentMap = {
        proposal: "contentProposal",
        position: "contentPosition",
        reports: "contentReports",
    };
    const contentEl = document.getElementById(contentMap[tabName]);
    if (contentEl) contentEl.classList.add("active");
}

// ============================================================
// フェーズ表示切替
// ============================================================
function showPhase(phase) {
    // 全フェーズを非表示
    elements.phaseActivate.style.display = "none";
    elements.phaseStart.style.display = "none";
    elements.phaseRunning.style.display = "none";
    elements.phaseComplete.style.display = "none";

    // 該当フェーズを表示
    switch (phase) {
        case "idle":
            elements.phaseActivate.style.display = "";
            setStatus("waiting", "AI起動待ち");
            break;
        case "activated":
            elements.phaseStart.style.display = "";
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
        case "trading":
            elements.phaseRunning.style.display = "";
            setStatus("trading", "トレード実行中");
            // ポジションタブに自動切替
            switchTab("position");
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
// 議論開始
// ============================================================
function startDiscussion() {
    elements.btnStart.disabled = true;
    elements.btnStart.innerHTML = '<span class="cb-icon">⏳</span> 市場データ取得中...';

    socket.emit("start_discussion", {});
}

// ============================================================
// 議論停止
// ============================================================
function stopDiscussion() {
    socket.emit("stop_discussion");
    onlineCount = 0;
    updateOnlineBadge();
}

// ============================================================
// オンラインバッジ更新
// ============================================================
function updateOnlineBadge() {
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
        const bubble = document.createElement("div");
        bubble.className = "system-bubble";
        bubble.innerHTML = `
            <div class="system-inner">
                <span class="sys-icon">\uD83D\uDCE2</span>
                <span class="sys-text">${escapeHtml(msg.content)}</span>
            </div>
        `;
        chatArea.appendChild(bubble);

    } else if (msg.type === "ai_message") {
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
                    <span class="msg-name">${escapeHtml(msg.ai_name)}</span>
                    <span class="msg-time">${time}</span>
                </div>
                <div class="msg-bubble">${escapeHtml(msg.content)}</div>
            </div>
        `;
        chatArea.appendChild(row);

    } else if (msg.type === "proposal") {
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
                    <span class="msg-name">${escapeHtml(msg.ai_name)}</span>
                    <span class="msg-time">${time}</span>
                </div>
                <div class="msg-bubble proposal-bubble">
                    <span class="proposal-tag">\uD83D\uDCCB 稟議書</span>
                    <pre style="white-space:pre-wrap;margin:8px 0 0">${escapeHtml(msg.content)}</pre>
                </div>
            </div>
        `;
        chatArea.appendChild(row);

    } else if (msg.type === "vote") {
        const row = document.createElement("div");
        row.className = "msg-row ai";

        const time = new Date(msg.timestamp).toLocaleTimeString("ja-JP", {
            hour: "2-digit",
            minute: "2-digit",
        });

        const voteClass = msg.content.includes("\u8CDB\u6210") ? "vote-support" : "vote-oppose";

        row.innerHTML = `
            <div class="msg-avatar" style="background:${msg.avatar_color}">
                ${msg.icon}
            </div>
            <div class="msg-body">
                <div class="msg-header">
                    <span class="msg-name">${escapeHtml(msg.ai_name)}</span>
                    <span class="msg-time">${time}</span>
                </div>
                <div class="msg-bubble ${voteClass}">${escapeHtml(msg.content)}</div>
            </div>
        `;
        chatArea.appendChild(row);
    }

    // 自動スクロール
    chatArea.scrollTop = chatArea.scrollHeight;
}

// ============================================================
// 右パネル: 稟議書表示
// ============================================================
function updateProposalPanel(proposal) {
    if (!elements.rpanelBody) return;

    const strategyLabel = proposal.strategy === "long" ? "LONG" : "SHORT";
    const strategyClass = proposal.strategy === "long" ? "strategy-long" : "strategy-short";

    elements.rpanelBody.innerHTML = `
        <div class="proposal-detail">
            <div class="proposal-header">
                <span class="${strategyClass}">${strategyLabel}</span>
                <span class="proposal-pair">${escapeHtml(proposal.pair)}</span>
            </div>
            <div class="proposal-fields">
                <div class="field"><label>エントリー</label><span>${proposal.entry_price}</span></div>
                <div class="field"><label>利確目標</label><span>${proposal.take_profit}</span></div>
                <div class="field"><label>損切り</label><span>${proposal.stop_loss}</span></div>
            </div>
            <div class="proposal-reasoning">
                <label>根拠</label>
                <p>${escapeHtml(proposal.reasoning)}</p>
            </div>
            <div class="voting-board" id="votingBoard"></div>
        </div>
    `;

    if (elements.rpanelBadge) {
        elements.rpanelBadge.textContent = proposal.status;
    }
}

// ============================================================
// 右パネル: 投票状況更新
// ============================================================
function updateVotingBoard(status) {
    const board = document.getElementById("votingBoard");
    if (!board) return;

    let html = '<h4>投票状況</h4>';
    html += `<p>${status.voted}/${status.total_voters} 投票済み</p>`;

    for (const [voterId, voteData] of Object.entries(status.votes)) {
        const label = voteData
            ? (voteData.vote === "support" ? "\u2705 賛成" : "\u274C 反対")
            : "\u23F3 未投票";
        html += `<div class="vote-entry"><span>${voterId}</span><span>${label}</span></div>`;
    }

    if (status.consensus === "approved") {
        html += '<div class="consensus-approved">承認</div>';
    } else if (status.consensus === "rejected") {
        html += '<div class="consensus-rejected">否決</div>';
    }

    board.innerHTML = html;
}

// ============================================================
// ポジション監視パネル：更新
// ============================================================
function updatePositionPanel(data) {
    if (!elements.positionCard) return;

    // 空表示を非表示、カードを表示
    if (elements.positionEmpty) elements.positionEmpty.style.display = "none";
    elements.positionCard.style.display = "";

    // シンボル & 戦略
    elements.posSymbol.textContent = data.trade_id ? `${data.trade_id}` : "—";
    if (data.strategy) {
        elements.posStrategy.textContent = data.strategy.toUpperCase();
        elements.posStrategy.className = `pos-strategy ${data.strategy}`;
    }

    // 現在価格
    elements.posCurrentPrice.textContent = formatPrice(data.current_price);

    // PnL
    const pnl = data.unrealized_pnl || 0;
    const pnlPct = data.pnl_percent || 0;
    elements.posPnl.textContent = pnl >= 0 ? `+${pnl.toFixed(4)}` : pnl.toFixed(4);
    elements.posPnlPercent.textContent = pnlPct >= 0 ? `+${pnlPct.toFixed(2)}%` : `${pnlPct.toFixed(2)}%`;

    // PnL色分け
    elements.posPnlBox.className = `pos-pnl ${pnl >= 0 ? "profit" : "loss"}`;

    // TP / Entry / SL
    elements.posTp.textContent = formatPrice(data.take_profit);
    elements.posEntry.textContent = formatPrice(data.entry_price);
    elements.posSl.textContent = formatPrice(data.stop_loss);

    // テクニカル指標
    elements.posRsi.textContent = data.rsi != null ? data.rsi.toFixed(1) : "—";
    elements.posVolume.textContent = data.volume_ratio != null ? `${data.volume_ratio.toFixed(1)}x` : "—";
    elements.posTime.textContent = data.time_label || "—";

    // フラグ
    elements.flagTrailing.style.display = data.trailing_stop_active ? "" : "none";
    elements.flagPartial.style.display = data.partial_closed ? "" : "none";
}

function resetPositionPanel() {
    if (elements.positionEmpty) elements.positionEmpty.style.display = "";
    if (elements.positionCard) elements.positionCard.style.display = "none";
}

// ============================================================
// レポートパネル：レポートカード追加
// ============================================================
function addReportCard(report) {
    if (!elements.reportsList) return;

    if (elements.reportsEmpty) elements.reportsEmpty.style.display = "none";

    const pnl = report.pnl || 0;
    const pnlClass = pnl >= 0 ? "profit" : "loss";
    const pnlStr = pnl >= 0 ? `+${pnl.toFixed(4)}` : pnl.toFixed(4);

    // close_reason のラベルとクラス
    const reasonMap = {
        tp_hit: { label: "利確", cls: "tp" },
        sl_hit: { label: "損切", cls: "sl" },
        trailing_stop: { label: "TS", cls: "ts" },
        timeout: { label: "時間超過", cls: "max" },
        manual: { label: "手動", cls: "max" },
    };
    const reason = reasonMap[report.close_reason] || { label: report.close_reason || "—", cls: "max" };

    const card = document.createElement("div");
    card.className = "report-card";
    card.innerHTML = `
        <div class="report-header">
            <span class="report-symbol">${escapeHtml(report.symbol || "")}</span>
            <span class="report-pnl ${pnlClass}">${pnlStr} USDT</span>
        </div>
        <div class="report-meta">
            ${report.opened_at || ""}
            <span class="report-reason ${reason.cls}">${reason.label}</span>
        </div>
    `;

    // クリックで詳細表示（将来的にモーダル化可能）
    card.addEventListener("click", () => {
        if (report.ai_analysis) {
            alert(report.ai_analysis);
        }
    });

    elements.reportsList.prepend(card);
}

// ============================================================
// ユーティリティ
// ============================================================
function escapeHtml(text) {
    if (!text) return "";
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

function formatPrice(price) {
    if (price == null) return "—";
    // 1以上なら小数2桁、1未満なら小数6桁
    return price >= 1 ? price.toFixed(2) : price.toFixed(6);
}

// ============================================================
// WebSocket イベントハンドラ
// ============================================================

// AI接続状態変更
socket.on("ai_status_change", (data) => {
    const indicator = document.getElementById(`indicator-${data.ai_id}`);
    if (!indicator) return;

    indicator.className = "status-indicator";
    indicator.classList.add(data.status);

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

// AI発言中通知
socket.on("ai_speaking", (data) => {
    if (elements.typingWho) {
        if (data.speaking) {
            elements.typingWho.textContent = data.ai_id;
            elements.typingWho.parentElement.style.display = "";
        } else {
            elements.typingWho.parentElement.style.display = "none";
        }
    }
});

// 稟議書提出
socket.on("proposal_submitted", (proposal) => {
    updateProposalPanel(proposal);
});

// 投票状況更新
socket.on("voting_update", (status) => {
    updateVotingBoard(status);
});

// 稟議書最終確定
socket.on("proposal_finalized", (proposal) => {
    updateProposalPanel(proposal);
});

// ---- トレード関連 ----

// トレード実行完了
socket.on("trade_executed", (trade) => {
    // ポジションパネルを初期化表示
    updatePositionPanel({
        trade_id: trade.trade_id,
        strategy: trade.strategy,
        current_price: trade.entry_price,
        entry_price: trade.entry_price,
        take_profit: trade.take_profit,
        stop_loss: trade.stop_loss,
        unrealized_pnl: 0,
        pnl_percent: 0,
        time_label: "0min",
    });
    // ポジションタブに自動切替
    switchTab("position");
});

// ポジション監視のリアルタイム更新（30秒ごと）
socket.on("trade_monitor_update", (data) => {
    updatePositionPanel(data);
});

// 部分利確
socket.on("trade_partial_tp", (data) => {
    addMessage({
        type: "system",
        content: `✂️ 部分利確: ${data.close_qty.toFixed(8)} @ ${data.close_price} | 残り: ${data.remaining_qty.toFixed(8)}`,
        timestamp: new Date().toISOString(),
    });
});

// トレード決済
socket.on("trade_closed", (data) => {
    const pnlLabel = data.pnl >= 0 ? `+${data.pnl}` : `${data.pnl}`;
    const pctLabel = data.pnl_percent != null ? ` (${data.pnl_percent}%)` : "";
    addMessage({
        type: "system",
        content: `トレード終了: ${data.reason} | 決済価格: ${data.close_price} | 損益: ${pnlLabel}${pctLabel}`,
        timestamp: new Date().toISOString(),
    });

    // ポジションパネルをリセット
    resetPositionPanel();
});

// レポート生成完了
socket.on("trade_report_generated", (report) => {
    addReportCard(report);
    addMessage({
        type: "system",
        content: `📑 AI分析レポート生成完了: ${report.symbol || ""}`,
        timestamp: new Date().toISOString(),
    });
    // レポートタブに自動切替
    switchTab("reports");
});

// 監視エラー
socket.on("trade_monitor_error", (data) => {
    console.warn("Monitor error:", data);
});

// エラー
socket.on("error", (data) => {
    console.error("Server error:", data.message);
    addMessage({
        type: "system",
        content: `エラー: ${data.message}`,
        timestamp: new Date().toISOString(),
    });
});

// リセット
socket.on("reset", () => {
    const chatArea = elements.chatArea;
    const children = Array.from(chatArea.children);
    children.forEach((child, i) => {
        if (i > 1) child.remove();
    });

    document.querySelectorAll(".status-indicator").forEach((el) => {
        el.className = "status-indicator offline";
    });

    showPhase("idle");
    onlineCount = 0;
    updateOnlineBadge();

    elements.btnActivateAll.disabled = false;
    elements.btnActivateAll.innerHTML =
        '<span class="cb-icon">\u26A1</span> 全AIを起動';

    // 右パネルリセット
    if (elements.rpanelBody) {
        elements.rpanelBody.innerHTML = `
            <div class="rpanel-empty">
                <div class="empty-icon">📋</div>
                <p>AIが稟議書を提出すると<br>ここに表示されます</p>
            </div>
        `;
    }
    resetPositionPanel();
    if (elements.reportsList) elements.reportsList.innerHTML = "";
    if (elements.reportsEmpty) elements.reportsEmpty.style.display = "";
    switchTab("proposal");
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
