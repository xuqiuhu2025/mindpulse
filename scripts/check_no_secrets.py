#!/usr/bin/env python
"""仓库密钥扫描：确保没有任何真实密钥被提交。

用法：python scripts/check_no_secrets.py [root]
退出码 0 = 通过；1 = 发现疑似密钥。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PATTERNS = {
    "OpenAI style key": re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    "AWS Access Key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "GitHub PAT": re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    "Slack token": re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    "Google API key": re.compile(r"AIza[0-9A-Za-z_-]{35}"),
    "GitLab PAT": re.compile(r"glpat-[A-Za-z0-9_-]{20,}"),
    "Private key block": re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}

ALLOWLIST = (
    "sk-your-placeholder",  # 文档示例
)

EXCLUDED_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", "DerivedData"}
EXCLUDED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2", ".ttf"}


def scan(root: Path) -> list[str]:
    findings: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in EXCLUDED_EXTENSIONS:
            continue
        if path.name == "check_no_secrets.py":
            continue  # 扫描器自身包含样例模式
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for name, pattern in PATTERNS.items():
            for match in pattern.finditer(content):
                token = match.group(0)
                if any(a in token for a in ALLOWLIST):
                    continue
                findings.append(f"{path.relative_to(root)}: {name} -> {token[:8]}***")
    return findings


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
    findings = scan(root)
    if findings:
        print("发现疑似密钥，提交被拒绝：")
        for f in findings:
            print(f"  - {f}")
        print("请把密钥移到 .env（不要提交），并考虑轮换已泄露的密钥。")
        return 1
    print("密钥扫描通过：未发现疑似密钥。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
