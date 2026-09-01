"""Offline tests for reakit.httptoolkit - control-API transport, parsing, reporting.

These stub the IPC connection with canned HTTP responses, so they run anywhere:
no HTTP Toolkit installation, no running desktop app, no device.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reakit.config import ConfigManager
from reakit import httptoolkit as htk


class FakeConn:
    """Stands in for a named pipe / unix socket, replaying one canned response."""

    def __init__(self, response: bytes):
        self.response = response
        self.sent = b""
        self._offset = 0

    def send(self, data: bytes):
        self.sent += data

    def recv(self, size: int) -> bytes:
        block = self.response[self._offset:self._offset + size]
        self._offset += len(block)
        return block

    def close(self):
        pass


def client_with(response: bytes) -> tuple[htk.HtkControlClient, FakeConn]:
    conn = FakeConn(response)
    client = htk.HtkControlClient(socket_path="/fake")
    client._connect = lambda: conn
    return client, conn


def http_response(body: str, status: int = 200, chunked: bool = False) -> bytes:
    if chunked:
        payload = f"{len(body):x}\r\n{body}\r\n0\r\n\r\n"
        head = f"HTTP/1.1 {status} OK\r\nTransfer-Encoding: chunked\r\n\r\n"
    else:
        payload = body
        head = f"HTTP/1.1 {status} OK\r\nContent-Length: {len(body)}\r\n\r\n"
    return (head + payload).encode("utf-8")


class TestTransport(unittest.TestCase):
    def test_content_length_response(self):
        client, _ = client_with(http_response('{"ready":true}'))
        status, text = client.request("GET", "/api/status")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(text), {"ready": True})

    def test_chunked_response(self):
        body = json.dumps({"ready": True, "note": "x" * 50})
        client, _ = client_with(http_response(body, chunked=True))
        _, text = client.request("GET", "/api/status")
        self.assertEqual(json.loads(text)["note"], "x" * 50)

    def test_request_serializes_json_body(self):
        client, conn = client_with(http_response('{"success":true,"data":{}}'))
        client.request("POST", "/api/execute", {"name": "events.list", "args": {}})
        sent = conn.sent.decode()
        self.assertIn("POST /api/execute HTTP/1.1", sent)
        self.assertIn("Content-Type: application/json", sent)
        self.assertIn('"name": "events.list"', sent)

    def test_empty_response_raises(self):
        client, _ = client_with(b"")
        with self.assertRaises(htk.HtkError):
            client.request("GET", "/api/status")

    def test_decode_chunked_multiple_chunks(self):
        raw = b"4\r\nabcd\r\n3\r\nefg\r\n0\r\n\r\n"
        self.assertEqual(htk._decode_chunked(raw), b"abcdefg")


class TestExecute(unittest.TestCase):
    def test_unwraps_data_envelope(self):
        payload = {"success": True, "data": {"total": 2, "events": [{"id": "a"}, {"id": "b"}]}}
        client, _ = client_with(http_response(json.dumps(payload)))
        data = client.execute("events.list")
        self.assertEqual(data["total"], 2)

    def test_defaults_to_mcp_source(self):
        """The free tier only permits mcp-sourced calls; ctl is Pro-only."""
        client, conn = client_with(http_response('{"success":true,"data":{}}'))
        client.execute("events.list", {"limit": 5})
        body = json.loads(conn.sent.decode().split("\r\n\r\n", 1)[1])
        self.assertEqual(body["source"], "mcp")
        self.assertEqual(body["args"], {"limit": 5})

    def test_tier_error_surfaces_as_htk_error(self):
        payload = {
            "success": False,
            "error": {"code": "TIER_REQUIRED_PRO", "message": "requires HTTP Toolkit Pro"},
        }
        client, _ = client_with(http_response(json.dumps(payload), status=403))
        with self.assertRaises(htk.HtkError) as ctx:
            client.execute("proxy.get-config")
        self.assertIn("TIER_REQUIRED_PRO", str(ctx.exception))

    def test_is_ready_false_when_not_running(self):
        client = htk.HtkControlClient(socket_path="/fake")

        def boom():
            raise htk.HtkNotRunning("absent")

        client._connect = boom
        self.assertFalse(client.is_ready())
        self.assertFalse(client.is_running())


class TestHelpers(unittest.TestCase):
    def test_split_url(self):
        self.assertEqual(
            htk._split_url("https://api.example.com/v1/login?x=1"),
            ("api.example.com", "/v1/login?x=1"),
        )
        self.assertEqual(htk._split_url("https://example.com"), ("example.com", "/"))
        self.assertEqual(htk._split_url("")[0], "-")

    def test_fmt_time_handles_bad_input(self):
        self.assertEqual(htk._fmt_time(None), "-")
        self.assertEqual(htk._fmt_time("nonsense"), "-")
        self.assertRegex(htk._fmt_time(1787970590201), r"^\d{2}:\d{2}:\d{2}$")

    def test_control_socket_path_is_platform_shaped(self):
        path = htk.control_socket_path()
        self.assertTrue(path.startswith("\\\\.\\pipe\\") or path.endswith(".sock"))

    def test_operation_aliases_map_to_real_names(self):
        self.assertEqual(htk.OPERATION_ALIASES["proxy"], "proxy.get-config")
        self.assertEqual(htk.OPERATION_ALIASES["events"], "events.list")


class TestReporting(unittest.TestCase):
    RESULT = {
        "total": 3,
        "events": [
            {"id": "aaaaaaaa-1111", "type": "http", "method": "GET",
             "url": "https://api.example.com/v1/me", "status": 200,
             "source": "okhttp/4.11.0", "timestamp": 1787970590201},
            {"id": "bbbbbbbb-2222", "type": "http", "method": "POST",
             "url": "https://cdn.example.com/upload", "status": 500,
             "source": "okhttp/4.11.0", "timestamp": 1787970591201},
        ],
    }

    def test_print_events_counts_rows(self):
        self.assertEqual(htk.print_events(self.RESULT), 2)

    def test_print_events_grep_filters(self):
        self.assertEqual(htk.print_events(self.RESULT, grep="cdn"), 1)
        self.assertEqual(htk.print_events(self.RESULT, grep="nomatch"), 0)

    def test_print_events_handles_empty(self):
        self.assertEqual(htk.print_events({"total": 0, "events": []}), 0)

    def test_print_outline_tolerates_sparse_payload(self):
        # Only ever prints; the point is that missing keys must not raise.
        htk.print_outline({"id": "x", "url": "https://e.com/p", "method": "GET"})


class TestEventLookupAndSave(unittest.TestCase):
    class FakeHtk:
        def events(self, filter=None, limit=20, offset=0):
            return TestReporting.RESULT

        def recent(self, filter=None, limit=20):
            return TestReporting.RESULT

    def test_resolve_event_id_expands_prefix(self):
        self.assertEqual(
            htk.resolve_event_id(self.FakeHtk(), "aaaaaaaa"), "aaaaaaaa-1111"
        )

    def test_resolve_event_id_returns_none_when_absent(self):
        self.assertIsNone(htk.resolve_event_id(self.FakeHtk(), "zzzzzzzz"))

    def test_resolve_event_id_passes_through_full_uuid(self):
        full = "4a72e9f1-eaca-4a08-a12a-5ebb24a538b6"
        self.assertEqual(htk.resolve_event_id(self.FakeHtk(), full), full)

    def test_save_events_writes_into_the_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = ConfigManager(workspace_root=Path(tmp) / "ws")
            out = htk.save_events(cfg, "com.test.app", TestReporting.RESULT, label="run1")
            self.assertIsNotNone(out)
            self.assertTrue(out.is_file())
            self.assertIn("traffic", out.parts)
            saved = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(saved["package"], "com.test.app")
            self.assertEqual(len(saved["events"]), 2)


class TestResolveOperation(unittest.TestCase):
    OPS = json.dumps([{"name": "events.list"}, {"name": "proxy.get-config"}])

    def test_expands_alias(self):
        client, _ = client_with(http_response(self.OPS))
        name, available = htk.resolve_operation(client, "proxy")
        self.assertEqual(name, "proxy.get-config")
        self.assertIsNone(available)

    def test_accepts_full_name(self):
        client, _ = client_with(http_response(self.OPS))
        name, available = htk.resolve_operation(client, "events.list")
        self.assertEqual(name, "events.list")
        self.assertIsNone(available)

    def test_reports_available_for_unknown_name(self):
        client, _ = client_with(http_response(self.OPS))
        name, available = htk.resolve_operation(client, "nosuch.operation")
        self.assertEqual(name, "nosuch.operation")
        self.assertEqual(available, ["events.list", "proxy.get-config"])

    def test_skips_validation_when_list_unavailable(self):
        client = htk.HtkControlClient(socket_path="/fake")

        def boom():
            raise htk.HtkNotRunning("absent")

        client._connect = boom
        name, available = htk.resolve_operation(client, "proxy")
        self.assertEqual(name, "proxy.get-config")
        self.assertIsNone(available)


class TestRecentPaging(unittest.TestCase):
    """events.list pages oldest-first, so 'recent' must seek to total - limit."""

    class PagingHtk(htk.HttpToolkit):
        def __init__(self, total):
            self.total = total
            self.calls = []

        def events(self, filter=None, limit=20, offset=0):
            self.calls.append((limit, offset))
            return {"total": self.total, "events": [{"id": f"e{offset}"}]}

    def test_seeks_to_the_tail_when_log_is_longer_than_limit(self):
        h = self.PagingHtk(total=94)
        h.recent(limit=20)
        self.assertEqual(h.calls[0], (1, 0))       # probe for the total
        self.assertEqual(h.calls[1], (20, 74))     # then the last 20

    def test_reads_from_zero_when_log_is_short(self):
        h = self.PagingHtk(total=5)
        h.recent(limit=20)
        self.assertEqual(h.calls[1], (20, 0))

    def test_preserves_total_in_result(self):
        h = self.PagingHtk(total=94)
        self.assertEqual(h.recent(limit=20)["total"], 94)


class TestConfigPaths(unittest.TestCase):
    def test_traffic_path_is_provisioned(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = ConfigManager(workspace_root=Path(tmp) / "ws")
            paths = cfg.get_app_paths("com.test.app")
            self.assertIn("traffic", paths)
            self.assertEqual(paths["traffic"].name, "traffic")
            self.assertEqual(paths["traffic"].parent, paths["root"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
