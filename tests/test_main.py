import json
import os
from unittest.mock import MagicMock, patch

import pytest

# Env must be set before importing main — req() asserts API_KEY is not None
os.environ.setdefault("OMNIROUTE_LOCAL_API_KEY", "test-key")
os.environ.setdefault("OMNIROUTE_CLOUD_API_KEY", "test-cloud-key")
os.environ.setdefault("OMNIROUTE_CLOUD_BASE_URL", "https://cloud.example.com/v1")
os.environ.setdefault("OMNIROUTE_LOCAL_BASE_URL", "http://127.0.0.1:20128")
os.environ.setdefault("OMNIROUTE_LOCAL_RUNTIME_MODEL_CODING", "qwen2.5-coder:14b")
os.environ.setdefault("OMNIROUTE_LOCAL_RUNTIME_MODEL_CODING_FAST", "qwen2.5-coder:7b")
os.environ.setdefault("OMNIROUTE_LOCAL_RUNTIME_MODEL_FAST", "qwen2.5:7b")
os.environ.setdefault("OMNIROUTE_LOCAL_RUNTIME_MODEL_REASONING", "deepseek-r1:14b")
os.environ.setdefault("OMNIROUTE_LOCAL_RUNTIME_MODEL_VISION", "qwen2.5-vl:7b")

from main import (  # noqa: E402
    LOCAL_URL,
    fail,
    find_connection,
    req,
    upsert_connection,
    upsert_node,
)


class TestFail:
    def test_exits_with_error(self):
        with pytest.raises(SystemExit) as exc:
            fail("something went wrong")
        assert exc.value.code == 1


class TestReq:
    def test_success(self):
        resp = MagicMock()
        resp.read.return_value = json.dumps({"ok": True}).encode()
        resp.__enter__.return_value = resp

        with patch("urllib.request.urlopen", return_value=resp) as m:
            result = req("GET", "/test")

        assert result == {"ok": True}
        m.assert_called_once()
        assert m.call_args[0][0].method == "GET"
        assert m.call_args[0][0].full_url == f"{LOCAL_URL}/test"

    def test_http_error(self):
        resp = MagicMock()
        resp.read.return_value = b"not found"
        resp.__enter__.return_value = resp

        err = __import__("urllib.error").error.HTTPError(
            "http://localhost", 404, "Not Found", {}, resp
        )

        with patch("urllib.request.urlopen", side_effect=err):
            result = req("GET", "/fail")

        assert result == {}

    def test_generic_exception(self):
        with patch("urllib.request.urlopen", side_effect=ConnectionError("boom")):
            result = req("GET", "/boom")

        assert result == {}


class TestFindConnection:
    @patch("main.req")
    def test_found(self, mock_req):
        mock_req.return_value = {
            "providers": [
                {"provider": "node-1", "id": "conn-42"},
            ]
        }
        assert find_connection("node-1") == "conn-42"

    @patch("main.req")
    def test_not_found(self, mock_req):
        mock_req.return_value = {"providers": []}
        assert find_connection("node-99") is None

    @patch("main.req")
    def test_list_directly(self, mock_req):
        mock_req.return_value = [
            {"provider": "node-1", "id": "conn-1"},
        ]
        assert find_connection("node-1") == "conn-1"


class TestUpsertNode:
    @patch("main.req")
    def test_existing(self, mock_req):
        nodes = [{"id": "n1"}]
        node_id = upsert_node(nodes, {"name": "test", "type": "openai"}, lambda n: True)
        assert node_id == "n1"
        assert mock_req.call_count == 1
        assert mock_req.call_args[0][:2] == ("PUT", "/api/provider-nodes/n1")

    @patch("main.req")
    def test_new(self, mock_req):
        mock_req.return_value = {"node": {"id": "n2"}}
        node_id = upsert_node([], {"name": "test", "type": "openai"}, lambda n: False)
        assert node_id == "n2"
        assert mock_req.call_args[0][:2] == ("POST", "/api/provider-nodes")


class TestUpsertConnection:
    @patch("main.find_connection")
    @patch("main.req")
    def test_existing(self, mock_req, mock_find):
        mock_find.return_value = "conn-1"
        conn_id = upsert_connection("node-1", {"name": "test", "authType": "apikey"})
        assert conn_id == "conn-1"
        assert mock_req.call_args[0][:2] == ("PUT", "/api/providers/conn-1")

    @patch("main.find_connection")
    @patch("main.req")
    def test_new(self, mock_req, mock_find):
        mock_find.return_value = None
        mock_req.return_value = {"connection": {"id": "conn-2"}}

        conn_id = upsert_connection("node-1", {"name": "test", "authType": "apikey"})

        assert conn_id == "conn-2"
        assert mock_req.call_args_list[0][0][:2] == ("POST", "/api/providers")
        assert mock_req.call_args_list[1][0][:2] == ("PUT", "/api/providers/conn-2")


def build_side_effect():
    def side_effect(method, path, body=None):
        if path == "/api/provider-nodes":
            return {"nodes": []}
        if path == "/api/combos":
            return {"combos": []}
        if path == "/api/providers":
            return {"connection": {"id": "new-conn"}}
        if path.startswith("/api/provider-nodes"):
            return {"node": {"id": "new-node"}}
        if path.startswith("/api/providers/") and path.endswith("/test"):
            return {}
        return {}

    return side_effect


class TestMain:
    @patch("main.LOCAL_KEY", None)
    @patch("main.req")
    def test_missing_local_key(self, mock_req):
        with pytest.raises(SystemExit):
            import main as m

            m.main()

    @patch("main.CLOUD_KEY", None)
    @patch("main.req")
    def test_missing_cloud_key(self, mock_req):
        with pytest.raises(SystemExit):
            import main as m

            m.main()

    @patch("main.CLOUD_URL", None)
    @patch("main.req")
    def test_missing_cloud_url(self, mock_req):
        with pytest.raises(SystemExit):
            import main as m

            m.main()

    @patch("main.LOCAL_URL", None)
    @patch("main.req")
    def test_missing_local_url(self, mock_req):
        with pytest.raises(SystemExit):
            import main as m

            m.main()

    @patch("main.LOCAL_RUNTIME_CODING", None)
    @patch("main.req")
    def test_missing_local_coding(self, mock_req):
        with pytest.raises(SystemExit):
            import main as m

            m.main()

    @patch("main.LOCAL_RUNTIME_CODING_FAST", None)
    @patch("main.req")
    def test_missing_local_coding_fast(self, mock_req):
        with pytest.raises(SystemExit):
            import main as m

            m.main()

    @patch("main.LOCAL_RUNTIME_FAST", None)
    @patch("main.req")
    def test_missing_local_fast(self, mock_req):
        with pytest.raises(SystemExit):
            import main as m

            m.main()

    @patch("main.LOCAL_RUNTIME_REASONING", None)
    @patch("main.req")
    def test_missing_local_reasoning(self, mock_req):
        with pytest.raises(SystemExit):
            import main as m

            m.main()

    @patch("main.LOCAL_RUNTIME_VISION", None)
    @patch("main.req")
    def test_missing_local_vision(self, mock_req):
        with pytest.raises(SystemExit):
            import main as m

            m.main()

    @patch("main.req")
    def test_fresh_setup(self, mock_req):
        mock_req.side_effect = build_side_effect()

        import main as m

        m.main()

    @patch("main.req")
    def test_coding_fast_combo_uses_dedicated_runtime_model(self, mock_req):
        mock_req.side_effect = build_side_effect()

        import main as m

        m.main()

        payloads = [
            call.args[2]
            for call in mock_req.call_args_list
            if call.args[:2] == ("POST", "/api/combos")
        ]
        coding_fast = next(payload for payload in payloads if payload["name"] == "best-coding-fast")
        assert coding_fast["models"][1]["model"].endswith("/qwen2.5-coder:7b")

    @patch("main.req")
    def test_re_run(self, mock_req):
        def side_effect(method, path, body=None):
            if path == "/api/provider-nodes":
                return {"nodes": [{"id": "existing-node"}]}
            if path == "/api/combos":
                return {
                    "combos": [
                        {"id": "c1", "name": "best-coding"},
                        {"id": "c2", "name": "best-fast"},
                        {"id": "c3", "name": "best-reasoning"},
                    ]
                }
            if path == "/api/providers":
                return {"connections": [{"id": "existing-conn"}]}
            return {}

        mock_req.side_effect = side_effect

        import main as m

        m.main()
