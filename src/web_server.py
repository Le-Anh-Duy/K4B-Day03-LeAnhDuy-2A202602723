"""
🌐 WEB UI BACKEND (DAY 03 LAB) — ReAct Agent Chat Demo

API server siêu nhẹ dùng 100% thư viện chuẩn Python (http.server), phục vụ:
  - Giao diện React tĩnh trong thư mục web/
  - REST API thông tin Provider / MCP Tools / Test Cases
  - Streaming (SSE) toàn bộ Thought - Action - Observation và console log
    của ReAct Agent theo thời gian thực
  - Lưu / tải lịch sử chat ra file JSON

Chạy:  python src/web_server.py
"""

import argparse
import io
import json
import mimetypes
import os
import sys
import threading
import time
import webbrowser
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from app import load_test_cases, run_react_agent
from mcp_server import MCPLibraryServer
from prompts import MAX_ITERATIONS, REACT_AGENT_SYSTEM_PROMPT
from providers import get_llm_provider

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_DIR = os.path.join(BASE_DIR, "web")
HISTORY_PATH = os.path.join(WEB_DIR, "chat_history.json")

# Trace của Web UI ghi ra file riêng, KHÔNG đè lên docs/trace_waterfall.json
# (đó là artifact của `python src/app.py --all` dùng để nộp Lab).
WEB_TRACE_PATH = os.path.join(BASE_DIR, "docs", "trace_waterfall_web.json")

# Agent chạy tuần tự: stdout là tài nguyên toàn cục nên chỉ phục vụ 1 request mỗi lượt.
AGENT_LOCK = threading.Lock()

PROVIDER = None
MCP_SERVER = None


# ==============================================================================
# SSE HELPER
# ==============================================================================

class SSEWriter:
    """File-like object: gom stdout của Agent theo từng dòng rồi đẩy ra SSE."""

    def __init__(self, emit):
        self._emit = emit
        self._buffer = ""

    def write(self, text: str) -> int:
        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            self._emit("log", {"line": line})
        return len(text)

    def flush(self):
        if self._buffer:
            self._emit("log", {"line": self._buffer})
            self._buffer = ""


# ==============================================================================
# HTTP HANDLER
# ==============================================================================

class LabRequestHandler(BaseHTTPRequestHandler):

    protocol_version = "HTTP/1.1"
    server_version = "VinUniLabWeb/1.0"

    # ---------------------------------------------------------------- utilities

    def log_message(self, fmt, *args):
        """Tắt access log mặc định cho đỡ rối terminal."""
        pass

    def _send_json(self, payload, status: int = 200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: str):
        if not os.path.isfile(path):
            self._send_json({"error": "Not found"}, status=404)
            return
        ctype, _ = mimetypes.guess_type(path)
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        raw = self.rfile.read(length).decode("utf-8", errors="replace")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    # --------------------------------------------------------------------- GET

    def do_GET(self):
        route = urlparse(self.path).path

        if route == "/api/meta":
            self._handle_meta()
            return

        if route == "/api/history":
            self._send_json(load_history())
            return

        # Static files (React app)
        rel = "index.html" if route in ("/", "") else route.lstrip("/")
        target = os.path.normpath(os.path.join(WEB_DIR, rel))
        if not target.startswith(WEB_DIR):          # chặn path traversal
            self._send_json({"error": "Forbidden"}, status=403)
            return
        self._send_file(target)

    # -------------------------------------------------------------------- POST

    def do_POST(self):
        route = urlparse(self.path).path

        if route == "/api/chat":
            self._handle_chat()
            return

        if route == "/api/history":
            save_history(self._read_json_body())
            self._send_json({"ok": True})
            return

        self._send_json({"error": "Not found"}, status=404)

    # ---------------------------------------------------------------- /api/meta

    def _handle_meta(self):
        try:
            test_cases = load_test_cases()
        except Exception:
            test_cases = []

        suggestions = [
            {
                "id": tc.get("id"),
                "question": tc.get("question"),
                "complexity": tc.get("complexity"),
                "type": tc.get("type"),
                "expected_behavior": tc.get("expected_behavior"),
            }
            for tc in test_cases
            if not str(tc.get("question", "")).strip().startswith("TODO")
        ]

        self._send_json({
            "provider": PROVIDER.__class__.__name__,
            "model": getattr(PROVIDER, "model_name", "unknown"),
            "mcp_server": MCP_SERVER.server_name,
            "mcp_version": MCP_SERVER.version,
            "max_iterations": MAX_ITERATIONS,
            "system_prompt": REACT_AGENT_SYSTEM_PROMPT.strip(),
            "tools": MCP_SERVER.list_tools(),
            "test_cases": suggestions,
        })

    # ---------------------------------------------------------------- /api/chat

    def _handle_chat(self):
        payload = self._read_json_body()
        message = str(payload.get("message", "")).strip()

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True

        broken = {"flag": False}

        def emit(event: str, data: dict):
            """Đẩy một frame SSE xuống browser ngay lập tức."""
            if broken["flag"]:
                return
            frame = "event: %s\ndata: %s\n\n" % (
                event,
                json.dumps(data, ensure_ascii=False),
            )
            try:
                self.wfile.write(frame.encode("utf-8"))
                self.wfile.flush()
            except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError, OSError):
                broken["flag"] = True

        if not message:
            emit("error", {"message": "Câu hỏi đang trống."})
            emit("done", {"trace": [], "answer": "", "duration_ms": 0})
            return

        if not AGENT_LOCK.acquire(timeout=120):
            emit("error", {"message": "Agent đang bận xử lý một yêu cầu khác."})
            emit("done", {"trace": [], "answer": "", "duration_ms": 0})
            return

        started = time.time()
        trace = []
        try:
            emit("start", {"message": message, "max_iterations": MAX_ITERATIONS})
            writer = SSEWriter(emit)
            try:
                with redirect_stdout(writer):
                    trace = run_react_agent(
                        message,
                        PROVIDER,
                        MCP_SERVER,
                        on_event=lambda entry: emit("trace", entry),
                    )
                    save_web_trace(trace)
            finally:
                writer.flush()
        except Exception as exc:          # demo UI cần nhìn thấy lỗi thay vì chết ngầm
            emit("error", {"message": "%s: %s" % (exc.__class__.__name__, exc)})
        finally:
            AGENT_LOCK.release()

        answer = ""
        for entry in reversed(trace):
            if entry.get("action_type") in (
                "FINAL_ANSWER",
                "MAX_ITERATIONS_REACHED",
                "EXECUTION_ERROR",
            ):
                answer = entry.get("output", "")
                break

        emit("done", {
            "trace": trace,
            "answer": answer,
            "duration_ms": round((time.time() - started) * 1000, 2),
        })


# ==============================================================================
# WATERFALL TRACE (RIÊNG CHO WEB UI)
# ==============================================================================

def save_web_trace(trace_data: list):
    """Ghi Waterfall Trace của phiên chat web ra docs/trace_waterfall_web.json."""
    os.makedirs(os.path.dirname(WEB_TRACE_PATH), exist_ok=True)
    with io.open(WEB_TRACE_PATH, "w", encoding="utf-8") as f:
        json.dump(trace_data, f, ensure_ascii=False, indent=2)
    print(f"📊 [OBSERVABILITY]: Đã lưu {len(trace_data)} sự kiện tại 'docs/trace_waterfall_web.json'!")


# ==============================================================================
# CHAT HISTORY (FILE JSON)
# ==============================================================================

def load_history():
    """Đọc lịch sử chat từ web/chat_history.json."""
    if not os.path.isfile(HISTORY_PATH):
        return {"sessions": []}
    try:
        with io.open(HISTORY_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"sessions": []}


def save_history(data):
    """Ghi toàn bộ lịch sử chat ra web/chat_history.json."""
    os.makedirs(WEB_DIR, exist_ok=True)
    with io.open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ==============================================================================
# ENTRY POINT
# ==============================================================================

def main():
    global PROVIDER, MCP_SERVER

    parser = argparse.ArgumentParser(description="Web UI cho ReAct Agent (Day 03 Lab)")
    parser.add_argument("--port", type=int, default=int(os.getenv("WEB_PORT", "7860")))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--no-browser", action="store_true", help="Không tự mở trình duyệt")
    args = parser.parse_args()

    PROVIDER = get_llm_provider()
    MCP_SERVER = MCPLibraryServer()

    url = "http://%s:%d" % (args.host, args.port)

    print("==========================================================")
    print("🌐 VINUNI AI COURSE - DAY 03 LAB: REACT AGENT WEB UI")
    print("==========================================================")
    print(f"🔌 LLM Provider  : {PROVIDER.__class__.__name__} ({getattr(PROVIDER, 'model_name', 'unknown')})")
    print(f"🌐 MCP Server    : {MCP_SERVER.server_name} v{MCP_SERVER.version}")
    print(f"🛠️  Tools         : {len(MCP_SERVER.list_tools())}")
    print(f"🚀 Đang chạy tại : {url}")
    print("   (Nhấn Ctrl+C để dừng)\n")

    httpd = ThreadingHTTPServer((args.host, args.port), LabRequestHandler)
    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Đã dừng Web Server.")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
