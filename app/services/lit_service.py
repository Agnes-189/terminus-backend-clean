import os
import logging
from typing import Dict, Any, List

logger = logging.getLogger("LitProtocolService")

TERMINUS_PROGRAM_ID = os.getenv("TERMINUS_PROGRAM_ID", "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU")

class LitProtocolService:
    @staticmethod
    def generate_vault_access_conditions(
        vault_owner: str,
        beneficiary_pubkey: str
    ) -> List[Dict[str, Any]]:
        """
        Generates Lit Protocol Access Control Conditions (ACCs) on Solana Devnet.
        Decryption requires:
          1. Vault state evaluates to Deceased
          2. Claiming user matches designated beneficiary_pubkey
        """
        accs = [
            {
                "method": "getAccountInfo",
                "params": [vault_owner],
                "chain": "solana",
                "returnValueTest": {
                    "key": "$.state",
                    "comparator": "=",
                    "value": "Deceased"
                }
            },
            {"operator": "and"},
            {
                "method": "customContract",
                "params": [beneficiary_pubkey],
                "chain": "solana",
                "returnValueTest": {
                    "key": ":userAddress",
                    "comparator": "=",
                    "value": beneficiary_pubkey
                }
            }
        ]
        logger.info(f"Generated Lit ACCs for vault owner {vault_owner} and beneficiary {beneficiary_pubkey}")
        return accs
