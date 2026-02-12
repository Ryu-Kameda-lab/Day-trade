"""
Project Parliament - メインアプリケーション
Flask + Flask-SocketIO によるリアルタイムAI議論プラットフォーム
"""
import os
from datetime import datetime

from gevent import monkey
monkey.patch_all()

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit

from config import Config, AI_PROFILES
from services.ai_manager import AIManager
from services.mexc_service import MEXCService
from services.technical_analysis import TechnicalAnalyzer
from services.market_screener import MarketScreener
from core.orchestrator import DiscussionOrchestrator
from core.proposal import ProposalManager
from core.voting import VotingManager
from core.trade_executor import TradeExecutor
from core.trade_reporter import TradeReporter
from utils.logger import get_logger

logger = get_logger("app")

# ============================================================
# Flask アプリケーション初期化
# ============================================================
app = Flask(__name__)
app.config.from_object(Config)

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="gevent",
)

# ============================================================
# サービスの初期化
# ============================================================
ai_manager = AIManager()
mexc_service = MEXCService()
proposal_manager = ProposalManager()
voting_manager = VotingManager()

# テクニカル分析 & スクリーナー
analyzer = TechnicalAnalyzer()
screener = MarketScreener(mexc_service, analyzer)

# オーケストレーターの emit コールバック
def socketio_emit(event, data):
    socketio.emit(event, data)

# トレードエグゼキューター
trade_executor = TradeExecutor(
    mexc_service,
    emit_callback=socketio_emit,
    analyzer=analyzer,
    config=Config,
)

# トレードレポーター
trade_reporter = TradeReporter(
    ai_manager=ai_manager,
    mexc_service=mexc_service,
    analyzer=analyzer,
    emit_callback=socketio_emit,
)

# トレードクローズ後にレポートを自動生成
def on_trade_closed_callback(trade_record):
    """TradeExecutorのクローズ後コールバック"""
    try:
        report = trade_reporter.generate_report(trade_record)
        logger.info("レポート自動生成完了: %s", report.report_id)
    except Exception as e:
        logger.error("レポート生成エラー: %s", e)

trade_executor.on_trade_closed = on_trade_closed_callback

# オーケストレーター
orchestrator = DiscussionOrchestrator(ai_manager, socketio_emit)

# ============================================================
# アプリケーション状態（インメモリ）
# ============================================================
app_state = {
    "phase": "idle",       # idle -> activated -> discussing -> voting -> reviewing -> trading -> complete
    "online_ais": set(),
    "messages": [],
    "current_proposal_id": None,
    "current_trade_id": None,
}


# ============================================================
# ルート
# ============================================================
@app.route("/")
def index():
    """メインページ"""
    return render_template("index.html", ai_profiles=AI_PROFILES)


@app.route("/api/status")
def get_status():
    """現在のアプリケーション状態を返す"""
    return jsonify({
        "phase": app_state["phase"],
        "online_count": len(app_state["online_ais"]),
        "total_count": len(AI_PROFILES),
        "online_ais": list(app_state["online_ais"]),
    })


@app.route("/api/proposal/<proposal_id>")
def get_proposal(proposal_id):
    """稟議書を取得する"""
    proposal = proposal_manager.get_proposal(proposal_id)
    if not proposal:
        return jsonify({"error": "Proposal not found"}), 404
    return jsonify(proposal.to_dict())


@app.route("/api/trade-status")
def get_trade_status():
    """現在のトレード状況を取得する"""
    trade_id = app_state.get("current_trade_id")
    if not trade_id:
        return jsonify({"error": "No active trade"}), 404
    return jsonify(trade_executor.get_trade_status(trade_id))


@app.route("/api/screening")
def get_screening():
    """市場スクリーニングを実行し結果を返す"""
    top_n = request.args.get("top_n", 10, type=int)
    results = screener.screen_market(top_n=top_n, emit_callback=socketio_emit)
    return jsonify({
        "count": len(results),
        "results": [r.to_dict() for r in results],
    })


@app.route("/api/trades")
def get_trades():
    """トレード履歴を取得する"""
    return jsonify({
        "open": trade_executor.get_all_open_trades(),
        "history": trade_executor.get_trade_history(),
    })


@app.route("/api/reports")
def get_reports():
    """レポート一覧を取得する"""
    return jsonify(trade_reporter.get_all_reports())


@app.route("/api/reports/<report_id>")
def get_report(report_id):
    """レポート詳細を取得する"""
    report = trade_reporter.get_report(report_id)
    if not report:
        return jsonify({"error": "Report not found"}), 404
    return jsonify(report)


# ============================================================
# WebSocket イベント
# ============================================================
@socketio.on("connect")
def handle_connect():
    """クライアント接続時"""
    logger.info("クライアント接続: %s", request.sid)
    emit("state_update", {
        "phase": app_state["phase"],
        "online_ais": list(app_state["online_ais"]),
    })


@socketio.on("disconnect")
def handle_disconnect():
    """クライアント切断時"""
    logger.info("クライアント切断: %s", request.sid)


@socketio.on("activate_all_ai")
def handle_activate_all():
    """全AIを起動する（実APIテスト実行）"""
    logger.info("全AI起動リクエスト受信")

    # 再実行時の状態ズレを避けるため、一度オンライン状態をクリアする
    app_state["online_ais"].clear()

    for ai_id, profile in AI_PROFILES.items():
        # 接続中ステータスを送信
        emit("ai_status_change", {
            "ai_id": ai_id,
            "status": "connecting",
            "name": profile["name"],
        }, broadcast=True)
        socketio.sleep(0.1)

    # 実際のAPI接続テスト
    results = ai_manager.activate_all()

    for ai_id, result in results.items():
        profile = AI_PROFILES.get(ai_id, {})
        status = result["status"]

        if status == "online":
            app_state["online_ais"].add(ai_id)

        emit("ai_status_change", {
            "ai_id": ai_id,
            "status": status,
            "name": result["name"],
        }, broadcast=True)

        # システムメッセージ
        if status == "online":
            content = f"{profile.get('icon', '')} {result['name']}（{profile.get('role_label', '')}）がオンラインになりました"
        else:
            content = f"{profile.get('icon', '')} {result['name']} - 接続エラー: {result.get('error', '不明')}"

        sys_msg = {
            "type": "system",
            "content": content,
            "timestamp": datetime.now().isoformat(),
        }
        app_state["messages"].append(sys_msg)
        emit("new_message", sys_msg, broadcast=True)
        socketio.sleep(0.05)

    # 完了通知
    online_count = len(app_state["online_ais"])
    total_count = len(AI_PROFILES)
    app_state["phase"] = "activated"
    emit("phase_change", {"phase": "activated"}, broadcast=True)
    emit("new_message", {
        "type": "system",
        "content": f"AI起動完了（{online_count}/{total_count}体オンライン）。「議論を開始」ボタンを押すとMEXC市場データを取得し、議論を開始します。",
        "timestamp": datetime.now().isoformat(),
    }, broadcast=True)


@socketio.on("start_discussion")
def handle_start_discussion(data=None):
    """
    議論開始リクエスト
    MEXC市場データを取得し、全AIに共有して議論を開始する
    """
    logger.info("議論開始リクエスト受信")

    app_state["phase"] = "discussing"
    emit("phase_change", {"phase": "discussing"}, broadcast=True)

    emit("new_message", {
        "type": "system",
        "content": "MEXC取引所から市場データを取得中...",
        "timestamp": datetime.now().isoformat(),
    }, broadcast=True)

    # MEXC市場データを取得
    try:
        market_data = mexc_service.get_market_overview()
    except Exception as e:
        logger.error("MEXC市場データ取得エラー: %s", e)
        market_data = {"pairs": [], "total_pairs": 0, "summary": f"市場データの取得に失敗しました: {e}"}

    # 市場データ取得完了メッセージ
    summary = market_data.get("summary", "")
    emit("new_message", {
        "type": "system",
        "content": f"{summary} テクニカル分析を実行中...",
        "timestamp": datetime.now().isoformat(),
    }, broadcast=True)

    # スクリーニング実行（テクニカル分析付き）
    try:
        screening_results = screener.screen_market(
            top_n=Config.SCREENING_TOP_N,
            emit_callback=socketio_emit,
        )
        emit("new_message", {
            "type": "system",
            "content": f"スクリーニング完了: スコア上位 {len(screening_results)} ペアを選定。各AIがテクニカル指標を基に分析します。",
            "timestamp": datetime.now().isoformat(),
        }, broadcast=True)
    except Exception as e:
        logger.warning("スクリーニングエラー: %s", e)
        screening_results = None
        emit("new_message", {
            "type": "system",
            "content": f"スクリーニングエラー: {e}。市場データのみで議論を開始します。",
            "timestamp": datetime.now().isoformat(),
        }, broadcast=True)

    # バックグラウンドで議論を実行
    def run_discussion():
        decision = orchestrator.start_discussion(
            market_data=market_data,
            screening_results=screening_results,
        )

        if decision == "PROPOSE":
            app_state["phase"] = "voting"
            socketio.emit("phase_change", {"phase": "voting"})
            socketio.emit("new_message", {
                "type": "system",
                "content": "稟議書の提出が決定されました。リーダーまたは議長による稟議書作成を待っています。",
                "timestamp": datetime.now().isoformat(),
            })
        elif decision == "ABORT":
            app_state["phase"] = "complete"
            socketio.emit("phase_change", {"phase": "complete"})
        else:
            # CONTINUE but max rounds reached
            app_state["phase"] = "complete"
            socketio.emit("phase_change", {"phase": "complete"})

    import gevent
    gevent.spawn(run_discussion)


@socketio.on("submit_proposal")
def handle_submit_proposal(data):
    """
    稟議書提出
    data: { "submitted_by": "gpt_leader", "strategy": "long", "pair": "BTC/USDT",
            "entry_price": 95200, "take_profit": 98500, "stop_loss": 93800, "reasoning": "..." }
    """
    logger.info("稟議書提出: %s", data.get("submitted_by"))

    proposal = proposal_manager.create_proposal(
        submitted_by=data.get("submitted_by", "claude_chair"),
        data=data,
    )
    app_state["current_proposal_id"] = proposal.id
    app_state["phase"] = "voting"

    emit("phase_change", {"phase": "voting"}, broadcast=True)
    emit("proposal_submitted", proposal.to_dict(), broadcast=True)
    emit("new_message", {
        "type": "proposal",
        "ai_id": proposal.submitted_by,
        "ai_name": AI_PROFILES.get(proposal.submitted_by, {}).get("name", "Unknown"),
        "icon": AI_PROFILES.get(proposal.submitted_by, {}).get("icon", ""),
        "avatar_color": AI_PROFILES.get(proposal.submitted_by, {}).get("avatar_color", "#333"),
        "content": (
            f"【稟議書】\n"
            f"戦略: {proposal.strategy.upper()}\n"
            f"通貨ペア: {proposal.pair}\n"
            f"エントリー: {proposal.entry_price}\n"
            f"利確目標: {proposal.take_profit}\n"
            f"損切りライン: {proposal.stop_loss}\n"
            f"根拠: {proposal.reasoning}"
        ),
        "timestamp": datetime.now().isoformat(),
    }, broadcast=True)


@socketio.on("cast_vote")
def handle_cast_vote(data):
    """
    投票
    data: { "proposal_id": "...", "voter_id": "claude_chair", "vote": "support", "reason": "..." }
    """
    proposal_id = data.get("proposal_id") or app_state.get("current_proposal_id")
    if not proposal_id:
        emit("error", {"message": "No active proposal"})
        return

    proposal = proposal_manager.get_proposal(proposal_id)
    if not proposal:
        emit("error", {"message": "Proposal not found"})
        return

    voter_id = data.get("voter_id")
    vote = data.get("vote")
    reason = data.get("reason", "")

    if not voter_id or vote not in ("support", "oppose"):
        emit("error", {"message": "Invalid vote payload"})
        return

    success = voting_manager.cast_vote(proposal, voter_id, vote, reason)
    if not success:
        emit("error", {"message": "Vote failed"})
        return

    # 投票メッセージ送信
    voter_profile = AI_PROFILES.get(voter_id, {})
    vote_label = "賛成" if vote == "support" else "反対"
    emit("new_message", {
        "type": "vote",
        "ai_id": voter_id,
        "ai_name": voter_profile.get("name", voter_id),
        "icon": voter_profile.get("icon", ""),
        "avatar_color": voter_profile.get("avatar_color", "#333"),
        "content": f"【投票】{vote_label} - {reason}",
        "timestamp": datetime.now().isoformat(),
    }, broadcast=True)

    # 投票状況を更新
    status = voting_manager.get_voting_status(proposal)
    emit("voting_update", status, broadcast=True)

    # コンセンサス判定
    consensus = status["consensus"]
    if consensus == "approved":
        proposal.status = "approved"
        app_state["phase"] = "reviewing"
        emit("phase_change", {"phase": "reviewing"}, broadcast=True)
        emit("new_message", {
            "type": "system",
            "content": "稟議書が承認されました。ブラッシュアップフェーズに移行します。",
            "timestamp": datetime.now().isoformat(),
        }, broadcast=True)
    elif consensus == "rejected":
        proposal.status = "rejected"
        app_state["phase"] = "discussing"
        emit("phase_change", {"phase": "discussing"}, broadcast=True)
        emit("new_message", {
            "type": "system",
            "content": "稟議書が否決されました。議論に戻ります。",
            "timestamp": datetime.now().isoformat(),
        }, broadcast=True)


@socketio.on("finalize_proposal")
def handle_finalize_proposal(data):
    """
    稟議書の最終確定
    data: { "proposal_id": "...", "final_data": {...} }
    """
    proposal_id = data.get("proposal_id") or app_state.get("current_proposal_id")
    if not proposal_id:
        emit("error", {"message": "No active proposal"})
        return

    final_data = data.get("final_data")
    proposal = proposal_manager.finalize(proposal_id, final_data)

    if proposal:
        emit("proposal_finalized", proposal.to_dict(), broadcast=True)
        emit("new_message", {
            "type": "system",
            "content": "稟議書が最終確定されました。トレード実行の準備が整いました。",
            "timestamp": datetime.now().isoformat(),
        }, broadcast=True)


@socketio.on("execute_trade")
def handle_execute_trade(data):
    """
    トレード実行
    data: { "proposal_id": "..." } または稟議書データ直接
    """
    proposal_id = data.get("proposal_id") or app_state.get("current_proposal_id")
    proposal = proposal_manager.get_proposal(proposal_id) if proposal_id else None

    if proposal:
        trade_data = {
            "pair": proposal.pair.replace("/", ""),
            "strategy": proposal.strategy,
            "entry_price": proposal.entry_price,
            "take_profit": proposal.take_profit,
            "stop_loss": proposal.stop_loss,
            "amount": data.get("amount", Config.MAX_TRADE_AMOUNT),
            "proposal_id": proposal_id,
        }
    else:
        trade_data = data

    app_state["phase"] = "trading"
    emit("phase_change", {"phase": "trading"}, broadcast=True)
    emit("new_message", {
        "type": "system",
        "content": f"トレードを実行します: {trade_data.get('strategy', '').upper()} {trade_data.get('pair', '')}",
        "timestamp": datetime.now().isoformat(),
    }, broadcast=True)

    try:
        trade_info = trade_executor.execute_trade(trade_data)
        app_state["current_trade_id"] = trade_info["trade_id"]

        emit("trade_executed", trade_info, broadcast=True)
        emit("new_message", {
            "type": "system",
            "content": (
                f"注文実行完了: {trade_info['side']} {trade_info['symbol']} "
                f"数量={trade_info['quantity']:.8f} 価格={trade_info['entry_price']}"
            ),
            "timestamp": datetime.now().isoformat(),
        }, broadcast=True)

        # 監視開始
        trade_executor.start_monitoring(trade_info["trade_id"])

    except Exception as e:
        logger.error("トレード実行エラー: %s", e)
        emit("error", {"message": f"トレード実行エラー: {str(e)}"}, broadcast=True)
        emit("new_message", {
            "type": "system",
            "content": f"トレード実行エラー: {str(e)}",
            "timestamp": datetime.now().isoformat(),
        }, broadcast=True)


@socketio.on("stop_discussion")
def handle_stop_discussion():
    """議論を強制終了"""
    logger.info("議論終了リクエスト受信")

    orchestrator.stop()

    app_state["phase"] = "idle"
    app_state["online_ais"].clear()
    app_state["messages"].clear()
    app_state["current_proposal_id"] = None
    app_state["current_trade_id"] = None

    ai_manager.shutdown_all()

    emit("phase_change", {"phase": "idle"}, broadcast=True)
    emit("reset", {}, broadcast=True)


# ============================================================
# メイン実行
# ============================================================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    logger.info("""
    ======================================
      Project Parliament
      http://localhost:%d
    ======================================
    """, port)
    socketio.run(app, host="0.0.0.0", port=port, debug=Config.DEBUG)
