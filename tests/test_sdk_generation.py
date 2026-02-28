from __future__ import annotations

import json
import tarfile
from pathlib import Path

from app.sdk.generator import generate_typed_sdk_package


def test_generate_typed_sdk_package_writes_publishable_tarball(tmp_path: Path) -> None:
    schema = {
        "openapi": "3.1.0",
        "info": {"title": "Test API", "version": "1.0.0"},
        "paths": {
            "/runs/{run_id}/leaderboard": {
                "get": {
                    "operationId": "get_leaderboard",
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/LeaderboardResponse"}
                                }
                            },
                        }
                    },
                }
            }
        },
        "components": {
            "schemas": {
                "LeaderboardItem": {
                    "type": "object",
                    "required": ["rank", "submission_id", "final_score"],
                    "properties": {
                        "rank": {"type": "integer"},
                        "submission_id": {"type": "string"},
                        "final_score": {"type": "number"},
                    },
                },
                "LeaderboardResponse": {
                    "type": "object",
                    "required": ["run_id", "items"],
                    "properties": {
                        "run_id": {"type": "string"},
                        "items": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/LeaderboardItem"},
                        },
                    },
                },
            }
        },
    }

    output_dir = tmp_path / "typescript-client"
    tarball_path = generate_typed_sdk_package(
        schema,
        output_dir,
        package_name="@acme/test-sdk",
        package_version="1.2.3",
    )

    assert (output_dir / "openapi.json").exists()
    assert (output_dir / "src" / "types.ts").exists()
    assert (output_dir / "src" / "client.ts").exists()
    assert tarball_path.exists()

    package_json = json.loads((output_dir / "package.json").read_text(encoding="utf-8"))
    assert package_json["name"] == "@acme/test-sdk"
    assert package_json["version"] == "1.2.3"

    with tarfile.open(tarball_path, "r:gz") as archive:
        members = {member.name for member in archive.getmembers()}

    assert "package/package.json" in members
    assert "package/src/client.ts" in members
    assert "package/src/types.ts" in members
