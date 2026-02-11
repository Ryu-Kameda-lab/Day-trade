"""
🏛️ Project Parliament - メインアプリケーション
Flask + Flask-SocketIO によるリアルタイムAI議論プラットフォーム
"""
import os
import json
from datetime import datetime

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit

from config import Config, AI_PROFILES

# ============================================================
# Flask アプリケーション初期化
# ============================================================
app = Flask(__name__)
app.config.from_object(Config)

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="eventlet",  # 非同期モード（eventlet使用）
)

# ============================================================
# アプリケーション状態（インメモリ）
# ============================================================
app_state = {
    "phase": "idle",       # idle → activated → discussing → voting → reviewing → trading → complete
    "online_ais": set(),   # オンラインのAI IDセット
    "messages": [],        # チャット履歴
    "current_proposal": None,  # 現在の稟議書
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


# ============================================================
# WebSocket イベント
# ============================================================
@socketio.on("connect")
def handle_connect():
    """クライアント接続時"""
    print(f"[WS] クライアント接続: {request.sid}")
    emit("state_update", {
        "phase": app_state["phase"],
        "online_ais": list(app_state["online_ais"]),
    })


@socketio.on("disconnect")
def handle_disconnect():
    """クライアント切断時"""
    print(f"[WS] クライアント切断: {request.sid}")


@socketio.on("activate_all_ai")
def handle_activate_all():
    """
    全AIを起動するリクエスト
    Phase 1 では接続テストのモック動作を実装
    """
    print("[CMD] 全AI起動リクエスト受信")

    # 全AIを順番にオンラインにする（実際にはAPI接続テスト）
    import time

    for ai_id, profile in AI_PROFILES.items():
        # 接続中ステータスを送信
        emit("ai_status_change", {
            "ai_id": ai_id,
            "status": "connecting",
            "name": profile["name"],
        }, broadcast=True)

        # Phase 2以降: ここで実際のAPI接続テストを行う
        socketio.sleep(0.3)  # モックの接続遅延

        # オンラインに変更
        app_state["online_ais"].add(ai_id)
        emit("ai_status_change", {
            "ai_id": ai_id,
            "status": "online",
            "name": profile["name"],
        }, broadcast=True)

        # システムメッセージ
        sys_msg = {
            "type": "system",
            "content": f"{profile['icon']} {profile['name']}（{profile['role_label']}）がオンラインになりました",
            "timestamp": datetime.now().isoformat(),
        }
        app_state["messages"].append(sys_msg)
        emit("new_message", sys_msg, broadcast=True)

    # 全AI起動完了
    app_state["phase"] = "activated"
    emit("phase_change", {"phase": "activated"}, broadcast=True)
    emit("new_message", {
        "type": "system",
        "content": "✅ 全AI（11体）の起動が完了しました。チャート画像をアップロードして議論を開始してください。",
        "timestamp": datetime.now().isoformat(),
    }, broadcast=True)


@socketio.on("start_discussion")
def handle_start_discussion(data):
    """
    議論開始リクエスト
    data: { "images": [...] }  ← アップロードされた画像データ
    """
    print("[CMD] 議論開始リクエスト受信")

    app_state["phase"] = "discussing"
    emit("phase_change", {"phase": "discussing"}, broadcast=True)

    # システムメッセージ
    image_count = data.get("image_count", 0)
    emit("new_message", {
        "type": "system",
        "content": f"📊 議論を開始します。{image_count}枚のチャート画像が全AIに共有されました。",
        "timestamp": datetime.now().isoformat(),
    }, broadcast=True)

    # Phase 3以降: ここでオーケストレーターが議論フローを開始する
    # TODO: orchestrator.start_discussion(images)


@socketio.on("stop_discussion")
def handle_stop_discussion():
    """議論を強制終了"""
    print("[CMD] 議論終了リクエスト受信")

    app_state["phase"] = "idle"
    app_state["online_ais"].clear()
    app_state["messages"].clear()
    app_state["current_proposal"] = None

    emit("phase_change", {"phase": "idle"}, broadcast=True)
    emit("reset", {}, broadcast=True)


# ============================================================
# メイン実行
# ============================================================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"""
    ╔══════════════════════════════════════════╗
    ║  🏛️  Project Parliament                 ║
    ║  http://localhost:{port}                  ║
    ╚══════════════════════════════════════════╝
    """)
    socketio.run(app, host="0.0.0.0", port=port, debug=Config.DEBUG)
