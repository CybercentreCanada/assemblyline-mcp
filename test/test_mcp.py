import pytest
import requests
from assemblyline.common import forge
from assemblyline.odm.models.apikey import get_apikey_id
from assemblyline.odm.models.user import USER_ROLES_BASIC
from assemblyline.odm.random_data import DEV_APIKEY_NAME, create_users
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from fastmcp.exceptions import ToolError

MCP_SERVER_URL = "http://localhost:8000/mcp/"


@pytest.fixture
def client():
    return Client(MCP_SERVER_URL, verify=False)


@pytest.fixture(scope="session")
def oauth_client():
    ds = forge.get_datastore()

    # Create the keycloak user for OAuth-related sign-ins
    ds.user.save(
        "admin-keycloak",
        {
            "uname": "admin-keycloak",
            "name": "Admin",
            "password": "__NO_PASSWORD__",
            "email": "admin@keycloak.com",
            "roles": USER_ROLES_BASIC,
        },
    )

    ds.user.commit()

    # Obtain an access token for the 'admin' user in Keycloak using the password grant type
    oauth_token = requests.post(
        "http://localhost:8080/realms/master/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "username": "admin",
            "password": "admin",
            "client_secret": "assemblyline",
            "client_id": "assemblyline",
            "scope": "openid email profile",
        },
    ).json()["access_token"]
    return Client(MCP_SERVER_URL, auth=oauth_token, verify=False)


@pytest.fixture(scope="session")
def apikey_client():
    # Create standard users for API key-related sign-ins
    ds = forge.get_datastore()
    create_users(ds)

    # Retrieve the API key name for the 'admin' user and construct the API key string
    apikey_name = ds.apikey.get(get_apikey_id(DEV_APIKEY_NAME, "admin")).key_name
    apikey = f"{apikey_name}:admin"

    return Client(
        transport=StreamableHttpTransport(MCP_SERVER_URL, headers={"X-USER": "admin", "X-APIKEY": apikey}), verify=False
    )


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
        response = await client.call_tool("hello_world")
        assert response.content[0].text == "Hello from your MCP server!"


@pytest.mark.asyncio
async def test_oauth(client, oauth_client):
    # Test the tool_call endpoint of the MCP client (unauthenticated)
    async with client:
        with pytest.raises(ToolError):
            # Expect an unauthenticated client to raise an AuthorizationError when calling the "indexes" tool
            await client.call_tool("indexes")

        async with oauth_client as auth_client:
            # We expect to get a response from the API since we're an authenticated user via OAuth
            response = await auth_client.call_tool("indexes")
            assert response.is_error == False


@pytest.mark.asyncio
async def test_apikey(client, apikey_client):
    # Test the tool_call endpoint of the MCP client (unauthenticated)
    async with client:
        with pytest.raises(ToolError):
            # Expect an unauthenticated client to raise an AuthorizationError when calling the "indexes" tool
            await client.call_tool("indexes")

        async with apikey_client as auth_client:
            # We expect to get a response from the API since we're an authenticated user via API key
            response = await auth_client.call_tool("indexes")
            assert response.is_error == False
