"""
Gemini レビュワーモジュール - 過去の取引提案を事後評価する
"""
import json
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

from exchange.mexc_client import MEXCClient
from ai.llm_client import LLMClient
from ai.prompts import SYSTEM_PROMPT, GEMINI_REVIEW_PROMPT
from config.settings import PROJECT_ROOT, is_configured

class GeminiReviewer:
    """過去ログの査読を行うクラス"""

    def __init__(self, mexc_client: MEXCClient | None = None, llm_client: LLMClient | None = None):
        self.client = mexc_client or MEXCClient()
        self.llm = llm_client or LLMClient()
        self.log_dir = PROJECT_ROOT / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def review_past_logs(self):
        """
        未査読のログファイルをチェックし、Geminiで評価を行う
        対象: 現在時刻より前の時間のログファイル (例: 今が15時なら14時以前のファイル)
        完了したファイルは "Reviewed_" プレフィックスを付ける
        """
        if not is_configured("GOOGLE_API_KEY"):
            print("Google APIキーが設定されていないため、査読をスキップします。")
            return

        print(f"[{datetime.now()}] Gemini査読サイクル開始...")

        # 対象ファイルを探す (Reviewed_ が付いていない、かつ現在の時間より前のもの)
        # ファイル名形式: proposals_YYYY-MM-DD_HH.json
        current_hour_str = datetime.now().strftime('%Y-%m-%d_%H')
        
        for filepath in self.log_dir.glob("proposals_*.json"):
            filename = filepath.name
            if filename.startswith("Reviewed_"):
                continue
                
            # ファイル名から日時を抽出して比較
            # proposals_2024-02-13_15.json -> 2024-02-13_15
            file_time_str = filename.replace("proposals_", "").replace(".json", "")
            
            # 文字列比較で十分 (YYYY-MM-DD_HH なので辞書順 = 時系列順)
            # 現在の時間("2024-02-13_16") よりも前の文字列なら過去のファイル
            if file_time_str >= current_hour_str:
                # 現在進行中のログはスキップ
                continue

            print(f"査読対象ファイルを発見: {filename}")
            self._process_file(filepath)

    def _process_file(self, filepath: Path):
        """1つのログファイルを処理"""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                proposals = json.load(f)
        except Exception as e:
            print(f"{filepath} 読み込みエラー: {e}")
            return

        updated = False
        all_reviewed = True  # 全て査読済みになったかフラグ

        for p in proposals:
            # 既にレビュー済みならスキップ
            if p.get("gemini_review"):
                continue

            # 提案データ
            symbol = p["symbol"]
            timestamp_str = p["timestamp"]  # isoformat
            direction = p["direction"]
            
            print(f"  - {symbol} ({timestamp_str}) を評価中...")

            # 市場データ取得 (提案時刻 〜 現在)
            # 1分足で取得して細かく見る
            market_outcome = self._fetch_market_outcome(symbol, timestamp_str)
            if not market_outcome:
                print("    市場データ取得失敗のためスキップ")
                all_reviewed = False
                continue

            # Geminiに評価させる
            review_result = self._ask_gemini(p, market_outcome)
            
            # Noneが返ってきた場合はエラーなのでセットせずスキップ (次回リトライ)
            if review_result is None:
                print("    Gemini評価失敗のためスキップ (次回リトライ)")
                all_reviewed = False
                continue

            p["gemini_review"] = review_result
            updated = True
            
            # APIレート制限考慮
            import time
            time.sleep(2)

        if updated:
            # 上書き保存
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(proposals, f, indent=2, ensure_ascii=False, default=str)
                print(f"  {filepath.name} を更新しました。")
            except Exception as e:
                print(f"  保存エラー: {e}")
                
        # 全てレビュー済みならリネーム
        if all_reviewed:
            new_name = "Reviewed_" + filepath.name
            new_path = filepath.with_name(new_name)
            try:
                filepath.rename(new_path)
                print(f"  完了: {new_name} にリネームしました。")
            except Exception as e:
                print(f"  リネームエラー: {e}")

    def _fetch_market_outcome(self, symbol: str, start_iso: str) -> dict | None:
        """提案後の市場データを取得して集計"""
        try:
            start_dt = datetime.fromisoformat(start_iso)
            # 現在までの経過時間(分)
            elapsed_min = int((datetime.now() - start_dt).total_seconds() / 60)
            
            if elapsed_min < 1:
                return None
                
            # MEXC APIでローソク足取得 (limit指定のみなので、多めに取ってフィルタする)
            # 1分足を使用
            limit = min(1000, elapsed_min + 60) # 余裕を持つ
            df = self.client.fetch_ohlcv(symbol, "1m", limit=limit)
            
            if df.empty:
                return None
                
            # start_dt 以降のデータを抽出
            # df.index は datetime
            mask = df.index >= start_dt
            df_slice = df[mask]
            
            if df_slice.empty:
                return None
                
            return {
                "highest": float(df_slice["high"].max()),
                "lowest": float(df_slice["low"].min()),
                "close": float(df_slice["close"].iloc[-1]),
                "start_price": float(df_slice["open"].iloc[0]),
            }
            
        except Exception as e:
            print(f"    Outcome取得エラー: {e}")
            return None

    def _ask_gemini(self, proposal_data: dict, market_data: dict) -> dict:
        """Geminiに評価を依頼"""
        main_p = proposal_data.get("main_proposal", {})
        direction = proposal_data.get("direction", "skip")
        
        entry = float(main_p.get("entry_price", {}).get("ideal", 0) or 0)
        tp1 = float(main_p.get("take_profit", {}).get("tp1", 0) or 0)
        sl = float(main_p.get("stop_loss", {}).get("price", 0) or 0)
        
        highest = market_data["highest"]
        lowest = market_data["lowest"]
        close = market_data["close"]
        
        # TP/SL到達判定 (簡易的)
        hit_tp = False
        hit_sl = False
        
        if direction == "long":
            if highest >= tp1: hit_tp = True
            if lowest <= sl: hit_sl = True
            max_profit_pct = (highest - entry) / entry * 100 if entry > 0 else 0
            max_loss_pct = (lowest - entry) / entry * 100 if entry > 0 else 0
        elif direction == "short":
            if lowest <= tp1: hit_tp = True
            if highest >= sl: hit_sl = True
            max_profit_pct = (entry - lowest) / entry * 100 if entry > 0 else 0
            max_loss_pct = (entry - highest) / entry * 100 if entry > 0 else 0
        else:
            max_profit_pct = 0
            max_loss_pct = 0

        # プロンプト作成
        prompt = GEMINI_REVIEW_PROMPT.format(
            timestamp=proposal_data["timestamp"],
            symbol=proposal_data["symbol"],
            direction=direction,
            entry_price=entry,
            tp=tp1,
            stop_loss=sl,
            reasoning=main_p.get("reasoning", ""),
            highest_price=highest,
            lowest_price=lowest,
            close_price=close,
            hit_tp="YES" if hit_tp else "NO",
            hit_sl="YES" if hit_sl else "NO",
            max_profit_pct=round(max_profit_pct, 2),
            max_loss_pct=round(max_loss_pct, 2),
        )

        # Geminiコール
        try:
            return self.llm.query_json(prompt, SYSTEM_PROMPT, provider="google")
        except Exception as e:
            print(f"    Gemini APIエラー: {e}")
            # エラー時はNoneを返し、保存しないことでリトライさせる
            return None
