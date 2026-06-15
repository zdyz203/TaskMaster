#!/usr/bin/env python
"""Claude Code hook -> 浮窗事件推送。

Claude Code 会通过 stdin 给每个 hook 传一段 JSON，包含 hook_event_name、
session_id、tool_name 等字段。本脚本读 stdin 后把它转成 HTTP 推给浮窗。

settings.json 配置示例（所有 hook 复用同一条命令即可）：

  {
    "hooks": {
      "PreToolUse":       [{ "matcher": ".*", "hooks": [{ "type": "command", "command": "python D:\\\\path\\\\notify.py" }] }],
      "PostToolUse":      [{ "matcher": ".*", "hooks": [{ "type": "command", "command": "python D:\\\\path\\\\notify.py" }] }],
      "UserPromptSubmit": [{ "hooks": [{ "type": "command", "command": "python D:\\\\path\\\\notify.py" }] }],
      "Notification":     [{ "hooks": [{ "type": "command", "command": "python D:\\\\path\\\\notify.py" }] }],
      "Stop":             [{ "hooks": [{ "type": "command", "command": "python D:\\\\path\\\\notify.py" }] }],
      "SubagentStop":     [{ "hooks": [{ "type": "command", "command": "python D:\\\\path\\\\notify.py" }] }],
      "SessionStart":     [{ "hooks": [{ "type": "command", "command": "python D:\\\\path\\\\notify.py" }] }],
      "SessionEnd":       [{ "hooks": [{ "type": "command", "command": "python D:\\\\path\\\\notify.py" }] }]
    }
  }

也支持手动调试：

  python notify.py --event PreToolUse --session abc123 --message "Bash: ls"
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request

ENDPOINT = "http://127.0.0.1:7878/event"


def _source_tag() -> str:
    """标识本次推送来自哪个工作区。"""
    try:
        cur = os.path.abspath(os.getcwd())
    except OSError:
        return "[?]"
    home = os.path.abspath(os.path.expanduser("~"))
    path = cur
    while True:
        if path != home and (
            os.path.isdir(os.path.join(path, ".git"))
            or os.path.isdir(os.path.join(path, ".claude"))
        ):
            return "[{}]".format(os.path.basename(path) or path)
        parent = os.path.dirname(path)
        if parent == path:
            break
        path = parent
    return "[{}]".format(os.path.basename(cur.rstrip("\\/")) or cur)


def _read_stdin_payload() -> dict:
    """读 Claude Code hook 通过 stdin 传入的 JSON；非 hook 调用时返回 {}。"""
    if sys.stdin is None or sys.stdin.isatty():
        return {}
    # 用 buffer 走二进制 + errors='replace'，避免 hook payload 里夹带非 UTF-8
    # 字节（Windows console 默认 cp1252 文本模式会直接抛 UnicodeDecodeError，
    # 然后整段 payload 连同 session_id 一起被吞掉）。
    try:
        buf = getattr(sys.stdin, "buffer", None)
        if buf is not None:
            raw = buf.read().decode("utf-8", "replace")
        else:
            raw = sys.stdin.read()
    except Exception:
        return {}
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _build_message(hook: dict, override: str) -> str:
    if override:
        body = override
    else:
        parts = []
        tool = hook.get("tool_name")
        if tool:
            parts.append(str(tool))
        notif = hook.get("message")
        if notif:
            parts.append(str(notif))
        prompt = hook.get("prompt")
        if prompt:
            txt = str(prompt).strip().splitlines()[0]
            parts.append(txt[:60] + ("…" if len(txt) > 60 else ""))
        body = " | ".join(parts)
    tag = _source_tag()
    return "{} {}".format(body, tag) if body else tag


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", default="", help="覆盖 hook_event_name（手动调试用）")
    parser.add_argument("--session", default="", help="覆盖 session_id（手动调试用）")
    parser.add_argument("--message", default="", help="附加 message")
    # 兼容旧调用：python notify.py <event> [message...]
    parser.add_argument("positional", nargs="*", help=argparse.SUPPRESS)
    args = parser.parse_args(argv[1:])

    hook = _read_stdin_payload()

    event = args.event or hook.get("hook_event_name") or ""
    session_id = args.session or hook.get("session_id") or ""
    msg_override = args.message

    if args.positional:
        if not event:
            event = args.positional[0]
        extra = " ".join(args.positional[1:]).strip()
        if extra and not msg_override:
            msg_override = extra

    if not event:
        print("notify.py: missing event (no stdin hook payload, no --event)", file=sys.stderr)
        return 2

    payload = {
        "event": event,
        "session_id": session_id,
        "message": _build_message(hook, msg_override),
    }
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            resp.read()
    except Exception:
        # 浮窗未启动时不要打断主流程
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
