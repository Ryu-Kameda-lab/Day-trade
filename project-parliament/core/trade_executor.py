"""
Project Parliament - トレード実行・監視エンジン
稟議書に基づく注文実行、リアルタイムポジション監視（30秒ポーリング）、
トレイリングストップ、部分利確、自動決済を行う。
"""
import time
import uuid
from datetime import datetime
from typing import Optional, Callable

import gevent

from config import Config
from models.trade import TradeRecord, PriceSnapshot
from utils.logger import get_logger

logger = get_logger("TradeExecutor")


class TradeExecutorError(Exception):
    """トレード実行固有のエラー"""
    pass


class TradeExecutor:
    """
    稟議書に基づくトレードの実行と監視を行う。

    改修ポイント（Phase C）:
        - 30秒間隔のリアルタイムポーリング監視
        - トレイリングストップ（2%利益で発動、1%距離）
        - 部分利確（TP距離50%到達で半量決済）
        - TradeRecord モデルによる履歴管理
        - テクニカル指標付き価格スナップショット
    """

    # デフォルト設定（Config から上書き可能）
    MONITOR_INTERVAL = 30           # ポーリング間隔（秒）
    MAX_DURATION = 14400            # 最大保有時間（秒 = 4時間）
    TRAILING_STOP_TRIGGER = 0.02    # トレイリングストップ発動閾値 (2%)
    TRAILING_STOP_DISTANCE = 0.01   # トレイリングストップ距離 (1%)
    PARTIAL_TP_RATIO = 0.5          # 部分利確比率 (50%)
    PARTIAL_TP_TRIGGER = 0.5        # TP距離の50%で発動

    def __init__(self, mexc_service, emit_callback=None, analyzer=None, config=None):
        """
        Args:
            mexc_service: MEXCService インスタンス
            emit_callback: WebSocketイベント送信用コールバック
            analyzer: TechnicalAnalyzer インスタンス（監視中のテクニカル指標取得用）
            config: Config オブジェクト（設定値上書き用）
        """
        self.mexc = mexc_service
        self.emit = emit_callback
        self.analyzer = analyzer
        self.active_trades: dict = {}       # trade_id -> trade_info (dict, 後方互換)
        self.trade_records: dict = {}       # trade_id -> TradeRecord
        self.closed_trades: list = []       # クローズ済みTradeRecordのリスト
        self.on_trade_closed: Optional[Callable] = None  # クローズ後のコールバック

        # Config 設定の読み込み
        if config:
            self.MONITOR_INTERVAL = getattr(config, "MONITOR_INTERVAL", self.MONITOR_INTERVAL)
            self.MAX_DURATION = getattr(config, "MAX_DURATION", self.MAX_DURATION)
            self.TRAILING_STOP_TRIGGER = getattr(config, "TRAILING_STOP_TRIGGER", self.TRAILING_STOP_TRIGGER)
            self.TRAILING_STOP_DISTANCE = getattr(config, "TRAILING_STOP_DISTANCE", self.TRAILING_STOP_DISTANCE)
            self.PARTIAL_TP_RATIO = getattr(config, "PARTIAL_TP_RATIO", self.PARTIAL_TP_RATIO)
            self.PARTIAL_TP_TRIGGER = getattr(config, "PARTIAL_TP_TRIGGER", self.PARTIAL_TP_TRIGGER)

    def _notify(self, event: str, data: dict):
        """WebSocketイベントを送信する（コールバックが設定されている場合）"""
        if self.emit:
            try:
                self.emit(event, data)
            except Exception as e:
                logger.warning("Failed to emit event %s: %s", event, e)

    def execute_trade(self, proposal: dict) -> dict:
        """
        稟議書に基づいて注文を実行する。

        Args:
            proposal: 稟議書辞書。以下のキーを含む:
                - pair: 取引ペア（例: "BTCUSDT"）
                - strategy: "long" or "short"
                - entry_price: エントリー価格
                - take_profit: 利確価格
                - stop_loss: 損切価格
                - amount: 取引金額（USDT）
                - proposal_id: 稟議書ID（任意）

        Returns:
            トレード情報辞書

        Raises:
            TradeExecutorError: 実行エラー
        """
        trade_id = str(uuid.uuid4())[:8]
        symbol = proposal.get("pair", "")
        strategy = proposal.get("strategy", "").lower()
        entry_price = float(proposal.get("entry_price", 0))
        take_profit = float(proposal.get("take_profit", 0))
        stop_loss = float(proposal.get("stop_loss", 0))
        amount = float(proposal.get("amount", 0))
        proposal_id = proposal.get("proposal_id")

        # バリデーション
        if not symbol:
            raise TradeExecutorError("pair is required in proposal")
        if strategy not in ("long", "short"):
            raise TradeExecutorError(f"Invalid strategy: {strategy}")
        if entry_price <= 0:
            raise TradeExecutorError("entry_price must be positive")

        # 取引金額上限チェック
        if amount > Config.MAX_TRADE_AMOUNT:
            raise TradeExecutorError(
                f"Trade amount {amount} exceeds MAX_TRADE_AMOUNT ({Config.MAX_TRADE_AMOUNT})"
            )
        if amount <= 0:
            raise TradeExecutorError("Trade amount must be positive")

        # ロング → BUY、ショート → SELL
        side = "BUY" if strategy == "long" else "SELL"

        # 数量を算出（entry_priceベース）
        quantity = amount / entry_price

        logger.info(
            "Executing trade [%s]: %s %s %s qty=%.8f entry=%.2f tp=%.2f sl=%.2f",
            trade_id, side, symbol, strategy, quantity, entry_price, take_profit, stop_loss,
        )

        # 注文を発行
        try:
            order_result = self.mexc.place_order(
                symbol=symbol,
                side=side,
                order_type="LIMIT",
                quantity=quantity,
                price=entry_price,
            )
        except Exception as e:
            logger.error("Order placement failed [%s]: %s", trade_id, e)
            raise TradeExecutorError(f"Order placement failed: {e}") from e

        order_id = order_result.get("orderId", "")

        # TradeRecord を作成
        record = TradeRecord(
            trade_id=trade_id,
            symbol=symbol,
            strategy=strategy,
            entry_price=entry_price,
            take_profit=take_profit,
            stop_loss=stop_loss,
            quantity=quantity,
            amount=amount,
            status="open",
            opened_at=datetime.now(),
            proposal_id=proposal_id,
            highest_price=entry_price if strategy == "long" else None,
            lowest_price=entry_price if strategy == "short" else None,
        )
        self.trade_records[trade_id] = record

        # 後方互換用のトレード情報辞書
        trade_info = {
            "trade_id": trade_id,
            "order_id": order_id,
            "symbol": symbol,
            "side": side,
            "strategy": strategy,
            "quantity": quantity,
            "entry_price": entry_price,
            "take_profit": take_profit,
            "stop_loss": stop_loss,
            "amount": amount,
            "status": "open",
            "opened_at": datetime.now().isoformat(),
            "closed_at": None,
            "close_reason": None,
            "close_price": None,
            "pnl": None,
            "order_result": order_result,
        }
        self.active_trades[trade_id] = trade_info

        self._notify("trade_executed", {
            "trade_id": trade_id,
            "symbol": symbol,
            "side": side,
            "strategy": strategy,
            "entry_price": entry_price,
            "take_profit": take_profit,
            "stop_loss": stop_loss,
            "quantity": quantity,
        })

        logger.info("Trade opened [%s]: order_id=%s", trade_id, order_id)
        return trade_info

    def start_monitoring(self, trade_id: str):
        """
        トレードの監視をバックグラウンドで開始する。
        30秒間隔のリアルタイムポーリング方式。

        Args:
            trade_id: 監視対象のトレードID
        """
        if trade_id not in self.active_trades:
            logger.warning("Cannot monitor unknown trade: %s", trade_id)
            return

        logger.info("Starting real-time monitoring for trade [%s] (interval: %ds)", trade_id, self.MONITOR_INTERVAL)
        gevent.spawn(self._monitor_loop, trade_id)

    def _monitor_loop(self, trade_id: str):
        """
        リアルタイム監視ループ（30秒ポーリング）。
        各チェックでTP/SL判定、トレイリングストップ、部分利確を実行する。
        """
        trade = self.active_trades.get(trade_id)
        record = self.trade_records.get(trade_id)
        if not trade:
            return

        symbol = trade["symbol"]
        take_profit = trade["take_profit"]
        stop_loss = trade["stop_loss"]
        strategy = trade["strategy"]
        start_time = time.time()
        check_count = 0

        logger.info(
            "Monitor loop started [%s]: %s %s entry=%.6f tp=%.6f sl=%.6f",
            trade_id, strategy, symbol, trade["entry_price"], take_profit, stop_loss,
        )

        while True:
            # トレードがまだアクティブか確認
            trade = self.active_trades.get(trade_id)
            if not trade or trade["status"] not in ("open", "partial_closed"):
                logger.info("Trade [%s] no longer active, stopping monitor", trade_id)
                return

            # 最大保有時間チェック
            elapsed = time.time() - start_time
            if elapsed >= self.MAX_DURATION:
                logger.info("Trade [%s] reached max duration (%.0fs), force closing", trade_id, elapsed)
                self.close_position(trade_id, "timeout")
                return

            # ポーリング間隔待機
            gevent.sleep(self.MONITOR_INTERVAL)
            check_count += 1

            # 現在価格を取得
            try:
                ticker = self.mexc.get_ticker_price(symbol)
                current_price = float(ticker.get("price", 0))
            except Exception as e:
                logger.warning("Failed to get price [%s] check #%d: %s", trade_id, check_count, e)
                self._notify("trade_monitor_error", {
                    "trade_id": trade_id,
                    "check_count": check_count,
                    "error": str(e),
                })
                continue

            # テクニカル指標のスナップショットを取得（analyzerがある場合）
            snapshot = self._create_price_snapshot(symbol, current_price)
            if record:
                record.price_history.append(snapshot)

            # 含み損益を計算
            if strategy == "long":
                unrealized_pnl = (current_price - trade["entry_price"]) * trade["quantity"]
                pnl_percent = ((current_price - trade["entry_price"]) / trade["entry_price"]) * 100
            else:
                unrealized_pnl = (trade["entry_price"] - current_price) * trade["quantity"]
                pnl_percent = ((trade["entry_price"] - current_price) / trade["entry_price"]) * 100

            # 時間ラベル
            elapsed_min = int(elapsed / 60)
            time_label = f"{elapsed_min}min" if elapsed_min < 60 else f"{elapsed_min // 60}h{elapsed_min % 60}m"

            logger.info(
                "Monitor [%s] #%d (%s): price=%.6f pnl=%.4f (%.2f%%) tp=%.6f sl=%.6f",
                trade_id, check_count, time_label,
                current_price, unrealized_pnl, pnl_percent,
                take_profit, stop_loss,
            )

            # WebSocket: リアルタイム更新を送信
            self._notify("trade_monitor_update", {
                "trade_id": trade_id,
                "check_count": check_count,
                "time_label": time_label,
                "current_price": current_price,
                "entry_price": trade["entry_price"],
                "take_profit": take_profit,
                "stop_loss": stop_loss,
                "unrealized_pnl": round(unrealized_pnl, 4),
                "pnl_percent": round(pnl_percent, 2),
                "strategy": strategy,
                "rsi": snapshot.rsi,
                "volume_ratio": snapshot.volume_ratio,
                "trailing_stop_active": record.trailing_stop_active if record else False,
                "partial_closed": record.partial_closed if record else False,
            })

            # --- TP/SL 判定 ---
            if strategy == "long":
                if current_price >= take_profit:
                    self.close_position(trade_id, "tp_hit")
                    return
                if current_price <= stop_loss:
                    self.close_position(trade_id, "sl_hit")
                    return
            else:  # short
                if current_price <= take_profit:
                    self.close_position(trade_id, "tp_hit")
                    return
                if current_price >= stop_loss:
                    self.close_position(trade_id, "sl_hit")
                    return

            # --- トレイリングストップ ---
            if record and self._check_trailing_stop(record, current_price):
                logger.info("Trailing stop triggered [%s] at %.6f", trade_id, current_price)
                self.close_position(trade_id, "trailing_stop")
                return

            # --- 部分利確 ---
            if record and not record.partial_closed:
                if self._should_partial_take_profit(trade, current_price):
                    self._partial_take_profit(trade_id)

    def _create_price_snapshot(self, symbol: str, current_price: float) -> PriceSnapshot:
        """テクニカル指標付きの価格スナップショットを作成する"""
        rsi = None
        macd_hist = None
        vol_ratio = None

        if self.analyzer:
            try:
                # 直近の15分足データで簡易分析
                klines = self.mexc.get_klines(symbol, "15m", 50)
                analysis = self.analyzer.analyze(klines, symbol, "15m")
                rsi = analysis.indicators.rsi
                if analysis.indicators.macd:
                    macd_hist = analysis.indicators.macd.get("histogram")
                vol_ratio = analysis.indicators.volume_ratio
            except Exception as e:
                logger.debug("Snapshot analysis failed for %s: %s", symbol, e)

        return PriceSnapshot(
            timestamp=datetime.now(),
            price=current_price,
            rsi=rsi,
            macd_histogram=macd_hist,
            volume_ratio=vol_ratio,
        )

    def _check_trailing_stop(self, record: TradeRecord, current_price: float) -> bool:
        """
        トレイリングストップの判定と更新を行う。

        Returns:
            True: トレイリングストップ発動（ポジションクローズすべき）
            False: 発動しない
        """
        entry = record.entry_price

        if record.strategy == "long":
            # 利益率を計算
            profit_pct = (current_price - entry) / entry

            # トリガー閾値を超えたらトレイリングストップ有効化
            if profit_pct >= self.TRAILING_STOP_TRIGGER:
                if not record.trailing_stop_active:
                    record.trailing_stop_active = True
                    record.highest_price = current_price
                    logger.info(
                        "Trailing stop activated [%s] at %.6f (profit: %.2f%%)",
                        record.trade_id, current_price, profit_pct * 100,
                    )
                    return False

                # 最高価格を更新
                if current_price > record.highest_price:
                    record.highest_price = current_price

                # トレイリングストップラインからの下落判定
                trailing_line = record.highest_price * (1 - self.TRAILING_STOP_DISTANCE)
                if current_price <= trailing_line:
                    return True

        else:  # short
            profit_pct = (entry - current_price) / entry

            if profit_pct >= self.TRAILING_STOP_TRIGGER:
                if not record.trailing_stop_active:
                    record.trailing_stop_active = True
                    record.lowest_price = current_price
                    logger.info(
                        "Trailing stop activated [%s] at %.6f (profit: %.2f%%)",
                        record.trade_id, current_price, profit_pct * 100,
                    )
                    return False

                if current_price < record.lowest_price:
                    record.lowest_price = current_price

                trailing_line = record.lowest_price * (1 + self.TRAILING_STOP_DISTANCE)
                if current_price >= trailing_line:
                    return True

        return False

    def _should_partial_take_profit(self, trade: dict, current_price: float) -> bool:
        """部分利確の条件を判定する"""
        entry = trade["entry_price"]
        tp = trade["take_profit"]
        strategy = trade["strategy"]

        if strategy == "long":
            tp_distance = tp - entry
            current_profit = current_price - entry
            if tp_distance > 0 and current_profit > 0:
                return (current_profit / tp_distance) >= self.PARTIAL_TP_TRIGGER
        else:
            tp_distance = entry - tp
            current_profit = entry - current_price
            if tp_distance > 0 and current_profit > 0:
                return (current_profit / tp_distance) >= self.PARTIAL_TP_TRIGGER

        return False

    def _partial_take_profit(self, trade_id: str):
        """部分利確を実行する（指定比率分を成行決済）"""
        trade = self.active_trades.get(trade_id)
        record = self.trade_records.get(trade_id)
        if not trade or not record:
            return

        close_qty = trade["quantity"] * self.PARTIAL_TP_RATIO
        close_side = "SELL" if trade["side"] == "BUY" else "BUY"

        logger.info(
            "Partial TP [%s]: closing %.8f (%.0f%%) of position",
            trade_id, close_qty, self.PARTIAL_TP_RATIO * 100,
        )

        try:
            ticker = self.mexc.get_ticker_price(trade["symbol"])
            partial_close_price = float(ticker.get("price", 0))

            self.mexc.place_order(
                symbol=trade["symbol"],
                side=close_side,
                order_type="MARKET",
                quantity=close_qty,
            )

            # 残りの数量を更新
            trade["quantity"] = trade["quantity"] - close_qty
            trade["status"] = "partial_closed"

            record.partial_closed = True
            record.partial_close_price = partial_close_price
            record.partial_close_quantity = close_qty

            self._notify("trade_partial_tp", {
                "trade_id": trade_id,
                "close_qty": close_qty,
                "close_price": partial_close_price,
                "remaining_qty": trade["quantity"],
            })

            logger.info(
                "Partial TP completed [%s]: closed %.8f at %.6f, remaining %.8f",
                trade_id, close_qty, partial_close_price, trade["quantity"],
            )

        except Exception as e:
            logger.error("Partial TP failed [%s]: %s", trade_id, e)

    def close_position(self, trade_id: str, reason: str) -> dict:
        """
        ポジションを決済する。

        Args:
            trade_id: トレードID
            reason: 決済理由 ("tp_hit", "sl_hit", "trailing_stop", "manual", "timeout")

        Returns:
            更新されたトレード情報

        Raises:
            TradeExecutorError: 決済エラー
        """
        trade = self.active_trades.get(trade_id)
        if not trade:
            raise TradeExecutorError(f"Trade not found: {trade_id}")
        if trade["status"] == "closed":
            raise TradeExecutorError(f"Trade {trade_id} is already closed")

        record = self.trade_records.get(trade_id)
        symbol = trade["symbol"]
        quantity = trade["quantity"]

        # 決済注文（エントリーの逆注文）
        close_side = "SELL" if trade["side"] == "BUY" else "BUY"

        logger.info(
            "Closing position [%s]: %s %s qty=%.8f reason=%s",
            trade_id, close_side, symbol, quantity, reason,
        )

        try:
            # 現在価格を取得
            ticker = self.mexc.get_ticker_price(symbol)
            close_price = float(ticker.get("price", 0))

            # 成行決済
            close_result = self.mexc.place_order(
                symbol=symbol,
                side=close_side,
                order_type="MARKET",
                quantity=quantity,
            )
        except Exception as e:
            logger.error("Failed to close position [%s]: %s", trade_id, e)
            raise TradeExecutorError(f"Close position failed: {e}") from e

        # 損益計算
        entry_price = trade["entry_price"]
        if trade["strategy"] == "long":
            pnl = (close_price - entry_price) * quantity
        else:
            pnl = (entry_price - close_price) * quantity

        pnl_percent = (pnl / trade["amount"]) * 100 if trade["amount"] else 0

        # 部分利確済みの場合、部分利確分のPnLを加算
        if record and record.partial_closed and record.partial_close_price:
            if trade["strategy"] == "long":
                partial_pnl = (record.partial_close_price - entry_price) * record.partial_close_quantity
            else:
                partial_pnl = (entry_price - record.partial_close_price) * record.partial_close_quantity
            pnl += partial_pnl

        now = datetime.now()

        # トレード情報を更新（後方互換）
        trade["status"] = "closed"
        trade["closed_at"] = now.isoformat()
        trade["close_reason"] = reason
        trade["close_price"] = close_price
        trade["pnl"] = round(pnl, 4)
        trade["close_result"] = close_result

        # TradeRecord を更新
        if record:
            record.status = "closed"
            record.closed_at = now
            record.close_reason = reason
            record.close_price = close_price
            record.pnl = round(pnl, 4)
            record.pnl_percent = round(pnl_percent, 2)
            self.closed_trades.append(record)

        pnl_label = f"+{pnl:.4f}" if pnl >= 0 else f"{pnl:.4f}"
        logger.info(
            "Position closed [%s]: reason=%s close_price=%.6f pnl=%s (%.2f%%)",
            trade_id, reason, close_price, pnl_label, pnl_percent,
        )

        self._notify("trade_closed", {
            "trade_id": trade_id,
            "reason": reason,
            "close_price": close_price,
            "pnl": trade["pnl"],
            "pnl_percent": round(pnl_percent, 2),
        })

        # クローズ後のコールバック（レポート生成用）
        if self.on_trade_closed and record:
            try:
                gevent.spawn(self.on_trade_closed, record)
            except Exception as e:
                logger.warning("on_trade_closed callback error: %s", e)

        return trade

    def get_trade_status(self, trade_id: str) -> dict:
        """トレードの現在の状況を取得する。"""
        trade = self.active_trades.get(trade_id)
        if not trade:
            return {"error": f"Trade not found: {trade_id}"}

        record = self.trade_records.get(trade_id)

        result = {
            "trade_id": trade["trade_id"],
            "symbol": trade["symbol"],
            "side": trade["side"],
            "strategy": trade["strategy"],
            "entry_price": trade["entry_price"],
            "take_profit": trade["take_profit"],
            "stop_loss": trade["stop_loss"],
            "status": trade["status"],
            "opened_at": trade["opened_at"],
            "trailing_stop_active": record.trailing_stop_active if record else False,
            "partial_closed": record.partial_closed if record else False,
        }

        # オープン中の場合は現在価格を付加
        if trade["status"] in ("open", "partial_closed"):
            try:
                ticker = self.mexc.get_ticker_price(trade["symbol"])
                current_price = float(ticker.get("price", 0))
                result["current_price"] = current_price

                # 含み損益
                if trade["strategy"] == "long":
                    unrealized_pnl = (current_price - trade["entry_price"]) * trade["quantity"]
                else:
                    unrealized_pnl = (trade["entry_price"] - current_price) * trade["quantity"]
                result["unrealized_pnl"] = round(unrealized_pnl, 4)
            except Exception as e:
                logger.warning("Failed to get current price for status: %s", e)
                result["current_price"] = None
                result["unrealized_pnl"] = None

        return result

    def get_trade_result(self, trade_id: str) -> dict:
        """完了したトレードの結果（損益計算）を取得する。"""
        trade = self.active_trades.get(trade_id)
        if not trade:
            return {"error": f"Trade not found: {trade_id}"}

        result = {
            "trade_id": trade["trade_id"],
            "symbol": trade["symbol"],
            "strategy": trade["strategy"],
            "side": trade["side"],
            "quantity": trade["quantity"],
            "entry_price": trade["entry_price"],
            "status": trade["status"],
            "opened_at": trade["opened_at"],
        }

        if trade["status"] == "closed":
            result.update({
                "close_price": trade["close_price"],
                "close_reason": trade["close_reason"],
                "closed_at": trade["closed_at"],
                "pnl": trade["pnl"],
                "pnl_percent": round(
                    (trade["pnl"] / trade["amount"]) * 100, 2
                ) if trade["amount"] else 0,
            })
        else:
            result["message"] = "Trade is still open"

        return result

    def get_all_open_trades(self) -> list:
        """全オープントレードのリストを返す"""
        return [
            self.get_trade_status(tid)
            for tid, t in self.active_trades.items()
            if t["status"] in ("open", "partial_closed")
        ]

    def get_trade_history(self) -> list:
        """クローズ済みトレードの履歴を返す"""
        return [r.to_dict() for r in self.closed_trades]

    def get_trade_record(self, trade_id: str) -> Optional[TradeRecord]:
        """TradeRecord を取得する（レポート生成用）"""
        return self.trade_records.get(trade_id)
