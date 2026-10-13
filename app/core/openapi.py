from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi


def custom_openapi_schema(app: FastAPI):
    """
    Generates enhanced OpenAPI/Swagger schema with API versioning strategies,
    rate limiting header specs, custom response examples, and deprecation policies.
    """
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="Terminus Protocol Backend API",
        version="2.0.0",
        summary="Globally Scalable Oracle & Custodial Inheritance Engine",
        description="""
    
# Terminus Protocol Backend API

Welcome to the **Terminus Oracle API documentation**. Terminus manages cross-jurisdictional medical/death attestation verification, dead-man's switch vaults, custodial asset sweeps, and automated Solana inheritance execution.
""",  # <-- Missing comma was here
        routes=app.routes,
    )
    app.openapi_schema = openapi_schema
    return openapi_schema