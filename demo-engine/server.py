#!/usr/bin/env python3
"""Tiny OpenAI-compatible demo endpoint for the Suparagent browser preview.

No real model, no external key: returns a short canned reply, streamed as
OpenAI-style SSE so the app's OpenAI-compatible engine works end to end.
"""
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODEL = "demo"


def chunk(text=None, finish=None, usage=None):
    delta = {"content": text} if text is not None else {}
    data = {
        "id": "chatcmpl-demo",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": MODEL,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
    }
    if usage is not None:
        data["usage"] = usage
    return ("data: " + json.dumps(data) + "\n\n").encode()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):  # noqa: A002 - matches BaseHTTPRequestHandler
        pass

    def do_GET(self):
        if self.path.rstrip("/") in ("/v1/models", "/models"):
            body = json.dumps({
                "object": "list",
                "data": [{"id": MODEL, "object": "model", "owned_by": "demo"}],
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path.rstrip("/") not in ("/v1/chat/completions", "/chat/completions"):
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length") or 0)
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            payload = {}
        messages = payload.get("messages") or []
        user = ""
        for m in reversed(messages):
            if isinstance(m, dict) and m.get("role") == "user":
                c = m.get("content")
                user = c if isinstance(c, str) else json.dumps(c)
                break
        prompt = user.strip().replace("\n", " ")
        if len(prompt) > 120:
            prompt = prompt[:117] + "..."
        reply = (
            "Demo engine online. You said: \u201c" + (prompt or "(empty)") + "\u201d. "
            "This is a canned local response so you can test the web app without a real API key."
        )
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        try:
            words = reply.split(" ")
            for i, word in enumerate(words):
                piece = word if i == len(words) - 1 else word + " "
                self.wfile.write(chunk(piece))
                self.wfile.flush()
                time.sleep(0.012)
            self.wfile.write(chunk(None, "stop", {
                "prompt_tokens": max(1, len(prompt.split())),
                "completion_tokens": len(words),
            }))
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 9000), Handler).serve_forever()
