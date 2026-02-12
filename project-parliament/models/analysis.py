"""テクニカル分析 データモデル"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class TechnicalIndicators:
    """テクニカル指標の計算結果"""
    rsi: Optional[float] = None
    macd: Optional[Dict] = None            # {"macd", "signal", "histogram"}
    ema: Optional[Dict[str, float]] = None  # {"ema_9", "ema_21", "ema_50", "ema_200"}
    bollinger: Optional[Dict] = None        # {"upper", "middle", "lower", "width"}
    volume_ratio: Optional[float] = None    # 平均出来高に対する直近出来高の比率
    atr: Optional[float] = None             # Average True Range

    def to_dict(self) -> dict:
        return {
            "rsi": self.rsi,
            "macd": self.macd,
            "ema": self.ema,
            "bollinger": self.bollinger,
            "volume_ratio": self.volume_ratio,
            "atr": self.atr,
        }


@dataclass
class SymbolAnalysis:
    """1通貨ペアの分析結果"""
    symbol: str
    timeframe: str                             # "15m", "1h", "4h"
    indicators: TechnicalIndicators
    signals: List[str] = field(default_factory=list)   # 検出されたシグナル
    score: float = 0.0                         # スクリーニングスコア (0-100)
    summary: str = ""                          # テキストサマリー
    timestamp: datetime = field(default_factory=datetime.now)
    raw_price: Optional[float] = None          # 直近終値
    change_percent: Optional[float] = None     # 24h変動率

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "indicators": self.indicators.to_dict(),
            "signals": self.signals,
            "score": self.score,
            "summary": self.summary,
            "timestamp": self.timestamp.isoformat(),
            "raw_price": self.raw_price,
            "change_percent": self.change_percent,
        }


@dataclass
class MultiTimeframeAnalysis:
    """複数時間足を統合した分析結果"""
    symbol: str
    analyses: Dict[str, SymbolAnalysis] = field(default_factory=dict)  # timeframe -> SymbolAnalysis
    overall_score: float = 0.0
    overall_signals: List[str] = field(default_factory=list)
    recommendation: str = ""  # "strong_buy", "buy", "neutral", "sell", "strong_sell"
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "analyses": {tf: a.to_dict() for tf, a in self.analyses.items()},
            "overall_score": self.overall_score,
            "overall_signals": self.overall_signals,
            "recommendation": self.recommendation,
            "timestamp": self.timestamp.isoformat(),
        }
