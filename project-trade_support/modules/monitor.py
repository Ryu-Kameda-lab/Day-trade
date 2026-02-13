"""
市場監視モジュール - 定期的に市場をスクリーニングし、有望な銘柄をAI分析・提案する
"""
import json
import time
from datetime import datetime
from pathlib import Path
import pandas as pd

from exchange.mexc_client import MEXCClient
from ai.llm_client import LLMClient
from modules.screener import ExpectedValueScreener
from modules.analyzer import Analyzer
from modules.strategist import Strategist
from modules.notifier import Notifier
from config.settings import PROJECT_ROOT


class MarketMonitor:
    """市場監視クラス"""

    def __init__(
        self,
        mexc_client: MEXCClient | None = None,
        llm_client: LLMClient | None = None,
        notifier: Notifier | None = None,
    ):
        self.client = mexc_client or MEXCClient()
        self.llm = llm_client or LLMClient()
        self.notifier = notifier or Notifier()
        self.screener = ExpectedValueScreener(self.client)
        self.analyzer = Analyzer(self.client, self.llm)
        self.strategist = Strategist(self.llm)

        # ログディレクトリ作成
        self.log_dir = PROJECT_ROOT / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def run_market_cycle(self) -> list[dict]:
        """
        市場監視サイクルを実行 (15分ごとに推奨)
        1. 期待値スクリーニング
        2. 上位3銘柄をAI分析
        3. 有望なら提案生成 & 通知
        4. ログ保存
        """
        print(f"[{datetime.now()}] 市場監視サイクル開始...")
        proposals = []

        # 1. 期待値スクリーニング
        try:
            # プログレスバー等はコンソール実行時はNoneでOK
            df = self.screener.run_screening()
        except Exception as e:
            error_msg = f"MEXCエラーのため候補銘柄無し: {e}"
            print(error_msg)
            # エラーログ保存
            self._save_proposals_to_log([{
                "timestamp": datetime.now().isoformat(),
                "symbol": "SYSTEM",
                "message": "MEXCエラーのため候補銘柄無し",
                "details": str(e),
                "type": "error"
            }])
            return []

        if df.empty:
            print("候補銘柄なし")
            return []

        # 上位3銘柄を抽出
        top_candidates = df.head(3)
        print(f"候補銘柄: {top_candidates['symbol'].tolist()}")

        for _, row in top_candidates.iterrows():
            symbol = row["symbol"]
            print(f"分析中: {symbol}...")
            
            # 2. AI分析
            # 15分足で分析
            analysis_result = self.analyzer.get_ai_analysis(symbol, "15m")
            
            # エラーチェック (analysis_result自体がエラー辞書の場合や、ai_analysisキーがない場合)
            if "error" in analysis_result:
                print(f"{symbol} 分析エラー: {analysis_result['error']}")
                self._save_proposals_to_log([{
                    "timestamp": datetime.now().isoformat(),
                    "symbol": symbol,
                    "message": "AI分析エラーのため分析無し",
                    "details": analysis_result['error'],
                    "type": "error"
                }])
                continue
                
            ai_data = analysis_result.get("ai_analysis", {})
            if not ai_data or "error" in ai_data:
                 print(f"{symbol} AI回答エラー: {ai_data.get('error')}")
                 self._save_proposals_to_log([{
                    "timestamp": datetime.now().isoformat(),
                    "symbol": symbol,
                    "message": "AI分析エラーのため分析無し",
                    "details": ai_data.get('error', 'Unknown AI error'),
                    "type": "error"
                }])
                 continue

            # 3. 提案生成
            strategy = self.strategist.generate_proposal(analysis_result)
            main_proposal_wrapper = strategy.get("proposal", {})
            # main_proposalは {"symbol":..., "current_price":..., "proposal": { "direction": ...} } の形式
            # あるいは strategist.generate_proposal が返すのは {"symbol":.., "proposal": ...}
            
            # generate_proposalの戻り値を確認:
            # return { "symbol": ..., "proposal": proposal_dict, ... }
            main_proposal = main_proposal_wrapper  # これが { "direction": ..., ... } のはず
            
            # strategist.generate_proposalの実装を見ると、
            # return { "symbol": ..., "proposal": proposal (dict from LLM) }
            # なので、strategy変数に入っているのはwrapper。
            # 下記で取り出す。
            
            # 修正: strategy = strategist.generate_proposal(...)
            # strategy["proposal"] が実際の提案内容
            main_content = strategy.get("proposal", {})
            
            direction = main_content.get("direction", "skip")
            confidence = main_content.get("confidence", "low")

            print(f"  -> {direction} (信頼度: {confidence})")

            # "見送り" 以外 かつ 信頼度 "中" 以上なら採用
            # confidenceは "high", "medium", "low"
            if direction != "skip" and confidence in ("medium", "high"):
                
                # セカンドオピニオン判定 (信頼度 "high" なら自動実行)
                second_opinion = None
                so_executed = False
                
                if confidence == "high":
                    print(f"  -> 信頼度Highのためセカンドオピニオン実行")
                    # strategy_full = self.strategist.generate_full_strategy... ではなく、
                    # 個別に呼ぶ
                    so_result = self.strategist.get_second_opinion(main_content, analysis_result)
                    second_opinion = so_result
                    so_executed = True
                
                # 提案データ構築
                proposal_data = {
                    "timestamp": datetime.now().isoformat(),
                    "symbol": symbol,
                    "price": row["price"],
                    "screening_score": row["total_score"],
                    "direction": direction,
                    "confidence": confidence,
                    # JSONシリアライズ可能な形にする必要あり
                    # analysis_result等はすでにdictなのでOK
                    "analysis": analysis_result,
                    "main_proposal": main_content,  # 提案本体
                    "second_opinion": second_opinion,
                    "so_executed": so_executed,
                    "gemini_review": None  # 後でGeminiが埋める
                }
                
                proposals.append(proposal_data)
                
                # 通知送信
                self._send_notification(proposal_data)

        # 4. ログ保存
        if proposals:
            self._save_proposals_to_log(proposals)
            print(f"{len(proposals)} 件の有効な提案をログ保存しました。")
        else:
            print("条件を満たす有効な提案はありませんでした。")

        return proposals

    def _send_notification(self, data: dict):
        """ユーザーへ通知"""
        symbol = data["symbol"]
        direction = data["direction"]
        conf = data["confidence"]
        so_executed = data["so_executed"]
        price = data["price"]
        
        main_p = data["main_proposal"]
        entry = main_p.get("entry_price", {}).get("ideal", "N/A")
        tp = main_p.get("take_profit", {}).get("tp1", "N/A")
        sl = main_p.get("stop_loss", {}).get("price", "N/A")
        reason = main_p.get("reasoning", "")
        if len(reason) > 100:
            reason = reason[:100] + "..."

        emoji = "🟢" if direction == "long" else "🔴"
        title = f"{emoji} {symbol} {direction.upper()} (信頼度: {conf})"
        
        # メッセージ分割 (Discord Embeds制限対策 & 可読性)
        # 1. 基本情報
        message_base = [
            f"**現在価格**: {price}",
            f"**エントリー**: {entry}",
            f"**TP**: {tp} / **SL**: {sl}",
        ]
        if so_executed:
             so = data.get("second_opinion", {})
             agreement = so.get("agreement", "N/A")
             message_base.append(f"\n🔄 **セカンドオピニオン**: {agreement}")

        self.notifier.send_alert(title, "\n".join(message_base), level="info")
        
        # 2. 根拠 (分割通知)
        reason = main_p.get("reasoning", "（根拠なし）")
        
        # 500文字ごとに分割して送信
        chunk_size = 500
        for i in range(0, len(reason), chunk_size):
            chunk = reason[i:i+chunk_size]
            part_title = f"📖 根拠 (Part {i//chunk_size + 1})"
            self.notifier.send_alert(part_title, chunk, level="info")

    def _save_proposals_to_log(self, proposals: list[dict]):
        """提案をログファイルに追記保存 (1時間ごとにローテーション)"""
        # ファイル名: proposals_YYYY-MM-DD_HH.json
        # 例: proposals_2024-02-13_15.json
        now = datetime.now()
        filename = f"proposals_{now.strftime('%Y-%m-%d_%H')}.json"
        
        # log_dirは pathlib.Path オブジェクト
        filepath = self.log_dir / filename

        # 既存データ読み込み
        current_data = []
        if filepath.exists():
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    current_data = json.load(f)
            except Exception as e:
                print(f"ログ読み込みエラー: {e}")

        # 追記
        current_data.extend(proposals)

        # 保存
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(current_data, f, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            print(f"ログ保存エラー: {e}")
            
    def get_latest_logs(self, limit: int = 50) -> list[dict]:
        """各種ログファイルからデータを読み込んで結合し、時系列逆順で返す"""
        # ファイル一覧を取得 (新しい順)
        # Reviewed_proposals_*.json と proposals_*.json の両方を取得する
        # globは複数パターン指定できないため、2回実行
        files_reviewed = list(self.log_dir.glob("Reviewed_proposals_*.json"))
        files_new = list(self.log_dir.glob("proposals_*.json"))
        
        # 文字列比較でソートできるよう、Reviewed_を取り除いたファイル名等で管理するか、単純に更新日時でソート
        all_files = sorted(files_reviewed + files_new, key=lambda x: x.name.replace("Reviewed_", ""), reverse=True)

        all_proposals = []
        for p in all_files:
            if len(all_proposals) >= limit:
                break
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # dataはリスト。逆順にして新しいものを先頭に
                    all_proposals.extend(reversed(data))
            except:
                continue
                
        return all_proposals[:limit]

