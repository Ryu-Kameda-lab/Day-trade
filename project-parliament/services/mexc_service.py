"""
Project Parliament - MEXC取引所APIラッパー
MEXC Spot API v3 のREST APIクライアント
"""
import hashlib
import hmac
import time

import requests
from urllib.parse import urlencode

from config import Config
from utils.logger import get_logger

logger = get_logger("MEXCService")


class MEXCServiceError(Exception):
    """MEXC API固有のエラー"""
    pass


class MEXCService:
    """MEXC取引所のREST APIラッパー"""

    def __init__(
        self,
        api_key: str = None,
        secret_key: str = None,
        base_url: str = None,
        testnet: bool = None,
    ):
        self.api_key = api_key or Config.MEXC_API_KEY
        self.secret_key = secret_key or Config.MEXC_SECRET_KEY
        self.base_url = (base_url or "https://api.mexc.com").rstrip("/")
        self.testnet = testnet if testnet is not None else Config.MEXC_USE_TESTNET
        self._session = requests.Session()
        self._session.headers.update({
            "X-MEXC-APIKEY": self.api_key,
            "Content-Type": "application/json",
        })

        mode = "TESTNET" if self.testnet else "PRODUCTION"
        logger.info("MEXCService initialized [%s] base_url=%s", mode, self.base_url)

    # ------------------------------------------------------------------
    # 内部ヘルパー
    # ------------------------------------------------------------------
    def _generate_signature(self, params: dict) -> str:
        """
        HMAC-SHA256署名を生成する。

        Args:
            params: クエリパラメータ辞書

        Returns:
            16進数文字列の署名
        """
        query_string = urlencode(params)
        signature = hmac.new(
            self.secret_key.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return signature

    def _request(
        self,
        method: str,
        endpoint: str,
        params: dict = None,
        signed: bool = False,
    ) -> dict:
        """
        HTTP共通リクエストを実行する。

        Args:
            method: "GET", "POST", "DELETE"
            endpoint: APIエンドポイント（例: "/api/v3/ping"）
            params: クエリパラメータ
            signed: 署名が必要か

        Returns:
            APIレスポンスの辞書

        Raises:
            MEXCServiceError: API呼び出し失敗時
        """
        if not self.api_key and signed:
            raise MEXCServiceError("MEXC_API_KEY is not configured")
        if not self.secret_key and signed:
            raise MEXCServiceError("MEXC_SECRET_KEY is not configured")

        params = params or {}
        url = f"{self.base_url}{endpoint}"

        if signed:
            params["timestamp"] = int(time.time() * 1000)
            params["signature"] = self._generate_signature(params)

        logger.debug("%s %s params=%s signed=%s", method, endpoint, params, signed)

        try:
            if method == "GET":
                resp = self._session.get(url, params=params, timeout=10)
            elif method == "POST":
                resp = self._session.post(url, params=params, timeout=10)
            elif method == "DELETE":
                resp = self._session.delete(url, params=params, timeout=10)
            else:
                raise MEXCServiceError(f"Unsupported HTTP method: {method}")

            # レスポンスのログ
            logger.debug("Response [%d]: %s", resp.status_code, resp.text[:500])

            if resp.status_code != 200:
                raise MEXCServiceError(
                    f"API error {resp.status_code}: {resp.text}"
                )

            return resp.json()

        except requests.exceptions.RequestException as e:
            logger.error("Request failed: %s %s - %s", method, endpoint, e)
            raise MEXCServiceError(f"Request failed: {e}") from e

    # ------------------------------------------------------------------
    # パブリックAPI（署名不要）
    # ------------------------------------------------------------------
    def test_connection(self) -> bool:
        """
        MEXC APIへの接続テスト。

        Returns:
            接続成功ならTrue
        """
        try:
            self._request("GET", "/api/v3/ping")
            logger.info("Connection test: OK")
            return True
        except MEXCServiceError as e:
            logger.warning("Connection test failed: %s", e)
            return False

    def get_server_time(self) -> int:
        """
        MEXCサーバーの現在時刻を取得する。

        Returns:
            サーバー時刻（ミリ秒タイムスタンプ）
        """
        data = self._request("GET", "/api/v3/time")
        return data.get("serverTime", 0)

    def get_ticker_price(self, symbol: str) -> dict:
        """
        指定シンボルの現在価格を取得する。

        Args:
            symbol: 取引ペア（例: "BTCUSDT"）

        Returns:
            {"symbol": "BTCUSDT", "price": "12345.67"}
        """
        data = self._request("GET", "/api/v3/ticker/price", {"symbol": symbol})
        logger.info("Ticker price %s: %s", symbol, data.get("price"))
        return data

    def get_klines(self, symbol: str, interval: str, limit: int = 100) -> list:
        """
        ローソク足データを取得する。

        Args:
            symbol: 取引ペア
            interval: 時間足（"1m", "5m", "15m", "1h", "4h" etc.）
            limit: 取得件数（最大1000）

        Returns:
            ローソク足データのリスト
        """
        data = self._request("GET", "/api/v3/klines", {
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
        })
        logger.info("Klines %s %s: %d candles", symbol, interval, len(data))
        return data

    def get_ticker_24hr(self, symbol: str = None) -> list | dict:
        """
        24時間ティッカー統計を取得する。

        Args:
            symbol: 取引ペア（省略時は全ペア）

        Returns:
            単一ペアの場合はdict、全ペアの場合はlist
        """
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/api/v3/ticker/24hr", params)

    def get_market_overview(self, quote_asset: str = "USDT", limit: int = 50) -> dict:
        """
        市場の概要を取得する。USDT建て主要ペアのデータを返す。

        Args:
            quote_asset: 基軸通貨（デフォルト: "USDT"）
            limit: 返すペア数の上限（出来高順）

        Returns:
            {
                "pairs": [...],         # USDT建てペアの配列（出来高順）
                "total_pairs": int,     # フィルタ後の総ペア数
                "summary": str,         # 簡潔な概要メッセージ
            }
        """
        try:
            all_tickers = self.get_ticker_24hr()
        except MEXCServiceError as e:
            logger.error("Failed to get 24hr tickers: %s", e)
            return {"pairs": [], "total_pairs": 0, "summary": "市場データの取得に失敗しました"}

        # USDT建てペアのみ抽出し、出来高が一定以上のものをフィルタ
        usdt_tickers = []
        for t in all_tickers:
            sym = t.get("symbol", "")
            if not sym.endswith(quote_asset):
                continue
            try:
                volume = float(t.get("quoteVolume", 0))
                price_change_pct = float(t.get("priceChangePercent", 0))
                last_price = float(t.get("lastPrice", 0))
                high = float(t.get("highPrice", 0))
                low = float(t.get("lowPrice", 0))
                open_price = float(t.get("openPrice", 0))
            except (ValueError, TypeError):
                continue
            # 出来高が5万USDT未満のペアは除外（ノイズ排除）
            if volume < 50000 or last_price <= 0:
                continue
            usdt_tickers.append({
                "symbol": sym,
                "price": last_price,
                "open": open_price,
                "high": high,
                "low": low,
                "change_percent": price_change_pct,
                "volume_usdt": round(volume, 2),
            })

        # 出来高順にソートして上位を取得
        sorted_by_volume = sorted(usdt_tickers, key=lambda x: x["volume_usdt"], reverse=True)
        top_pairs = sorted_by_volume[:limit]

        summary = f"MEXC市場: {len(usdt_tickers)}ペア中、出来高上位{len(top_pairs)}ペアを取得しました。"
        logger.info("Market overview: %d USDT pairs, returning top %d", len(usdt_tickers), len(top_pairs))

        return {
            "pairs": top_pairs,
            "total_pairs": len(usdt_tickers),
            "summary": summary,
        }

    def get_order_book(self, symbol: str, limit: int = 20) -> dict:
        """
        板情報を取得する。

        Args:
            symbol: 取引ペア
            limit: 深さ（デフォルト20）

        Returns:
            {"bids": [...], "asks": [...]}
        """
        return self._request("GET", "/api/v3/depth", {
            "symbol": symbol,
            "limit": limit,
        })

    def get_multi_timeframe_klines(
        self,
        symbol: str,
        intervals: list = None,
        limit: int = 100,
    ) -> dict:
        """
        複数時間足のローソク足データを一括取得する。

        Args:
            symbol: 取引ペア（例: "BTCUSDT"）
            intervals: 時間足リスト（デフォルト: ["15m", "1h", "4h"]）
            limit: 各時間足のデータ件数

        Returns:
            {interval: klines_list} の辞書
        """
        if intervals is None:
            intervals = ["15m", "1h", "4h"]

        result = {}
        for interval in intervals:
            try:
                klines = self.get_klines(symbol, interval, limit)
                result[interval] = klines
                logger.debug(
                    "Multi-TF klines %s %s: %d candles",
                    symbol, interval, len(klines),
                )
            except MEXCServiceError as e:
                logger.warning(
                    "Failed to get klines %s %s: %s",
                    symbol, interval, e,
                )
                result[interval] = []
        return result

    def get_recent_trades(self, symbol: str, limit: int = 100) -> list:
        """
        直近の約定履歴を取得する。

        Args:
            symbol: 取引ペア（例: "BTCUSDT"）
            limit: 取得件数（最大1000）

        Returns:
            約定履歴のリスト
        """
        return self._request("GET", "/api/v3/trades", {
            "symbol": symbol,
            "limit": limit,
        })

    # ------------------------------------------------------------------
    # プライベートAPI（署名必要）
    # ------------------------------------------------------------------
    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: float = None,
    ) -> dict:
        """
        注文を作成する。

        Args:
            symbol: 取引ペア
            side: "BUY" or "SELL"
            order_type: "LIMIT" or "MARKET"
            quantity: 注文数量
            price: 指値価格（LIMITの場合必須）

        Returns:
            注文レスポンス
        """
        params = {
            "symbol": symbol,
            "side": side.upper(),
            "type": order_type.upper(),
            "quantity": str(quantity),
        }
        if order_type.upper() == "LIMIT" and price is not None:
            params["price"] = str(price)

        logger.info(
            "Placing order: %s %s %s qty=%s price=%s",
            symbol, side, order_type, quantity, price,
        )
        return self._request("POST", "/api/v3/order", params, signed=True)

    def get_open_orders(self, symbol: str = None) -> list:
        """
        オープン注文一覧を取得する。

        Args:
            symbol: 取引ペア（省略時は全ペア）

        Returns:
            注文リスト
        """
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/api/v3/openOrders", params, signed=True)

    def cancel_order(self, symbol: str, order_id: str) -> dict:
        """
        注文をキャンセルする。

        Args:
            symbol: 取引ペア
            order_id: 注文ID

        Returns:
            キャンセルレスポンス
        """
        logger.info("Cancelling order: symbol=%s order_id=%s", symbol, order_id)
        return self._request("DELETE", "/api/v3/order", {
            "symbol": symbol,
            "orderId": order_id,
        }, signed=True)

    def get_account_balance(self) -> dict:
        """
        アカウント残高を取得する。

        Returns:
            アカウント情報（残高一覧を含む）
        """
        return self._request("GET", "/api/v3/account", signed=True)

    def get_order_status(self, symbol: str, order_id: str) -> dict:
        """
        注文の状態を確認する。

        Args:
            symbol: 取引ペア
            order_id: 注文ID

        Returns:
            注文状態情報
        """
        return self._request("GET", "/api/v3/order", {
            "symbol": symbol,
            "orderId": order_id,
        }, signed=True)
