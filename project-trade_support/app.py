"""
AI仮想通貨デイトレードアシスタント - エントリポイント

使用方法:
    streamlit run app.py
"""
import subprocess
import sys
import os


def main():
    """Streamlitダッシュボードを起動"""
    dashboard_path = os.path.join(os.path.dirname(__file__), "dashboard", "app.py")
    subprocess.run([
        sys.executable, "-m", "streamlit", "run",
        dashboard_path,
        "--server.port", "8501",
        "--browser.gatherUsageStats", "false",
    ])


if __name__ == "__main__":
    main()
