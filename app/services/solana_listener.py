import os
import json
import asyncio
import logging
import websockets
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.oracle_job import OracleJob, JobStatus, OracleAuditLog

logger = logging.getLogger("SolanaWebSocketListener")

WSS_ENDPOINT = os.getenv("SOLANA_WSS_URL", "wss://api.devnet.solana.com")
PROGRAM_ID = os.getenv("TERMINUS_PROGRAM_ID", "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU")


async def listen_to_solana_events():
    """
    WebSocket listener that subscribes to on-chain program logs
    and automatically updates oracle jobs upon settlement or state change.
    """
    subscribe_message = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "logsSubscribe",
        "params": [
            {"mentions": [PROGRAM_ID]},
            {"commitment": "finalized"}
        ]
    }

    while True:
        try:
            async with websockets.connect(WSS_ENDPOINT) as ws:
                await ws.send(json.dumps(subscribe_message))
                logger.info(f"🌐 [WEBSOCKET CONNECTED] Listening for Solana Program: {PROGRAM_ID}")

                while True:
                    response = await ws.recv()
                    data = json.loads(response)

                    if "params" in data and "result" in data["params"]:
                        logs = data["params"]["result"]["value"]["logs"]
                        signature = data["params"]["result"]["value"]["signature"]
                        
                        _process_onchain_logs(logs, signature)

        except (websockets.ConnectionClosed, Exception) as e:
            logger.warning(f"⚠️ [WEBSOCKET DISCONNECTED] Retrying in 5s: {str(e)}")
            await asyncio.sleep(5)


def _process_onchain_logs(logs: list, signature: str):
    """Parses execution logs and syncs status back to the database."""
    db: Session = SessionLocal()
    try:
        for log in logs:
            if "Program log: Event: ClaimSettled" in log:
                logger.info(f"⚡ [EVENT DETECTED] ClaimSettled in TX: {signature}")
                # Parse job reference from logs if present and update DB
                job = db.query(OracleJob).filter(OracleJob.solana_tx_signature == signature).first()
                if job:
                    job.status = JobStatus.CONFIRMED
                    audit = OracleAuditLog(
                        job_id=job.id,
                        from_status="SOLANA_BROADCASTING",
                        to_status="SETTLED_ON_CHAIN",
                        details=f"WebSocket verified settlement TX: {signature}"
                    )
                    db.add(audit)
                    db.commit()
    except Exception as err:
        logger.error(f"Error processing log event: {str(err)}")
    finally:
        db.close()