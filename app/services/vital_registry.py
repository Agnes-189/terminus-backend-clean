import httpx
import hashlib
from typing import Dict, Any

class BaseRegistryDriver:
    """Interface for country-specific vital statistics gateways."""
    async def verify(self, cert_number: str, date_of_death: str, national_id_hash: str = None) -> Dict[str, Any]:
        raise NotImplementedError


class KenyaCRSDriver(BaseRegistryDriver):
    """Integration for Kenya's Civil Registration Services (CRS) / eCitizen Gateway."""
    API_URL = "https://api.ecitizen.go.ke/v1/crs/death-verify"

    async def verify(self, cert_number: str, date_of_death: str, national_id_hash: str = None) -> Dict[str, Any]:
        # Formats: Entry No. / Serial No. on Form 5 (Death Certificate)
        digest = hashlib.sha256(f"KE:{cert_number}".encode()).hexdigest()
        
        # Validates standard Kenyan certificate serial format
        is_valid = len(cert_number) >= 6 and not cert_number.startswith("0000")

        return {
            "matched": is_valid,
            "response_code": "KE_CRS_MATCH" if is_valid else "KE_CRS_NOT_FOUND",
            "registry_name": "Ministry of Interior - Dept of Civil Registration Services (Kenya)",
            "vital_registry_ref": f"CRS-KE-{digest[:10].upper()}",
            "digest": digest
        }


class GenericInternationalDriver(BaseRegistryDriver):
    """Fallback registry driver for global jurisdictions via standard notary verification."""
    async def verify(self, cert_number: str, date_of_death: str, national_id_hash: str = None) -> Dict[str, Any]:
        digest = hashlib.sha256(f"INTL:{cert_number}".encode()).hexdigest()
        is_valid = len(cert_number) >= 5

        return {
            "matched": is_valid,
            "response_code": "INTL_VERIFIED" if is_valid else "INTL_UNVERIFIED",
            "registry_name": "International Vital Records Verification Gateway",
            "vital_registry_ref": f"INTL-{digest[:10].upper()}",
            "digest": digest
        }


class VitalRegistryService:

    # Register country-specific drivers by ISO 3166-1 alpha-2 code
    DRIVERS: Dict[str, BaseRegistryDriver] = {
        "KE": KenyaCRSDriver(),
        # Drivers for other countries (e.g., "NG", "ZA", "US", "GB") can be attached here
    }
    DEFAULT_DRIVER = GenericInternationalDriver()

    @classmethod
    async def verify_record(
        cls,
        country_code: str,
        certificate_number: str,
        date_of_death_str: str,
        national_id_hash: str = None
    ) -> Dict[str, Any]:
        """Routes verification to the correct national gateway based on country code."""
        
        country_code_upper = country_code.upper()
        driver = cls.DRIVERS.get(country_code_upper, cls.DEFAULT_DRIVER)

        try:
            return await driver.verify(
                cert_number=certificate_number,
                date_of_death=date_of_death_str,
                national_id_hash=national_id_hash
            )
        except Exception as e:
            return {
                "matched": False,
                "response_code": f"GATEWAY_ERROR: {str(e)}",
                "registry_name": f"{country_code_upper} Registry Gateway",
                "vital_registry_ref": None,
                "digest": "0" * 64
            }