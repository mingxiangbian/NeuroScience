"""Run the local API; the frozen model environment is never modified."""
from pathlib import Path
import os
import sys

if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    os.chdir(root)
    if Path(sys.prefix).resolve() != (root / ".venv").resolve():
        raise SystemExit("请使用本模块 .venv/bin/python start.py，勿在冻结模型环境安装网站依赖。")
    from topicweb.staged_app import create_app
    import uvicorn
    app = create_app()
    print("本地工作台：http://127.0.0.1:8787")
    print(f"访问令牌文件：{root / 'private/access-token'}（仅本机可读）")
    uvicorn.run(app, host="127.0.0.1", port=8787, access_log=False)
