import os
import logging
import httpx
from typing import Dict, Any, Optional

logger = logging.getLogger("IPFSService")

PINATA_API_KEY = os.getenv("PINATA_API_KEY", "")
PINATA_SECRET_API_KEY = os.getenv("PINATA_SECRET_API_KEY", "")
PINATA_JWT = os.getenv("PINATA_JWT", "")
PINATA_PIN_FILE_URL = "https://api.pinata.cloud/pinning/pinFileToIPFS"
PINATA_PIN_JSON_URL = "https://api.pinata.cloud/pinning/pinJSONToIPFS"

class IPFSService:
    @staticmethod
    def _get_headers() -> Dict[str, str]:
        if PINATA_JWT:
            return {"Authorization": f"Bearer {PINATA_JWT}"}
        return {
            "pinata_api_key": PINATA_API_KEY,
            "pinata_secret_api_key": PINATA_SECRET_API_KEY
        }

    @classmethod
    async def pin_bytes_to_ipfs(
        cls, 
        file_bytes: bytes, 
        filename: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Pins raw encrypted byte payload to IPFS via Pinata REST API."""
        headers = cls._get_headers()
        files = {
            'file': (filename, file_bytes, 'application/octet-stream')
        }
        
        payload = {}
        if metadata:
            payload['pinataMetadata'] = str(metadata)

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    PINATA_PIN_FILE_URL, 
                    files=files, 
                    headers=headers
                )
                response.raise_for_status()
                data = response.json()
                ipfs_hash = data.get("IpfsHash")
                logger.info(f"Successfully pinned file {filename} to IPFS: {ipfs_hash}")
                return {
                    "ipfs_cid": ipfs_hash,
                    "pin_size": data.get("PinSize"),
                    "timestamp": data.get("Timestamp")
                }
            except Exception as e:
                logger.error(f"Failed to pin file {filename} to IPFS: {str(e)}")
                raise RuntimeError(f"IPFS pinning error: {str(e)}") from e

    @classmethod
    async def pin_json_to_ipfs(
        cls, 
        json_data: Dict[str, Any], 
        pin_name: str
    ) -> Dict[str, Any]:
        """Pins structured JSON metadata to IPFS via Pinata REST API."""
        headers = cls._get_headers()
        headers["Content-Type"] = "application/json"
        
        body = {
            "pinataContent": json_data,
            "pinataMetadata": {"name": pin_name}
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    PINATA_PIN_JSON_URL, 
                    json=body, 
                    headers=headers
                )
                response.raise_for_status()
                data = response.json()
                ipfs_hash = data.get("IpfsHash")
                logger.info(f"Successfully pinned JSON {pin_name} to IPFS: {ipfs_hash}")
                return {
                    "ipfs_cid": ipfs_hash,
                    "pin_size": data.get("PinSize"),
                    "timestamp": data.get("Timestamp")
                }
            except Exception as e:
                logger.error(f"Failed to pin JSON to IPFS: {str(e)}")
                raise RuntimeError(f"IPFS JSON pinning error: {str(e)}") from e
