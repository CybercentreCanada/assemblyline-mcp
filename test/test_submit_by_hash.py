import json
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest
from assemblyline_client.v4_client.common.utils import ClientError
from assemblyline_client.v4_client.module.submit import Submit
from fastmcp import Client
from fastmcp.exceptions import ToolError
from starlette.requests import Request

from mcp_server import app

SHA256 = "0123456789abcdef" * 4


@pytest.fixture
def assemblyline_client(monkeypatch):
    client = MagicMock()
    client.submit.return_value = {"sid": "test-submission", "files": [{"sha256": SHA256}]}

    @contextmanager
    def get_client():
        yield client

    monkeypatch.setattr(app, "get_assemblyline_client", get_client)
    return client


async def test_submit_by_hash_schema():
    async with Client(app.initialize_server()) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}

    tool = tools["submit_by_hash"]
    assert tool.inputSchema["required"] == ["file_hash"]
    assert set(tool.inputSchema["properties"]) == {
        "file_hash",
        "fname",
        "params",
        "metadata",
        "submission_profile",
    }
    hash_schema = tool.inputSchema["properties"]["file_hash"]
    assert hash_schema["minLength"] == hash_schema["maxLength"] == 64
    assert hash_schema["pattern"] == r"^[0-9a-fA-F]+$"
    assert tool.annotations.readOnlyHint is False
    assert tool.annotations.destructiveHint is False
    assert tool.annotations.idempotentHint is False
    assert tool.annotations.openWorldHint is True


@pytest.mark.parametrize("file_hash", [SHA256, SHA256.upper()])
async def test_submit_by_hash_defaults(assemblyline_client, file_hash):
    async with Client(app.initialize_server()) as client:
        response = await client.call_tool("submit_by_hash", {"file_hash": file_hash})

    assert response.data == assemblyline_client.submit.return_value
    assemblyline_client.submit.assert_called_once_with(
        sha256=SHA256, fname=None, params=None, metadata=None, submission_profile=None
    )


@pytest.mark.parametrize(
    "options",
    [
        {
            "fname": "sample.exe",
            "params": {"ignore_cache": True, "services": {"selected": ["Static Analysis"]}},
            "metadata": {"source": "mcp"},
            "submission_profile": "static",
        },
        {"fname": None, "params": {}, "metadata": {}, "submission_profile": None},
    ],
)
async def test_submit_by_hash_options(assemblyline_client, options):
    async with Client(app.initialize_server()) as client:
        response = await client.call_tool("submit_by_hash", {"file_hash": SHA256, **options})

    assert response.data == assemblyline_client.submit.return_value
    assemblyline_client.submit.assert_called_once_with(sha256=SHA256, **options)


async def test_submit_by_hash_client_request(assemblyline_client):
    connection = MagicMock()
    connection.post.return_value = {"sid": "test-submission"}
    assemblyline_client.submit = Submit(connection)
    options = {
        "fname": "sample.exe",
        "params": {"ignore_cache": True},
        "metadata": {"source": "mcp"},
        "submission_profile": "static",
    }

    async with Client(app.initialize_server()) as client:
        response = await client.call_tool("submit_by_hash", {"file_hash": SHA256.upper(), **options})

    assert response.data == {"sid": "test-submission"}
    connection.post.assert_called_once()
    assert connection.post.call_args.args == ("api/v4/submit/",)
    assert json.loads(connection.post.call_args.kwargs["data"]) == {
        "sha256": SHA256,
        "name": options["fname"],
        "params": options["params"],
        "metadata": options["metadata"],
        "submission_profile": options["submission_profile"],
    }
    assert connection.post.call_args.kwargs["files"] == {}
    assert connection.post.call_args.kwargs["headers"] is None


@pytest.mark.parametrize(
    "file_hash",
    ["", "a" * 32, "a" * 40, "a" * 63, "a" * 65, "g" * 64, "a" * 63 + "\n", SHA256 + "\n", " " + SHA256, None, 123],
)
async def test_submit_by_hash_rejects_invalid_hash(assemblyline_client, file_hash):
    async with Client(app.initialize_server()) as client:
        with pytest.raises(ToolError):
            await client.call_tool("submit_by_hash", {"file_hash": file_hash})

    assemblyline_client.submit.assert_not_called()


async def test_submit_by_hash_requires_hash(assemblyline_client):
    async with Client(app.initialize_server()) as client:
        with pytest.raises(ToolError):
            await client.call_tool("submit_by_hash", {})

    assemblyline_client.submit.assert_not_called()


@pytest.mark.parametrize(
    ("status_code", "message"),
    [(403, "Submission permission denied"), (404, "File not found"), (503, "Submission quota exceeded")],
)
async def test_submit_by_hash_propagates_api_errors(assemblyline_client, status_code, message):
    assemblyline_client.submit.side_effect = ClientError(message, status_code)

    async with Client(app.initialize_server()) as client:
        with pytest.raises(ToolError, match=message):
            await client.call_tool("submit_by_hash", {"file_hash": SHA256})

    assemblyline_client.submit.assert_called_once()


@pytest.mark.parametrize(
    ("headers", "auth_kwargs"),
    [
        ([(b"x-user", b"test-user"), (b"x-apikey", b"test-key")], {"apikey": ("test-user", "test-key")}),
        ([(b"authorization", b"Bearer test-token")], {"oauth": "test-token"}),
    ],
)
async def test_submit_by_hash_uses_request_authentication(monkeypatch, headers, auth_kwargs):
    request = Request({"type": "http", "headers": headers})
    get_client = MagicMock()
    get_client.return_value.submit.return_value = {"sid": "test-submission"}
    monkeypatch.setattr(app, "get_http_request", lambda: request)
    monkeypatch.setattr(app, "get_client", get_client)

    async with Client(app.initialize_server()) as client:
        response = await client.call_tool("submit_by_hash", {"file_hash": SHA256})

    assert response.data == {"sid": "test-submission"}
    assert get_client.call_count == 1
    assert get_client.call_args.args == (app.AL_UI,)
    for key, value in auth_kwargs.items():
        assert get_client.call_args.kwargs[key] == value
    get_client.return_value.submit.assert_called_once_with(
        sha256=SHA256, fname=None, params=None, metadata=None, submission_profile=None
    )


async def test_submit_by_hash_requires_authentication(monkeypatch):
    request = Request({"type": "http", "headers": []})
    get_client = MagicMock()
    monkeypatch.setattr(app, "get_http_request", lambda: request)
    monkeypatch.setattr(app, "get_client", get_client)

    async with Client(app.initialize_server()) as client:
        with pytest.raises(ToolError, match="No API key or authorization token"):
            await client.call_tool("submit_by_hash", {"file_hash": SHA256})

    get_client.assert_not_called()
