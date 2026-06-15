"""AI 工作状态浮窗。

启动后驻留桌面顶层，通过本地 HTTP API 接收 Claude Code hook 事件，
按 session_id 维护多个浮窗，每个浮窗两行展示：
  - 上行：最近收到的 message
  - 下行：当前状态（空闲中 / 工作中 / 待确认）

POST http://127.0.0.1:7878/event  body: {"event": "...", "session_id": "...", "message": "..."}
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

from PyQt5.QtCore import Qt, pyqtSignal, QObject, QTimer
from PyQt5.QtGui import QColor, QPainter, QBrush, QPen, QCursor, QIcon, QPixmap, QFont, QFontMetrics
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QMenu,
    QSystemTrayIcon,
    QWidget,
)


HTTP_HOST = "127.0.0.1"
HTTP_PORT = 7878

# 三种 UI 状态
ST_IDLE = "idle"
ST_WORKING = "working"
ST_CONFIRM = "confirm"

STATE_LABEL = {
    ST_IDLE: "空闲中",
    ST_WORKING: "工作中",
    ST_CONFIRM: "待确认",
}

STATE_COLOR = {
    ST_IDLE: QColor(140, 140, 145),
    ST_WORKING: QColor(70, 200, 95),
    ST_CONFIRM: QColor(240, 195, 50),
}

# Claude Code hook 事件（小写）
EV_SESSION_START = "sessionstart"
EV_USER_PROMPT = "userpromptsubmit"
EV_PRE_TOOL = "pretooluse"
EV_POST_TOOL = "posttooluse"
EV_STOP = "stop"
EV_SUBAGENT_STOP = "subagentstop"
EV_NOTIFICATION = "notification"
EV_SESSION_END = "sessionend"

VALID_EVENTS = {
    EV_SESSION_START, EV_USER_PROMPT, EV_PRE_TOOL, EV_POST_TOOL,
    EV_STOP, EV_SUBAGENT_STOP, EV_NOTIFICATION, EV_SESSION_END,
}

WORKING_EVENTS = {EV_USER_PROMPT, EV_PRE_TOOL, EV_POST_TOOL}
IDLE_EVENTS = {EV_STOP, EV_SUBAGENT_STOP}


class EventBus(QObject):
    """跨线程信号总线：HTTP 线程 → UI 线程。"""
    event_received = pyqtSignal(str, str, str)  # event, session_id, message


class StatusWindow(QWidget):
    """单个 session 的状态浮窗，两行展示：message + 状态。"""

    SIZE_H = 60
    MIN_W = 90
    MAX_W = 320
    PADDING = 10
    GAP = 4
    DOT_RESERVE = 14  # 右下角小圆点占用的横向空间

    def __init__(self, session_id: str):
        super().__init__()
        self.session_id = session_id
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)

        self._state = ST_IDLE
        self._message = ""
        self._last_event = EV_SESSION_START
        self.tag = ""

        self._msg_font = QFont()
        self._msg_font.setPointSize(9)
        self._state_font = QFont()
        self._state_font.setPointSize(11)
        self._state_font.setBold(True)

        self._drag_pos = None
        self._anchor_right = None
        self._anchor_top = None
        self._flash_on = False
        self._flash_timer = QTimer(self)
        self._flash_timer.setInterval(450)
        self._flash_timer.timeout.connect(self._toggle_flash)
        self._apply_size()

    # ---------- 状态切换 ----------

    def set_state(self, state: str):
        if state not in STATE_LABEL:
            return
        self._state = state
        self.setToolTip(self._tooltip_text())
        self._apply_size()
        if state == ST_CONFIRM:
            self.start_flash()
        else:
            self.stop_flash()
        self.update()

    def start_flash(self):
        self._flash_on = True
        if not self._flash_timer.isActive():
            self._flash_timer.start()

    def stop_flash(self):
        if self._flash_timer.isActive():
            self._flash_timer.stop()
        self._flash_on = False
        self.update()

    def _toggle_flash(self):
        self._flash_on = not self._flash_on
        self.update()

    def set_message(self, message: str):
        message = message or ""
        m = WindowManager._TAG_RE.search(message)
        if m:
            tag = m.group(1).strip()
            self.tag = tag
            rest = message[:m.start()].rstrip()
            message = "[{}] {}".format(tag, rest) if rest else "[{}]".format(tag)
        self._message = message
        self.setToolTip(self._tooltip_text())
        self._apply_size()
        self.update()

    def _apply_size(self):
        """根据 message 和状态文字宽度自适应浮窗宽度。"""
        msg = self._message or "(no message)"
        msg_w = QFontMetrics(self._msg_font).horizontalAdvance(msg)
        st_w = QFontMetrics(self._state_font).horizontalAdvance(
            STATE_LABEL.get(self._state, self._state)
        )
        text_w = max(msg_w, st_w)
        # 文字 + 左右内边距 + 状态色圆点占用空间
        target = text_w + 2 * self.PADDING + self.DOT_RESERVE
        target = max(self.MIN_W, min(self.MAX_W, target))
        if self.width() != target or self.height() != self.SIZE_H:
            self.setFixedSize(target, self.SIZE_H)
            if self._anchor_right is not None and self._anchor_top is not None:
                self.move(self._anchor_right - target, self._anchor_top)

    @property
    def state(self) -> str:
        return self._state

    @property
    def last_event(self) -> str:
        return self._last_event

    @last_event.setter
    def last_event(self, ev: str):
        self._last_event = ev

    def _tooltip_text(self):
        label = STATE_LABEL.get(self._state, self._state)
        head = "session={}".format(self.session_id[:8] if self.session_id else "?")
        if self._message:
            return "{}\n{}\n{}".format(head, label, self._message)
        return "{}\n{}".format(head, label)

    # ---------- 渲染 ----------

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()

        # 外框：圆角半透明黑底 + 状态色边框
        border_color = STATE_COLOR.get(self._state, QColor(120, 120, 130))
        if self._flash_on and self._state == ST_CONFIRM:
            # 闪烁时用状态色填充作为高亮帧
            bg = QColor(border_color)
            bg.setAlpha(220)
            p.setBrush(QBrush(bg))
        else:
            p.setBrush(QBrush(QColor(28, 28, 32, 230)))
        p.setPen(QPen(border_color, 1.8))
        p.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 8, 8)

        inner_w = w - 2 * self.PADDING
        row_h = (h - 2 * self.PADDING - self.GAP) // 2

        # 上行：message
        p.setFont(self._msg_font)
        p.setPen(QPen(QColor(225, 225, 230)))
        msg = self._message or "(no message)"
        msg = QFontMetrics(self._msg_font).elidedText(msg, Qt.ElideRight, inner_w)
        p.drawText(
            self.PADDING,
            self.PADDING,
            inner_w,
            row_h,
            Qt.AlignVCenter | Qt.AlignLeft,
            msg,
        )

        # 下行：状态文字（彩色加粗）
        p.setFont(self._state_font)
        p.setPen(QPen(STATE_COLOR.get(self._state, QColor(200, 200, 200))))
        p.drawText(
            self.PADDING,
            self.PADDING + row_h + self.GAP,
            inner_w,
            row_h,
            Qt.AlignVCenter | Qt.AlignLeft,
            STATE_LABEL.get(self._state, self._state),
        )

        # 状态色小圆点（右下角辅助标识）
        dot_r = 5
        cx = w - self.PADDING - dot_r
        cy = h - self.PADDING - row_h // 2
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(STATE_COLOR.get(self._state, QColor(150, 150, 150))))
        p.drawEllipse(cx - dot_r, cy - dot_r, dot_r * 2, dot_r * 2)

    # ---------- 鼠标交互 ----------

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, _event):
        self._drag_pos = None

    def contextMenuEvent(self, _event):
        menu = QMenu(self)
        menu.addAction("空闲中", lambda: self.set_state(ST_IDLE))
        menu.addAction("工作中", lambda: self.set_state(ST_WORKING))
        menu.addAction("待确认", lambda: self.set_state(ST_CONFIRM))
        menu.addSeparator()
        menu.addAction("关闭此浮窗", self.close)
        quit_act = QAction("退出程序", self)
        quit_act.triggered.connect(QApplication.instance().quit)
        menu.addAction(quit_act)
        menu.exec_(QCursor.pos())


class WindowManager(QObject):
    """按 session_id 管理多个浮窗，实现事件 → 状态的映射。"""

    def __init__(self):
        super().__init__()
        self._windows = {}  # session_id -> StatusWindow

    def handle_event(self, event: str, session_id: str, message: str):
        event = event.strip().lower()
        if event not in VALID_EVENTS:
            return
        # session_id 为空时，尝试用 message 末尾的 [tag] 找回已有窗口
        sid = session_id or self._sid_from_tag(message) or "default"

        if event == EV_SESSION_START:
            win = self._windows.get(sid)
            if win is None:
                win = StatusWindow(sid)
                self._windows[sid] = win
                self._place_window(win)
            win.set_state(ST_IDLE)
            if message:
                win.set_message(message)
            win.last_event = event
            win.show()
            return

        if event == EV_SESSION_END:
            win = self._windows.pop(sid, None)
            if win is not None:
                win.close()
                win.deleteLater()
            return

        # 其余事件需先有窗口；没有就懒创建一个，避免事件顺序异常时丢失反馈
        win = self._windows.get(sid)
        if win is None:
            win = StatusWindow(sid)
            self._windows[sid] = win
            self._place_window(win)
            win.show()

        if message:
            win.set_message(message)

        if event in WORKING_EVENTS:
            win.set_state(ST_WORKING)
            win.last_event = event
        elif event in IDLE_EVENTS:
            win.set_state(ST_IDLE)
            win.last_event = event
        elif event == EV_NOTIFICATION:
            # 仅在上一步不是 stop/subagentstop 时切到待确认
            if win.last_event not in IDLE_EVENTS:
                win.set_state(ST_CONFIRM)
                win.last_event = event

    def _place_window(self, win: StatusWindow):
        """新窗口在屏幕右上角向下堆叠，按右边缘对齐。"""
        screen = QApplication.primaryScreen().availableGeometry()
        existing = [w for w in self._windows.values() if w is not win and w.isVisible()]
        offset_y = 60 + len(existing) * (StatusWindow.SIZE_H + 8)
        right_edge = screen.right() - 20
        win.move(
            right_edge - win.width(),
            screen.top() + offset_y,
        )
        # 宽度后续变化时保持右边缘贴合
        win._anchor_right = right_edge
        win._anchor_top = screen.top() + offset_y

    def windows(self):
        return list(self._windows.values())

    _TAG_RE = re.compile(r"\[([^\[\]]+)\]\s*$")

    def _sid_from_tag(self, message: str) -> str:
        """从 message 末尾的 [tag] 抽出 tag，找到已有窗口的真实 session_id。
        notify.py 在每条 message 末尾加了 [<工作区名>] 标识源工作区，可作为备用 key。"""
        if not message:
            return ""
        m = self._TAG_RE.search(message)
        if not m:
            return ""
        tag = m.group(1).strip()
        if not tag:
            return ""
        # 优先匹配同 tag 已有窗口
        for sid, win in self._windows.items():
            if getattr(win, "tag", None) == tag:
                return sid
        # 没有就以 tag 自身作 sid（后续同 tag 事件都会落到一起）
        return "tag:" + tag


# ---------- HTTP 服务 ----------

def _sanitize(text: str) -> str:
    """剥掉孤立代理字符（notify.py 通过 surrogateescape 透传的非 UTF-8 字节），
    否则后续 print / Qt 渲染会抛 UnicodeEncodeError。"""
    if not text:
        return ""
    return text.encode("utf-8", "replace").decode("utf-8", "replace")


class EventHandler(BaseHTTPRequestHandler):
    bus = None  # 由 serve_http 注入

    def _json_response(self, code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        path = self.path.rstrip("/")
        if path not in ("/event", "/status"):
            self._json_response(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._json_response(400, {"error": "invalid json"})
            return
        event = str(data.get("event", "")).strip().lower()
        session_id = _sanitize(str(data.get("session_id", "") or ""))
        message = _sanitize(str(data.get("message", "") or ""))
        ts = datetime.now().strftime("%H:%M:%S")
        print(
            "[{ts}] hook <- {addr} event={event} sid={sid} message={msg}".format(
                ts=ts,
                addr=self.client_address[0],
                event=event or "<empty>",
                sid=(session_id[:8] + "..") if len(session_id) > 8 else (session_id or "<empty>"),
                msg=message or "<empty>",
            ),
            flush=True,
        )
        if event not in VALID_EVENTS:
            self._json_response(
                400,
                {"error": "event must be one of {}".format(sorted(VALID_EVENTS))},
            )
            return
        self.bus.event_received.emit(event, session_id, message)
        self._json_response(200, {"ok": True, "event": event})

    def do_GET(self):
        if self.path.rstrip("/") in ("", "/health"):
            self._json_response(200, {"ok": True})
            return
        self._json_response(404, {"error": "not found"})

    def log_message(self, *_args, **_kwargs):
        return


def serve_http(bus):
    handler_cls = type("BoundHandler", (EventHandler,), {"bus": bus})
    httpd = ThreadingHTTPServer((HTTP_HOST, HTTP_PORT), handler_cls)
    Thread(target=httpd.serve_forever, name="event-http", daemon=True).start()
    return httpd


# ---------- 托盘图标 ----------

def _tray_icon():
    pm = QPixmap(32, 32)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QBrush(QColor(30, 30, 35)))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(2, 2, 28, 28, 6, 6)
    # 两行示意
    p.setBrush(QBrush(QColor(220, 220, 225)))
    p.drawRect(6, 9, 20, 3)
    p.setBrush(QBrush(QColor(70, 200, 95)))
    p.drawRect(6, 19, 14, 4)
    p.end()
    return QIcon(pm)


def build_tray(manager: WindowManager):
    tray = QSystemTrayIcon(_tray_icon())
    menu = QMenu()

    def toggle_all():
        wins = manager.windows()
        if not wins:
            return
        any_visible = any(w.isVisible() for w in wins)
        for w in wins:
            w.setVisible(not any_visible)

    menu.addAction("显示/隐藏全部", toggle_all)
    menu.addSeparator()
    quit_act = QAction("退出", menu)
    quit_act.triggered.connect(QApplication.instance().quit)
    menu.addAction(quit_act)
    tray.setContextMenu(menu)
    tray.setToolTip("TaskMaster")
    tray.show()
    return tray


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    bus = EventBus()
    manager = WindowManager()
    bus.event_received.connect(manager.handle_event)

    serve_http(bus)
    tray = build_tray(manager)
    _ = tray

    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
