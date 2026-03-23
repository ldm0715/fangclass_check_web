"""打包脚本 — 使用 PyInstaller 将项目打包为可执行程序"""

import subprocess
import sys

# 确保在非 UTF-8 环境（如 GitHub Actions）中也能正常输出中文
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def main():
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "build.spec",
        "--clean",
        "--noconfirm",
    ]

    print("=" * 50)
    print("  开始打包...")
    print(f"  命令: {' '.join(cmd)}")
    print("=" * 50)

    result = subprocess.run(cmd)

    if result.returncode == 0:
        print()
        print("=" * 50)
        print("  打包成功！")
        print("  输出目录: dist/方课提问记录查询/")
        print("  运行: dist/方课提问记录查询/方课提问记录查询.exe")
        print()
        print("=" * 50)
    else:
        print("打包失败，请检查错误信息")
        sys.exit(1)


if __name__ == "__main__":
    main()
