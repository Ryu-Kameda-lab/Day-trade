"""レポート データモデル"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class TradeReport:
    """トレード事後分析レポート"""
    report_id: str
    trade_id: str
    symbol: str
    strategy: str
    pnl: float
    pnl_percent: float
    duration: str                      # "2時間34分" のような表示用文字列
    entry_price: float
    close_price: float
    close_reason: str
    entry_analysis: Optional[Dict] = None   # エントリー時のテクニカル指標
    exit_analysis: Optional[Dict] = None    # クローズ時のテクニカル指標
    ai_analysis: str = ""              # AIによる事後要因分析テキスト
    lessons_learned: str = ""          # 改善ポイント
    price_history_summary: List[Dict] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "report_id": self.report_id,
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "strategy": self.strategy,
            "pnl": self.pnl,
            "pnl_percent": self.pnl_percent,
            "duration": self.duration,
            "entry_price": self.entry_price,
            "close_price": self.close_price,
            "close_reason": self.close_reason,
            "entry_analysis": self.entry_analysis,
            "exit_analysis": self.exit_analysis,
            "ai_analysis": self.ai_analysis,
            "lessons_learned": self.lessons_learned,
            "price_history_summary": self.price_history_summary,
            "created_at": self.created_at.isoformat(),
        }

    @property
    def result_label(self) -> str:
        """結果ラベル（表示用）"""
        if self.pnl > 0:
            return f"🟢 +${self.pnl:.2f} (+{self.pnl_percent:.2f}%)"
        elif self.pnl < 0:
            return f"🔴 -${abs(self.pnl):.2f} ({self.pnl_percent:.2f}%)"
        else:
            return "⚪ ±$0.00 (0.00%)"

    @property
    def close_reason_label(self) -> str:
        """クローズ理由の日本語ラベル"""
        labels = {
            "tp_hit": "利確目標到達",
            "sl_hit": "損切りライン到達",
            "trailing_stop": "トレイリングストップ",
            "manual": "手動クローズ",
            "timeout": "最大保有時間超過",
            "partial_tp": "部分利確",
        }
        return labels.get(self.close_reason, self.close_reason or "不明")
