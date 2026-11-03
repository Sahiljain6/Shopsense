import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.hidden_path_middleware import BlockGitMetadataMiddleware


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.add_middleware(BlockGitMetadataMiddleware)

    @app.get("/{requested_path:path}")
    async def echo_path(requested_path: str) -> dict[str, str]:
        return {"path": requested_path}

    return TestClient(app)


@pytest.mark.parametrize(
    "path",
    [
        ".git",
        ".git/HEAD",
        ".git/config",
        "nested/.git/config",
        "nested/.GIT/objects/example",
        ".git%2Fconfig",
        "nested/%2egit/config",
        "nested/%252egit/config",
    ],
)
def test_git_metadata_paths_return_404(client: TestClient, path: str) -> None:
    response = client.get(f"/{path}")

    assert response.status_code == 404
    assert response.text == "Not Found"
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("path", [".github/workflows/ci.yml", ".gitignore", "products"])
def test_non_git_metadata_paths_are_not_blocked(client: TestClient, path: str) -> None:
    response = client.get(f"/{path}")

    assert response.status_code == 200
