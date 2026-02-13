"""
自動売買ボット実行スクリプト
15分ごとに市場監視を行い、1時間ごとに過去ログの査読を行います。
"""
import time
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from modules.monitor import MarketMonitor
from modules.gemini_reviewer import GeminiReviewer

def job_monitor(monitor: MarketMonitor):
    print(f"\n[{datetime.now()}] --- 市場監視ジョブ開始 ---")
    try:
        monitor.run_market_cycle()
    except Exception as e:
        print(f"監視ジョブエラー: {e}")
    print(f"[{datetime.now()}] --- 市場監視ジョブ終了 ---\n")

def job_review(reviewer: GeminiReviewer):
    print(f"\n[{datetime.now()}] --- 査読ジョブ開始 ---")
    try:
        reviewer.review_past_logs()
    except Exception as e:
        print(f"査読ジョブエラー: {e}")
    print(f"[{datetime.now()}] --- 査読ジョブ終了 ---\n")

def main():
    print("AI Trading Bot - Scheduler Started")
    
    monitor = MarketMonitor()
    reviewer = GeminiReviewer()
    
    scheduler = BlockingScheduler()
    
    # 15分ごとに市場監視 (毎時 00, 15, 30, 45分に実行)
    scheduler.add_job(job_monitor, 'cron', minute='0,15,30,45', args=[monitor])
    
    # 1時間ごとに査読 (毎時 10分に実行 - ログ生成完了を待つため少しずらす)
    scheduler.add_job(job_review, 'cron', minute='10', args=[reviewer])
    
    # 初回起動時に即時実行するか確認（デバッグ用）
    # print("初回チェックを実行中...")
    # job_monitor(monitor)
    
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("Scheduler stopped.")

if __name__ == "__main__":
    main()
