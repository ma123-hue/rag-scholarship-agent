"""
启动脚本 —— 一键启动后端（及可选的前端）

用法：
    python run.py              # 仅启动后端
    python run.py --frontend   # 同时启动前端
    python run.py --reload     # 后端热重载模式（开发用）
    python run.py --help       # 查看全部选项
"""

import argparse
import os
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

PORT = 8000
HOST = "0.0.0.0"
FRONTEND_PORT = 5173
PROJECT_ROOT = Path(__file__).resolve().parent
VENV_PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"


def ensure_project_interpreter() -> None:
    """即使用户输入的是全局 python，也切换到项目 .venv，避免环境污染。"""
    if not VENV_PYTHON.exists():
        print(f"[ERROR] 未找到项目虚拟环境：{VENV_PYTHON}")
        print("    请在 PyCharm 中把解释器设置为 .venv\\Scripts\\python.exe")
        sys.exit(1)

    current = os.path.normcase(os.path.realpath(sys.executable))
    expected = os.path.normcase(os.path.realpath(VENV_PYTHON))
    if current != expected:
        print(f"[INFO] 当前解释器不是项目 .venv，正在自动切换：{VENV_PYTHON}")
        os.execv(
            str(VENV_PYTHON),
            [str(VENV_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]],
        )


def print_banner():
    print("=" * 58)
    print("  高校奖助学金申请评估与指导智能体系统")
    print("  DeepAgent + MCP + RAG + FastAPI + Vue3")
    print("=" * 58)


def check_env_file():
    env_path = PROJECT_ROOT / ".env"
    example_path = PROJECT_ROOT / ".env.example"
    if not env_path.exists():
        if example_path.exists():
            print("[!] 未发现 .env 文件，正在从 .env.example 复制...")
            import shutil
            shutil.copy2(example_path, env_path)
            print("[OK] 已创建 .env 文件，请根据需要修改其中的配置")
        else:
            print("[!] 未发现 .env 和 .env.example 文件，将使用默认配置")
    else:
        print("[OK] .env 文件已存在")


def check_dependencies():
    try:
        import uvicorn  # noqa: F401
        import fastapi  # noqa: F401
    except ImportError:
        print("[ERROR] 缺少依赖！请先运行：pip install -r requirements.txt")
        sys.exit(1)


def ensure_backend_port_available(host: str, port: int) -> None:
    """启动前明确检查端口，避免浏览器继续连接残留的旧后端。"""
    probe_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        if sock.connect_ex((probe_host, port)) == 0:
            print(f"[ERROR] 后端端口 {port} 已被占用，可能已有一套项目服务正在运行。")
            print("    请先停止旧的运行任务，再重新启动；不要同时运行两次 run.py。")
            sys.exit(1)


def start_backend(reload: bool, host: str = HOST, port: int = PORT):
    backend_dir = PROJECT_ROOT / "backend"

    print(f"[OK] 后端工作目录: {backend_dir}")
    print(f"[INFO] 启动 FastAPI 服务: http://{host}:{port}")
    if reload:
        print("[INFO] 热重载模式已开启（开发用）")

    cmd = [
        sys.executable, "-m", "uvicorn",
        "app.main:app",
        "--host", host,
        "--port", str(port),
    ]
    if reload:
        cmd.append("--reload")

    child_env = os.environ.copy()
    # 覆盖 PyCharm/系统中可能遗留的错误 PYTHONPATH（例如“代码backend”）。
    child_env["PYTHONPATH"] = str(backend_dir)
    proc = subprocess.Popen(cmd, cwd=str(backend_dir), env=child_env)
    return proc


def start_frontend():
    frontend_dir = PROJECT_ROOT / "frontend"
    if not (frontend_dir / "node_modules").exists():
        print("[INFO] 前端依赖未安装，正在安装（npm install）...")
        subprocess.run(["npm", "install"], cwd=str(frontend_dir), shell=True, check=True)

    print(f"[INFO] 启动前端 Vite 开发服务器: http://localhost:{FRONTEND_PORT}")
    proc = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=str(frontend_dir),
        shell=True,
    )
    return proc


def open_browser(port: int = PORT):
    time.sleep(2)
    webbrowser.open(f"http://localhost:{port}/docs")


def main():
    ensure_project_interpreter()
    parser = argparse.ArgumentParser(
        description="启动高校奖助学金评估系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run.py                    仅启动后端
  python run.py --frontend         同时启动前端
  python run.py --reload           开发模式（热重载）
  python run.py --no-browser       不自动打开浏览器
  python run.py --port 8080        自定义端口
        """,
    )
    parser.add_argument("--frontend", action="store_true", help="同时启动前端开发服务器")
    parser.add_argument("--reload", action="store_true", help="后端热重载模式（开发用）")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    parser.add_argument("--host", default=HOST, help=f"后端监听地址（默认 {HOST}）")
    parser.add_argument("--port", type=int, default=PORT, help=f"后端监听端口（默认 {PORT}）")

    args = parser.parse_args()

    print_banner()

    # 检查环境
    check_env_file()
    check_dependencies()
    ensure_backend_port_available(args.host, args.port)

    # 启动后端
    backend_proc = start_backend(reload=args.reload, host=args.host, port=args.port)

    # 启动前端（可选）
    frontend_proc = None
    if args.frontend:
        frontend_proc = start_frontend()

    print("\n" + "=" * 54)
    print("  系统启动中，按 Ctrl+C 停止所有服务")
    print("=" * 54 + "\n")

    try:
        # 等待后端进程结束
        backend_proc.wait()
    except KeyboardInterrupt:
        print("\n[!] 正在停止服务...")
        backend_proc.terminate()
        if frontend_proc:
            frontend_proc.terminate()
        print("[OK] 服务已停止")
        sys.exit(0)


if __name__ == "__main__":
    main()
