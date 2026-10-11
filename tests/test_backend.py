# OpenFill - generative fill for GIMP 3
# Copyright (C) 2022 Torben Giesselmann, (C) 2026 Beckett Harriman
# SPDX-License-Identifier: GPL-3.0-or-later
"""describe_error: every failure reaches the user in plain words with a next step."""

import inspect
import re
import unittest

from openfill import backend
from openfill.backend import (
    BackendError,
    BackendUnavailable,
    GenerationCancelled,
    GenerationTimeout,
    ModelMissing,
    OutOfMemory,
    WorkflowRejected,
    describe_error,
    has_next_step,
)

NEXT_STEP = re.compile(r"settings|download|select|try|close|install", re.IGNORECASE)

# Raw texts the backends really raise (backends/comfy.py, backends/a1111.py).
RAW = {
    BackendUnavailable: "connection refused",
    ModelMissing: "ckpt_name: 'x.safetensors' not in []",
    OutOfMemory: "CUDA out of memory. Tried to allocate 2.00 GiB",
    GenerationTimeout: "no result after 240 s",
    GenerationCancelled: "cancelled by the user",
    WorkflowRejected: "KSampler: Required input is missing: model",
}


class NothingSelected(BackendError):
    """Same shape as app.NothingSelected (that module needs GIMP)."""


class UnsupportedImage(BackendError):
    """Same shape as app.UnsupportedImage."""


def backend_error_classes():
    return [
        obj
        for _, obj in inspect.getmembers(backend, inspect.isclass)
        if issubclass(obj, BackendError) and obj.__module__ == backend.__name__
    ]


class DescribeErrorTests(unittest.TestCase):
    def test_every_backend_error_class_has_a_next_step(self):
        classes = backend_error_classes()
        self.assertGreaterEqual(len(classes), 7)
        for cls in classes:
            for raw in (RAW.get(cls, "something went wrong"), ""):
                with self.subTest(cls=cls.__name__, raw=raw):
                    text = describe_error(cls(raw))
                    self.assertRegex(text, NEXT_STEP)
                    self.assertNotIn(f"{cls.__name__}:", text)

    def test_messages_with_their_own_next_step_are_shown_unchanged(self):
        nothing = (
            "Nothing is selected. Select the area to fill first (for example with the Rectangle or "
            "Free Select tool), then run Generative Fill again."
        )
        indexed = "This image uses indexed colors. Convert it with Image > Mode > RGB and run the command again."
        self.assertEqual(describe_error(NothingSelected(nothing)), nothing)
        self.assertEqual(describe_error(UnsupportedImage(indexed)), indexed)

    def test_dedicated_wordings(self):
        self.assertIn("ran out of memory", describe_error(OutOfMemory("x")))
        self.assertIn("close other programs", describe_error(OutOfMemory("x")))
        self.assertEqual(
            describe_error(GenerationCancelled("x")),
            "Generation was cancelled. Run the command again to try once more.",
        )
        timeout = describe_error(GenerationTimeout("no result after 240 s"))
        self.assertTrue(timeout.startswith("The request timed out (no result after 240 s)."))
        self.assertIn("Generation time limit", timeout)
        rejected = describe_error(WorkflowRejected("KSampler: Required input is missing: model"))
        self.assertIn("ComfyUI rejected the request: KSampler", rejected)
        self.assertIn("Models", rejected)

    def test_model_missing_keeps_the_app_wording(self):
        msg = (
            "'Stable Diffusion 1.5 Inpainting' is not downloaded yet. Open Filters > OpenFill > Generative "
            "Fill Settings > Models and press Download."
        )
        self.assertEqual(describe_error(ModelMissing(msg)), f"A model file is missing on the backend: {msg}")
        bare = describe_error(ModelMissing("ckpt_name: 'x' not in []"))
        self.assertIn("press Download", bare)

    def test_backend_unavailable_with_and_without_next_step(self):
        port = "Port 8199 is used by another program (it is not ComfyUI). Close that program."
        self.assertEqual(describe_error(BackendUnavailable(port)), f"The AI backend is not available: {port}")
        bare = describe_error(BackendUnavailable("connection refused"))
        self.assertTrue(bare.startswith("The AI backend is not available: connection refused. "))
        self.assertIn("Generative Fill Settings", bare)

    def test_unexpected_exception_keeps_class_name_and_gets_a_step(self):
        text = describe_error(KeyError("seed"))
        self.assertTrue(text.startswith("KeyError: 'seed'"))
        self.assertTrue(has_next_step(text))


if __name__ == "__main__":
    unittest.main()


class ConnectionLostTests(unittest.TestCase):
    """rob-backend-crash-mid-job: ComfyUI killed while sampling must read as a stopped backend."""

    class FakeClient:
        def __init__(self, alive, status=0):
            self.alive, self.status = alive, status

        def queue_prompt(self, graph):
            return "p1"

        def wait_for(self, *args, **kwargs):
            from openfill.comfy_api import ComfyApiError

            raise ComfyApiError("GET /history/p1 failed: <urlopen error [WinError 10061] refused>", self.status)

        def is_alive(self, timeout=3.0):
            return self.alive

        def interrupt(self):
            pass

        def clear_queue(self):
            pass

    def run_with(self, client):
        from openfill.backends.comfy import ComfyBackend

        backend_ = ComfyBackend("http://x", client=client, request_timeout=30)
        with self.assertRaises(BackendUnavailable) as ctx:
            backend_._run({}, 20, 1, 512 * 512, None)
        return str(ctx.exception)

    def test_server_gone_gives_plain_message(self):
        from openfill.backends.comfy import CONNECTION_LOST

        text = self.run_with(self.FakeClient(alive=False))
        self.assertEqual(text, CONNECTION_LOST)
        self.assertNotIn("urlopen", describe_error(BackendUnavailable(text)))
        self.assertTrue(has_next_step(text))

    def test_server_still_up_keeps_detail(self):
        self.assertIn("/history", self.run_with(self.FakeClient(alive=True)))
