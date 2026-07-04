"""FastAPI gateway for Epis-KG."""

__all__ = ["create_app"]


def create_app():  # noqa: ANN201 - lazy import keeps CLI import cost low
    from api_gateway.main import create_app as _create_app

    return _create_app()
