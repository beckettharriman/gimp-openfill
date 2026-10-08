# Stable Boy - generative fill for GIMP 3
# Copyright (C) 2026 Stable Boy contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""urllib-only client for the ComfyUI HTTP and WebSocket API."""

from __future__ import annotations

import json
import socket
import time
import uuid
from typing import Callable, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .websocket import OP_BINARY, OP_TEXT, WebSocket, WebSocketError, ws_url

ProgressCallback = Callable[[float, str], None]


class ComfyApiError(RuntimeError):
    def __init__(self, message: str, status: int = 0, node_errors: dict | None = None,
                 payload: dict | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.node_errors = node_errors or {}
        self.payload = payload or {}


class ComfyExecutionError(ComfyApiError):
    """``execution_error`` event from the server (includes the exception type)."""

    def __init__(self, message: str, exception_type: str = "", node_type: str = "",
                 traceback: str = "") -> None:
        super().__init__(message)
        self.exception_type = exception_type
        self.node_type = node_type
        self.traceback = traceback

    @property
    def is_out_of_memory(self) -> bool:
        text = f"{self.exception_type} {self!s}".lower()
        return "outofmemory" in text or "out of memory" in text or "cuda error" in text


class ComfyClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8188", timeout: float = 30.0,
                 client_id: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client_id = client_id or uuid.uuid4().hex

    # low level -----------------------------------------------------------

    def _request(self, method: str, path: str, body: bytes | None = None,
                 content_type: str | None = None, timeout: float | None = None) -> bytes:
        headers = {"Accept": "application/json"}
        if content_type:
            headers["Content-Type"] = content_type
        req = Request(self.base_url + path, data=body, headers=headers, method=method)
        try:
            with urlopen(req, timeout=timeout or self.timeout) as resp:
                return resp.read()
        except HTTPError as err:
            raw = err.read()
            payload = {}
            try:
                payload = json.loads(raw.decode("utf-8"))
            except Exception:
                pass
            message = payload.get("error", {}).get("message") if isinstance(payload.get("error"), dict) \
                else payload.get("error") or raw[:300].decode("utf-8", "replace")
            raise ComfyApiError(f"{method} {path} -> HTTP {err.code}: {message}", err.code,
                                payload.get("node_errors"), payload) from err
        except (URLError, socket.timeout, TimeoutError, ConnectionError, OSError) as err:
            raise ComfyApiError(f"{method} {path} failed: {err}") from err

    def _json(self, method: str, path: str, body: dict | None = None, timeout: float | None = None) -> dict:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        raw = self._request(method, path, data, "application/json" if data else None, timeout)
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except ValueError as err:
            raise ComfyApiError(f"{method} {path}: invalid JSON response") from err

    # endpoints -----------------------------------------------------------

    def is_alive(self, timeout: float = 3.0) -> bool:
        try:
            self._request("GET", "/system_stats", timeout=timeout)
            return True
        except ComfyApiError:
            return False

    def system_stats(self) -> dict:
        return self._json("GET", "/system_stats")

    def object_info(self, node_class: str | None = None) -> dict:
        path = "/object_info" if node_class is None else f"/object_info/{node_class}"
        try:
            return self._json("GET", path)
        except ComfyApiError as err:
            if node_class is not None and err.status == 404:
                return {}
            raise

    def combo_options(self, node_class: str, input_name: str) -> list[str]:
        """Enumerated options for ``input_name`` of ``node_class`` (or [])."""
        info = self.object_info(node_class).get(node_class)
        try:
            required = info["input"]["required"]
            options = required[input_name][0]
            return [str(o) for o in options] if isinstance(options, list) else []
        except (KeyError, TypeError, IndexError):
            return []

    def upload_image(self, filename: str, data: bytes, subfolder: str = "stable-boy",
                     overwrite: bool = True) -> str:
        """POST multipart to ``/upload/image``; returns ``subfolder/filename``."""
        boundary = "----StableBoy" + uuid.uuid4().hex
        fields = {"type": "input", "subfolder": subfolder, "overwrite": "true" if overwrite else "false"}
        body = bytearray()
        for key, value in fields.items():
            body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{value}\r\n").encode()
        body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; "
                 f"filename=\"{filename}\"\r\nContent-Type: image/png\r\n\r\n").encode()
        body += data
        body += f"\r\n--{boundary}--\r\n".encode()
        raw = self._request("POST", "/upload/image", bytes(body),
                            f"multipart/form-data; boundary={boundary}")
        info = json.loads(raw.decode("utf-8"))
        name = info.get("name", filename)
        sub = info.get("subfolder", subfolder)
        return f"{sub}/{name}" if sub else name

    def queue_prompt(self, graph: dict) -> str:
        payload = {"prompt": graph, "client_id": self.client_id}
        info = self._json("POST", "/prompt", payload)
        if "prompt_id" not in info:
            raise ComfyApiError(f"/prompt did not return a prompt_id: {info}", payload=info,
                                node_errors=info.get("node_errors"))
        return info["prompt_id"]

    def history(self, prompt_id: str) -> dict | None:
        info = self._json("GET", f"/history/{prompt_id}")
        return info.get(prompt_id)

    def queue(self) -> dict:
        return self._json("GET", "/queue")

    def is_busy(self) -> bool:
        try:
            q = self.queue()
        except ComfyApiError:
            return False
        return bool(q.get("queue_running")) or bool(q.get("queue_pending"))

    def interrupt(self) -> None:
        self._json("POST", "/interrupt", {})

    def view(self, filename: str, subfolder: str = "", folder_type: str = "output") -> bytes:
        query = urlencode({"filename": filename, "subfolder": subfolder, "type": folder_type})
        return self._request("GET", f"/view?{query}", timeout=max(self.timeout, 120))

    def free(self, unload_models: bool = True, free_memory: bool = True) -> None:
        """Ask the server to release models and VRAM."""
        self._json("POST", "/free", {"unload_models": unload_models, "free_memory": free_memory})

    # job tracking --------------------------------------------------------

    def clear_queue(self) -> None:
        self._json("POST", "/queue", {"clear": True})

    def wait_for(self, prompt_id: str, total_steps: int, deadline: float,
                 progress: ProgressCallback | None = None, poll_interval: float = 1.0,
                 preview: Callable[[bytes], None] | None = None,
                 cancel: Callable[[], bool] | None = None) -> dict:
        """Block until ``prompt_id`` finishes; return ``history[prompt_id]``.

        Uses the websocket for step-level progress (and binary preview frames,
        handed raw to ``preview``) and falls back to polling ``/history`` when
        it is not available. ``cancel()`` is polled every loop; when it
        returns True the job is interrupted, the queue cleared and
        :class:`ComfyApiError` ("cancelled") raised. Raises
        :class:`ComfyApiError` on timeout and :class:`ComfyExecutionError`
        on failure.
        """
        ws: Optional[WebSocket] = None
        try:
            ws = WebSocket(ws_url(self.base_url, self.client_id), timeout=5.0)
            ws.connect()
            ws.settimeout(poll_interval)
        except (WebSocketError, OSError):
            ws = None
        done_steps = 0
        queued_text = "Waiting for the AI backend..."
        if progress:
            progress(0.0, queued_text)
        last_poll = 0.0
        try:
            while True:
                now = time.monotonic()
                if now > deadline:
                    raise ComfyApiError("timed out waiting for the backend")
                if cancel and cancel():
                    for action in (self.interrupt, self.clear_queue):
                        try:
                            action()
                        except ComfyApiError:
                            pass
                    raise ComfyApiError("cancelled by the user")
                if ws is not None:
                    try:
                        opcode, payload = ws.recv()
                    except socket.timeout:
                        opcode, payload = None, b""
                    except (WebSocketError, OSError):
                        ws = None
                        opcode, payload = None, b""
                    if opcode == OP_BINARY and preview is not None:
                        try:
                            preview(payload)
                        except Exception:  # noqa: BLE001 - previews are best effort
                            pass
                    if opcode == OP_TEXT:
                        msg = json.loads(payload.decode("utf-8"))
                        kind, data = msg.get("type"), msg.get("data") or {}
                        if data.get("prompt_id") not in (None, prompt_id) and kind != "status":
                            continue
                        if kind == "progress":
                            value, maximum = data.get("value", 0), max(1, data.get("max", 1))
                            frac = (done_steps + value) / max(total_steps, maximum)
                            if progress:
                                progress(min(0.99, frac), f"Generating... step {value}/{maximum}")
                            if value >= maximum:
                                done_steps += maximum
                        elif kind == "executing":
                            node = data.get("node")
                            if node is None and data.get("prompt_id") == prompt_id:
                                break  # finished
                            if progress and node is not None:
                                progress(min(0.99, done_steps / max(1, total_steps)),
                                         f"Running node {node}...")
                        elif kind == "execution_error" and data.get("prompt_id") == prompt_id:
                            raise ComfyExecutionError(
                                data.get("exception_message", "execution error"),
                                data.get("exception_type", ""), data.get("node_type", ""),
                                "\n".join(data.get("traceback", []) or []))
                        elif kind == "execution_interrupted" and data.get("prompt_id") == prompt_id:
                            raise ComfyApiError("generation was interrupted")
                # Poll the history as a safety net (and as the only signal
                # when the websocket is unavailable).
                if now - last_poll >= poll_interval:
                    last_poll = now
                    if ws is None:
                        time.sleep(poll_interval)
                    entry = self.history(prompt_id)
                    if entry:
                        status = entry.get("status", {})
                        if status.get("status_str") == "error":
                            raise ComfyExecutionError(_status_message(status))
                        break
        finally:
            if ws is not None:
                ws.close()
        entry = None
        for _ in range(30):
            entry = self.history(prompt_id)
            if entry:
                break
            time.sleep(0.5)
        if not entry:
            raise ComfyApiError("the backend finished but produced no history entry")
        status = entry.get("status", {})
        if status.get("status_str") == "error":
            raise ComfyExecutionError(_status_message(status))
        if progress:
            progress(1.0, "Done")
        return entry

    def output_images(self, history_entry: dict, node_id: str | None = None) -> list[bytes]:
        """Download every image produced by ``node_id`` (or all SaveImage nodes)."""
        outputs = history_entry.get("outputs", {})
        images: list[bytes] = []
        for nid, out in outputs.items():
            if node_id is not None and nid != node_id:
                continue
            for img in out.get("images", []):
                if img.get("type") != "output":
                    continue
                images.append(self.view(img["filename"], img.get("subfolder", ""), "output"))
        return images


def _status_message(status: dict) -> str:
    for msg in status.get("messages", []):
        if isinstance(msg, list) and len(msg) == 2 and msg[0] == "execution_error":
            data = msg[1] or {}
            return f"{data.get('exception_type', '')}: {data.get('exception_message', 'error')}"
    return "execution failed"
