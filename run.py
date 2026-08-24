#!/usr/bin/env python3
"""便捷入口：python run.py --once / --serve / --web

自动把项目根加入 sys.path，使 `from src...` 可用。
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from src.main import main  # noqa: E402

if __name__ == "__main__":
    main()
