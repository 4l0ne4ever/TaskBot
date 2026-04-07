from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app


def _resp_json(status: int, payload: dict) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.text = ""
    r.json = MagicMock(return_value=payload)
    r.content = b""
    return r


def _resp_bytes(status: int, data: bytes) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.text = ""
    r.content = data
    return r


def test_get_file_content_binary_uses_alt_media() -> None:
    tc = TestClient(app)

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, params=None, headers=None):
            if url.endswith("/files/f1") and (params or {}).get("fields") == "mimeType,name":
                return _resp_json(200, {"mimeType": "application/pdf", "name": "a.pdf"})
            if url.endswith("/files/f1") and (params or {}).get("alt") == "media":
                return _resp_bytes(200, b"%PDF")
            raise AssertionError((url, params))

    with patch("app.main.httpx.AsyncClient", FakeClient):
        r = tc.post(
            "/mcp",
            headers={"Authorization": "Bearer t"},
            json={"tool_name": "get_file_content", "arguments": {"file_id": "f1"}},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["mime_type"] == "application/pdf"
    assert body["name"] == "a.pdf"
    assert body["content_base64"]


def test_get_file_content_google_doc_uses_export() -> None:
    tc = TestClient(app)

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, params=None, headers=None):
            if url.endswith("/files/g1") and (params or {}).get("fields") == "mimeType,name":
                return _resp_json(
                    200,
                    {"mimeType": "application/vnd.google-apps.document", "name": "Doc"},
                )
            if url.endswith("/files/g1/export") and (params or {}).get("mimeType") == "application/pdf":
                return _resp_bytes(200, b"%PDF-1")
            raise AssertionError((url, params))

    with patch("app.main.httpx.AsyncClient", FakeClient):
        r = tc.post(
            "/mcp",
            headers={"Authorization": "Bearer t"},
            json={"tool_name": "get_file_content", "arguments": {"file_id": "g1"}},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["mime_type"] == "application/pdf"
    assert body["content_base64"]


def test_get_file_content_folder_rejected() -> None:
    tc = TestClient(app)

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, params=None, headers=None):
            if (params or {}).get("fields") == "mimeType,name":
                return _resp_json(
                    200,
                    {"mimeType": "application/vnd.google-apps.folder", "name": "F"},
                )
            raise AssertionError((url, params))

    with patch("app.main.httpx.AsyncClient", FakeClient):
        r = tc.post(
            "/mcp",
            headers={"Authorization": "Bearer t"},
            json={"tool_name": "get_file_content", "arguments": {"file_id": "folder1"}},
        )
    assert r.status_code == 400
