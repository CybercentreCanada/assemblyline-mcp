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
FILE_SOURCES = {
    "sha256": {"pattern": "^[a-f0-9]{64}$", "sources": ["hash-store"]},
    "sha1": {"pattern": "^[a-f0-9]{40}$", "sources": ["hash-store"]},
    "md5": {"pattern": "^[a-f0-9]{32}$", "sources": ["hash-store"]},
    "tlsh": {"pattern": "^((?:T1)?[0-9a-fA-F]{70})$", "sources": []},
    "ssdeep": {"pattern": "^[0-9]{1,18}:[a-zA-Z0-9/+]{0,64}:[a-zA-Z0-9/+]{0,64}$", "sources": []},
    "ticket": {"pattern": r"CASE-\d+", "sources": ["ticket-store"]},
    "source_url": {"pattern": r"https://example\.org/files/\w+", "sources": ["url-store"]},
}


@pytest.fixture
def assemblyline_client(monkeypatch):
    client = MagicMock()
    client.submit.return_value = {"sid": "test-submission", "files": [{"sha256": SHA256}]}
    client.user.whoami.return_value = {"configuration": {"submission": {"file_sources": FILE_SOURCES}}}

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
        "hash_type",
    }
    hash_schema = tool.inputSchema["properties"]["file_hash"]
    assert hash_schema["minLength"] == 1
    assert tool.inputSchema["properties"]["hash_type"]["default"] == "sha256"
    assert "submission.file_sources" in tool.description
    assert "default_external_sources" in tool.inputSchema["properties"]["params"]["description"]
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
        fetch_input=("sha256", SHA256), fname=None, params=None, metadata=None, submission_profile=None
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
        {"fname": None, "params": {"default_external_sources": []}, "metadata": None, "submission_profile": None},
    ],
)
async def test_submit_by_hash_options(assemblyline_client, options):
    async with Client(app.initialize_server()) as client:
        response = await client.call_tool("submit_by_hash", {"file_hash": SHA256, **options})

    assert response.data == assemblyline_client.submit.return_value
    assemblyline_client.submit.assert_called_once_with(fetch_input=("sha256", SHA256), **options)


@pytest.mark.parametrize(
    ("hash_type", "file_hash", "normalized"),
    [
        ("sha256", SHA256.upper(), SHA256),
        ("sha1", "A" * 40, "a" * 40),
        ("md5", "B" * 32, "b" * 32),
        ("tlsh", "T1" + "A" * 70, "T1" + "A" * 70),
        ("tlsh", "a" * 70, "a" * 70),
        ("ssdeep", "3:AbC/+:dEF", "3:AbC/+:dEF"),
        ("ssdeep", "3::", "3::"),
        ("ticket", "CASE-123", "CASE-123"),
        ("source_url", "https://example.org/files/Sample", "https://example.org/files/Sample"),
    ],
)
async def test_submit_by_hash_client_request(assemblyline_client, hash_type, file_hash, normalized):
    connection = MagicMock()
    connection.post.return_value = {"sid": "test-submission"}
    assemblyline_client.submit = Submit(connection)
    options = {
        "fname": "sample.exe",
        "params": {"ignore_cache": True, "default_external_sources": ["hash-store", "ticket-store"]},
        "metadata": {"source": "mcp"},
        "submission_profile": "static",
    }

    async with Client(app.initialize_server()) as client:
        response = await client.call_tool("submit_by_hash", {"file_hash": file_hash, "hash_type": hash_type, **options})

    assert response.data == {"sid": "test-submission"}
    connection.post.assert_called_once()
    assert connection.post.call_args.args == ("api/v4/submit/",)
    assert json.loads(connection.post.call_args.kwargs["data"]) == {
        hash_type: normalized,
        "name": options["fname"],
        "params": options["params"],
        "metadata": options["metadata"],
        "submission_profile": options["submission_profile"],
    }
    assert connection.post.call_args.kwargs["files"] == {}
    assert connection.post.call_args.kwargs["headers"] is None


@pytest.mark.parametrize(
    ("hash_type", "file_hash"),
    [
        ("md5", "a" * 31),
        ("sha1", "a" * 41),
        ("md5", "g" * 32),
        ("tlsh", "not-tlsh"),
        ("ssdeep", "not-ssdeep"),
        ("ticket", "case-123"),
        ("ticket", "CASE-123\n"),
        ("source_url", "http://example.org/files/Sample"),
    ],
)
async def test_submit_by_hash_validates_configured_pattern(assemblyline_client, hash_type, file_hash):
    async with Client(app.initialize_server()) as client:
        with pytest.raises(ToolError, match="does not match the configured pattern"):
            await client.call_tool("submit_by_hash", {"file_hash": file_hash, "hash_type": hash_type})

    assemblyline_client.submit.assert_not_called()


@pytest.mark.parametrize("hash_type", ["unknown", "params", "name", "base64", "url"])
async def test_submit_by_hash_rejects_unadvertised_type(assemblyline_client, hash_type):
    async with Client(app.initialize_server()) as client:
        with pytest.raises(ToolError, match="Unsupported hash_type"):
            await client.call_tool("submit_by_hash", {"file_hash": SHA256, "hash_type": hash_type})

    assemblyline_client.submit.assert_not_called()


async def test_submit_by_hash_propagates_configuration_errors(assemblyline_client):
    assemblyline_client.user.whoami.side_effect = ClientError("Configuration access denied", 403)
    async with Client(app.initialize_server()) as client:
        with pytest.raises(ToolError, match="Configuration access denied"):
            await client.call_tool("submit_by_hash", {"file_hash": SHA256})

    assemblyline_client.submit.assert_not_called()


async def test_submit_by_hash_uses_current_configuration(assemblyline_client):
    assemblyline_client.user.whoami.return_value = {
        "configuration": {
            "submission": {"file_sources": {"incident_id": {"pattern": r"INC-\d{4}", "sources": ["incidents"]}}}
        }
    }

    async with Client(app.initialize_server()) as client:
        await client.call_tool(
            "submit_by_hash",
            {
                "file_hash": "INC-1234",
                "hash_type": "incident_id",
                "params": {"default_external_sources": ["incidents"]},
            },
        )

    assemblyline_client.submit.assert_called_once_with(
        fetch_input=("incident_id", "INC-1234"),
        fname=None,
        params={"default_external_sources": ["incidents"]},
        metadata=None,
        submission_profile=None,
    )


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
    get_client.return_value.user.whoami.return_value = {"configuration": {"submission": {"file_sources": FILE_SOURCES}}}
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
        fetch_input=("sha256", SHA256), fname=None, params=None, metadata=None, submission_profile=None
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
