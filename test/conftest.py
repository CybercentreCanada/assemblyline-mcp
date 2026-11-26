import pytest
import requests
from assemblyline.common import forge
from assemblyline.odm.models.apikey import get_apikey_id
from assemblyline.odm.models.user import USER_ROLES_BASIC
from assemblyline.odm.random_data import DEV_APIKEY_NAME, create_users
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

MCP_SERVER_URL = "http://localhost:8000/mcp/"


@pytest.fixture
def client():
    return Client(MCP_SERVER_URL, verify=False)


@pytest.fixture(scope="session")
def oauth_client():
    ds = forge.get_datastore()
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
        timeout=10,
    ).json()["access_token"]
    return Client(MCP_SERVER_URL, auth=oauth_token, verify=False)


@pytest.fixture(scope="session")
def apikey_client():
    ds = forge.get_datastore()
    create_users(ds)

    apikey_name = ds.apikey.get(get_apikey_id(DEV_APIKEY_NAME, "admin")).key_name
    apikey = f"{apikey_name}:admin"

    return Client(
        transport=StreamableHttpTransport(MCP_SERVER_URL, headers={"X-USER": "admin", "X-APIKEY": apikey}),
        verify=False,
    )
