"""トレード履歴 データモデル"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class PriceSnapshot:
    """監視中の価格スナップショット"""
    timestamp: datetime
    price: float
    rsi: Optional[float] = None
    macd_histogram: Optional[float] = None
    volume_ratio: Optional[float] = None
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "price": self.price,
            "rsi": self.rsi,
            "macd_histogram": self.macd_histogram,
            "volume_ratio": self.volume_ratio,
            "note": self.note,
        }


@dataclass
class TradeRecord:
    """トレード履歴レコード"""
    trade_id: str
    symbol: str
    strategy: str             # "long" / "short"
    entry_price: float
    close_price: Optional[float] = None
    take_profit: float = 0.0
    stop_loss: float = 0.0
    quantity: float = 0.0
    amount: float = 0.0
    status: str = "open"      # "open" / "partial_closed" / "closed"
    pnl: Optional[float] = None
    pnl_percent: Optional[float] = None
    close_reason: Optional[str] = None  # "tp_hit", "sl_hit", "trailing_stop", "manual", "timeout", "partial_tp"
    opened_at: datetime = field(default_factory=datetime.now)
    closed_at: Optional[datetime] = None
    price_history: List[PriceSnapshot] = field(default_factory=list)
    proposal_id: Optional[str] = None
    report_id: Optional[str] = None
    # トレイリングストップ用
    highest_price: Optional[float] = None   # 最高到達価格（ロング）
    lowest_price: Optional[float] = None    # 最低到達価格（ショート）
    trailing_stop_active: bool = False
    partial_closed: bool = False
    partial_close_price: Optional[float] = None
    partial_close_quantity: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "strategy": self.strategy,
            "entry_price": self.entry_price,
            "close_price": self.close_price,
            "take_profit": self.take_profit,
            "stop_loss": self.stop_loss,
            "quantity": self.quantity,
            "amount": self.amount,
            "status": self.status,
            "pnl": self.pnl,
            "pnl_percent": self.pnl_percent,
            "close_reason": self.close_reason,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "price_history": [p.to_dict() for p in self.price_history],
            "proposal_id": self.proposal_id,
            "report_id": self.report_id,
            "highest_price": self.highest_price,
            "lowest_price": self.lowest_price,
            "trailing_stop_active": self.trailing_stop_active,
            "partial_closed": self.partial_closed,
        }

    @property
    def unrealized_pnl(self) -> Optional[float]:
        """未実現損益を計算（直近のprice_historyから）"""
        if not self.price_history or self.status == "closed":
            return None
        last_price = self.price_history[-1].price
        if self.strategy == "long":
            return (last_price - self.entry_price) * self.quantity
        else:
            return (self.entry_price - last_price) * self.quantity

    @property
    def unrealized_pnl_percent(self) -> Optional[float]:
        """未実現損益率を計算"""
        if not self.price_history or self.status == "closed":
            return None
        last_price = self.price_history[-1].price
        if self.strategy == "long":
            return ((last_price - self.entry_price) / self.entry_price) * 100
        else:
            return ((self.entry_price - last_price) / self.entry_price) * 100
