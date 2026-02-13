"""
MEXC APIクライアント - ccxt経由でMEXC先物APIに接続
"""
import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from config.settings import MEXC_API_KEY, MEXC_SECRET_KEY


class MEXCClient:
    """MEXC取引所APIラッパー"""

    def __init__(self, api_key: str = "", secret_key: str = ""):
        self.api_key = api_key or MEXC_API_KEY
        self.secret_key = secret_key or MEXC_SECRET_KEY

        # ccxt MEXC インスタンス（先物）
        self.exchange = ccxt.mexc({
            "apiKey": self.api_key,
            "secret": self.secret_key,
            "options": {"defaultType": "swap"},  # 先物取引
            "enableRateLimit": True,
        })

    def fetch_futures_symbols(self) -> list[dict]:
        """全先物銘柄のシンボル情報を取得"""
        try:
            markets = self.exchange.load_markets()
            futures = []
            for symbol, market in markets.items():
                if market.get("swap") and market.get("active"):
                    futures.append({
                        "symbol": symbol,
                        "base": market.get("base", ""),
                        "quote": market.get("quote", ""),
                        "info": market,
                    })
            return futures
        except Exception as e:
            print(f"[MEXCClient] 先物銘柄取得エラー: {e}")
            return []

    def fetch_tickers(self) -> dict:
        """全先物銘柄のティッカー情報を取得"""
        try:
            tickers = self.exchange.fetch_tickers()
            # swapのみフィルタ
            swap_tickers = {}
            for symbol, ticker in tickers.items():
                if ":USDT" in symbol or symbol.endswith("/USDT"):
                    swap_tickers[symbol] = ticker
            return swap_tickers
        except Exception as e:
            print(f"[MEXCClient] ティッカー取得エラー: {e}")
            return {}

    def fetch_ohlcv(
        self, symbol: str, timeframe: str = "15m", limit: int = 200
    ) -> pd.DataFrame:
        """OHLCVデータ（ローソク足）を取得してDataFrameで返す"""
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            if not ohlcv:
                return pd.DataFrame()

            df = pd.DataFrame(
                ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
            )
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df.set_index("timestamp", inplace=True)
            return df
        except Exception as e:
            print(f"[MEXCClient] OHLCV取得エラー ({symbol}, {timeframe}): {e}")
            return pd.DataFrame()

    def fetch_current_price(self, symbol: str) -> float | None:
        """現在価格を取得"""
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return ticker.get("last")
        except Exception as e:
            print(f"[MEXCClient] 現在価格取得エラー ({symbol}): {e}")
            return None

    def fetch_order_book(self, symbol: str, limit: int = 20) -> dict:
        """オーダーブックを取得"""
        try:
            return self.exchange.fetch_order_book(symbol, limit)
        except Exception as e:
            print(f"[MEXCClient] オーダーブック取得エラー ({symbol}): {e}")
            return {"bids": [], "asks": []}

    def fetch_ticker_detail(self, symbol: str) -> dict:
        """個別銘柄のティッカー詳細を取得"""
        try:
            return self.exchange.fetch_ticker(symbol)
        except Exception as e:
            print(f"[MEXCClient] ティッカー詳細取得エラー ({symbol}): {e}")
            return {}

    def fetch_funding_rate(self, symbol: str) -> dict:
        """資金調達率（Funding Rate）を取得"""
        try:
            rates = self.exchange.fetch_funding_rate(symbol)
            return {
                "symbol": symbol,
                "funding_rate": rates.get("fundingRate", 0),
                "next_funding_time": rates.get("fundingDatetime"),
            }
        except Exception as e:
            print(f"[MEXCClient] Funding Rate取得エラー ({symbol}): {e}")
            return {"symbol": symbol, "funding_rate": 0}

    def fetch_open_interest(self, symbol: str) -> dict:
        """未決済建玉（Open Interest）を取得 — MEXC ticker APIから算出"""
        import requests

        try:
            # ccxt シンボル (例: BTC/USDT:USDT) → MEXC契約名 (例: BTC_USDT)
            base = symbol.split("/")[0]
            contract_symbol = f"{base}_USDT"

            # ticker API から holdVol（建玉枚数）を取得
            ticker_url = "https://contract.mexc.com/api/v1/contract/ticker"
            ticker_resp = requests.get(ticker_url, params={"symbol": contract_symbol}, timeout=8)

            if ticker_resp.status_code != 200:
                return {"symbol": symbol, "open_interest": 0, "open_interest_value": 0}

            ticker_data = ticker_resp.json()
            if not ticker_data.get("success") or not ticker_data.get("data"):
                return {"symbol": symbol, "open_interest": 0, "open_interest_value": 0}

            td = ticker_data["data"]
            hold_vol = float(td.get("holdVol", 0) or 0)
            last_price = float(td.get("lastPrice", 0) or 0)

            # contract detail から contractSize を取得してOI金額を算出
            detail_url = "https://contract.mexc.com/api/v1/contract/detail"
            detail_resp = requests.get(detail_url, params={"symbol": contract_symbol}, timeout=8)
            contract_size = 1.0
            if detail_resp.status_code == 200:
                detail_data = detail_resp.json()
                if detail_data.get("success") and detail_data.get("data"):
                    contract_size = float(detail_data["data"].get("contractSize", 1) or 1)

            oi_value = hold_vol * contract_size * last_price

            return {
                "symbol": symbol,
                "open_interest": hold_vol,
                "open_interest_value": oi_value,
            }
        except Exception as e:
            print(f"[MEXCClient] OI取得エラー ({symbol}): {e}")
            return {"symbol": symbol, "open_interest": 0, "open_interest_value": 0}

    def fetch_orderbook_depth(self, symbol: str, limit: int = 20) -> dict:
        """
        オーダーブックの深さ・スプレッドを計算して返す
        """
        try:
            ob = self.exchange.fetch_order_book(symbol, limit)
            bids = ob.get("bids", [])
            asks = ob.get("asks", [])

            if not bids or not asks:
                return {"symbol": symbol, "spread": 0, "depth_bid": 0, "depth_ask": 0, "spread_pct": 0}

            best_bid = bids[0][0]
            best_ask = asks[0][0]
            spread = best_ask - best_bid
            mid_price = (best_ask + best_bid) / 2
            spread_pct = (spread / mid_price * 100) if mid_price > 0 else 0

            # 板の厚み（数量合計）
            depth_bid = sum(b[1] for b in bids)
            depth_ask = sum(a[1] for a in asks)

            # 板の厚み（金額換算）
            depth_bid_value = sum(b[0] * b[1] for b in bids)
            depth_ask_value = sum(a[0] * a[1] for a in asks)

            return {
                "symbol": symbol,
                "best_bid": best_bid,
                "best_ask": best_ask,
                "spread": round(spread, 8),
                "spread_pct": round(spread_pct, 4),
                "depth_bid": round(depth_bid, 4),
                "depth_ask": round(depth_ask, 4),
                "depth_bid_value": round(depth_bid_value, 2),
                "depth_ask_value": round(depth_ask_value, 2),
                "depth_total_value": round(depth_bid_value + depth_ask_value, 2),
            }
        except Exception as e:
            print(f"[MEXCClient] オーダーブック深度取得エラー ({symbol}): {e}")
            return {"symbol": symbol, "spread": 0, "depth_bid": 0, "depth_ask": 0, "spread_pct": 0}

