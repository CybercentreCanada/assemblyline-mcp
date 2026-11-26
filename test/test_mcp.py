import pytest
from fastmcp.exceptions import ToolError


@pytest.mark.asyncio
async def test_get_status(client):
    # Test the ping endpoint of the MCP client
    async with client:
        assert await client.ping() == True


@pytest.mark.asyncio
async def test_get_tools(client):
    # Test the list_tools endpoint of the MCP client
    async with client:
        assert await client.list_tools()


@pytest.mark.asyncio
async def test_tool_hello_world(client):
    # Test the tool_call endpoint of the MCP client (unauthenticated)
    async with client:
        response = await client.call_tool("hello_world", timeout=10)
        assert response.content[0].text == "Hello from your MCP server!"


@pytest.mark.asyncio
async def test_oauth(client, oauth_client):
    # Test the tool_call endpoint of the MCP client (unauthenticated)
    async with client:
        with pytest.raises(ToolError):
            # Expect an unauthenticated client to raise an AuthorizationError when calling the "indexes" tool
            await client.call_tool("indexes", timeout=10)

        async with oauth_client as auth_client:
            # We expect to get a response from the API since we're an authenticated user via OAuth
            response = await auth_client.call_tool("indexes", timeout=10)
            assert response.is_error == False


@pytest.mark.asyncio
async def test_apikey(client, apikey_client):
    # Test the tool_call endpoint of the MCP client (unauthenticated)
    async with client:
        with pytest.raises(ToolError):
            # Expect an unauthenticated client to raise an AuthorizationError when calling the "indexes" tool
            await client.call_tool("indexes", timeout=10)

        async with apikey_client as auth_client:
            # We expect to get a response from the API since we're an authenticated user via API key
            response = await auth_client.call_tool("indexes", timeout=10)
            assert response.is_error == False
