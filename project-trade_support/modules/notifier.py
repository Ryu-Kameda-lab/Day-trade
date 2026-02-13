"""
通知モジュール - Discord Webhookへの通知送信
"""
import json
import requests
from datetime import datetime
from config.settings import DISCORD_WEBHOOK_URL, is_configured


class Notifier:
    """Discord Webhook通知クラス"""

    def __init__(self, webhook_url: str = ""):
        self.webhook_url = webhook_url or DISCORD_WEBHOOK_URL
        self.history: list[dict] = []  # 通知履歴

    @property
    def is_configured(self) -> bool:
        return bool(self.webhook_url) and not self.webhook_url.startswith("your_")

    def send_alert(self, title: str, message: str, level: str = "info") -> bool:
        """
        アラート通知を送信

        Args:
            title: 通知タイトル
            message: 通知メッセージ
            level: info / warning / critical

        Returns:
            送信成功/失敗
        """
        # 履歴に追加
        notification = {
            "time": datetime.now().isoformat(),
            "title": title,
            "message": message,
            "level": level,
            "sent": False,
        }

        if not self.is_configured:
            notification["error"] = "Discord Webhook URLが未設定"
            self.history.append(notification)
            return False

        # Discord Embed カラー
        colors = {
            "info": 0x3498DB,      # 青
            "warning": 0xF39C12,   # オレンジ
            "critical": 0xE74C3C,  # 赤
        }

        # Discord Webhook送信
        payload = {
            "embeds": [{
                "title": title,
                "description": message,
                "color": colors.get(level, 0x95A5A6),
                "timestamp": datetime.utcnow().isoformat(),
                "footer": {"text": "AI Trading Assistant"},
            }]
        }

        try:
            resp = requests.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            notification["sent"] = resp.status_code in (200, 204)
            if not notification["sent"]:
                notification["error"] = f"HTTP {resp.status_code}"
        except Exception as e:
            notification["error"] = str(e)

        self.history.append(notification)
        return notification["sent"]

    def send_trade_proposal(self, proposal: dict) -> bool:
        """取引提案をDiscordに通知"""
        symbol = proposal.get("symbol", "N/A")
        p = proposal.get("proposal", {})
        direction = p.get("direction", "skip")

        if direction == "skip":
            title = f"📊 {symbol} - 取引見送り"
        else:
            emoji = "🟢" if direction == "long" else "🔴"
            title = f"{emoji} {symbol} - {direction.upper()} 提案"

        lines = []
        if direction != "skip":
            entry = p.get("entry_price", {})
            tp = p.get("take_profit", {})
            sl = p.get("stop_loss", {})
            lines.append(f"**エントリー**: {entry.get('ideal', 'N/A')}")
            lines.append(f"**TP1**: {tp.get('tp1', 'N/A')} / **TP2**: {tp.get('tp2', 'N/A')}")
            lines.append(f"**SL**: {sl.get('price', 'N/A')}")
            lines.append(f"**R:R比**: 1:{p.get('risk_reward_ratio', 'N/A')}")
            lines.append(f"**信頼度**: {p.get('confidence', 'N/A')}")

        reasoning = p.get("reasoning", "")
        if reasoning:
            lines.append(f"\n{reasoning}")

        return self.send_alert(title, "\n".join(lines), level="info")

    def send_periodic_report(self, positions: list[dict]) -> bool:
        """定期レポート送信"""
        if not positions:
            return self.send_alert(
                "📋 定期レポート",
                "現在アクティブなポジションはありません。",
                level="info",
            )

        lines = [f"**アクティブポジション数**: {len(positions)}\n"]
        for pos in positions:
            emoji = "🟢" if pos.get("direction") == "long" else "🔴"
            pnl = pos.get("pnl_pct", 0)
            pnl_emoji = "📈" if pnl >= 0 else "📉"
            lines.append(
                f"{emoji} **{pos.get('symbol', 'N/A')}** "
                f"({pos.get('direction', 'N/A').upper()}) "
                f"{pnl_emoji} {pnl:+.2f}%"
            )

        return self.send_alert("📋 定期レポート", "\n".join(lines), level="info")

    def get_history(self, limit: int = 50) -> list[dict]:
        """通知履歴を取得"""
        return list(reversed(self.history[-limit:]))
