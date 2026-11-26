import pytest
from assemblyline.common import forge
from assemblyline.odm.models.config import HASH_PATTERN_MAP
from assemblyline.odm.models.file import File
from assemblyline.odm.randomizer import random_model_obj
from fastmcp.exceptions import ToolError


@pytest.mark.parametrize(
    ("file_hash", "hash_type"),
    [("not-a-hash", "sha256"), ("a" * 64, "unsupported-type")],
)
async def test_submit_by_hash_rejects_invalid_input(apikey_client, file_hash, hash_type):
    # Tests should reject invalid hashes and types
    async with apikey_client as client:
        with pytest.raises(ToolError):
            await client.call_tool("submit", {"file_hash": file_hash, "hash_type": hash_type})


@pytest.mark.parametrize("hash_type", HASH_PATTERN_MAP)
async def test_submit_by_hash(apikey_client, hash_type):
    # Create a file to submit by hash
    ds = forge.get_datastore()
    fs = forge.get_filestore()

    file = random_model_obj(File)
    # Fix TLSH for testing, should always start with T1
    file.tlsh = "T1" + file.tlsh[2:]

    ds.file.save(file.sha256, file)
    ds.file.commit()

    fs.put(file.sha256, b"test")

    # Initiate a submission using the hash
    async with apikey_client as client:
        # By default, Assemblyline supports submitting using common hash types
        response = await client.call_tool("submit", {"hash_type": hash_type, "file_hash": getattr(file, hash_type)})
        assert response.data["sid"]
