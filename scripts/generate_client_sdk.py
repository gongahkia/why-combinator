#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.sdk.generator import generate_sdk_artifacts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate typed SDK artifacts from OpenAPI schema.")
    parser.add_argument(
        "--schema-output",
        default="sdk/openapi.json",
        help="Path to write the OpenAPI schema JSON.",
    )
    parser.add_argument(
        "--sdk-output-dir",
        default="sdk/typescript-client",
        help="Directory where the typed SDK package files are generated.",
    )
    parser.add_argument(
        "--package-name",
        default="@bengers/hackathon-sdk",
        help="NPM package name for generated SDK metadata.",
    )
    parser.add_argument(
        "--package-version",
        default="0.1.0",
        help="Generated SDK package version.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    schema_path, tarball_path = generate_sdk_artifacts(
        schema_output_path=Path(args.schema_output),
        sdk_output_dir=Path(args.sdk_output_dir),
        package_name=args.package_name,
        package_version=args.package_version,
    )
    print(f"openapi_schema={schema_path}")
    print(f"sdk_tarball={tarball_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
