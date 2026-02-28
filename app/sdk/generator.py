from __future__ import annotations

import json
import re
import tarfile
from pathlib import Path

from app.main import app


def export_openapi_schema(target_path: Path) -> dict[str, object]:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    schema = app.openapi()
    target_path.write_text(json.dumps(schema, indent=2, sort_keys=True), encoding="utf-8")
    return schema


def _to_pascal_case(value: str) -> str:
    parts = re.split(r"[^a-zA-Z0-9]+", value)
    normalized = "".join(part[:1].upper() + part[1:] for part in parts if part)
    return normalized or "Model"


def _to_camel_case(value: str) -> str:
    pascal = _to_pascal_case(value)
    return pascal[:1].lower() + pascal[1:] if pascal else "operation"


def _sanitize_identifier(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", value)
    if not cleaned:
        return "id"
    if cleaned[0].isdigit():
        return f"_{cleaned}"
    return cleaned


def _schema_to_ts_type(
    schema: dict[str, object],
    component_name_map: dict[str, str],
) -> str:
    ref = schema.get("$ref")
    if isinstance(ref, str):
        schema_name = ref.rsplit("/", maxsplit=1)[-1]
        return component_name_map.get(schema_name, _to_pascal_case(schema_name))

    enum_values = schema.get("enum")
    if isinstance(enum_values, list) and enum_values:
        literals = [json.dumps(value) for value in enum_values]
        return " | ".join(literals)

    one_of = schema.get("oneOf")
    if isinstance(one_of, list) and one_of:
        return " | ".join(
            _schema_to_ts_type(item, component_name_map)
            for item in one_of
            if isinstance(item, dict)
        )

    any_of = schema.get("anyOf")
    if isinstance(any_of, list) and any_of:
        return " | ".join(
            _schema_to_ts_type(item, component_name_map)
            for item in any_of
            if isinstance(item, dict)
        )

    all_of = schema.get("allOf")
    if isinstance(all_of, list) and all_of:
        return " & ".join(
            _schema_to_ts_type(item, component_name_map)
            for item in all_of
            if isinstance(item, dict)
        )

    schema_type = schema.get("type")
    if schema_type == "string":
        return "string"
    if schema_type in {"integer", "number"}:
        return "number"
    if schema_type == "boolean":
        return "boolean"
    if schema_type == "array":
        items = schema.get("items")
        if isinstance(items, dict):
            return f"{_schema_to_ts_type(items, component_name_map)}[]"
        return "unknown[]"
    if schema_type == "object":
        properties = schema.get("properties")
        required_raw = schema.get("required")
        required = set(required_raw) if isinstance(required_raw, list) else set()
        if isinstance(properties, dict) and properties:
            parts: list[str] = []
            for property_name, property_schema in sorted(properties.items()):
                if not isinstance(property_schema, dict):
                    continue
                optional = "" if property_name in required else "?"
                ts_type = _schema_to_ts_type(property_schema, component_name_map)
                parts.append(f"{json.dumps(property_name)}{optional}: {ts_type};")
            return "{ " + " ".join(parts) + " }"
        return "Record<string, unknown>"
    return "unknown"


def _render_typescript_models(schema: dict[str, object]) -> str:
    components = schema.get("components")
    schemas = components.get("schemas") if isinstance(components, dict) else None
    if not isinstance(schemas, dict) or not schemas:
        return "export type UnknownOpenApiSchema = Record<string, unknown>;\n"

    component_name_map = {
        name: _to_pascal_case(name)
        for name in schemas
    }

    sections: list[str] = []
    for schema_name, schema_def in sorted(schemas.items()):
        if not isinstance(schema_def, dict):
            continue
        ts_name = component_name_map[schema_name]
        schema_type = schema_def.get("type")
        properties = schema_def.get("properties")
        required_raw = schema_def.get("required")
        required = set(required_raw) if isinstance(required_raw, list) else set()

        if schema_type == "object" and isinstance(properties, dict) and properties:
            fields: list[str] = []
            for property_name, property_schema in sorted(properties.items()):
                if not isinstance(property_schema, dict):
                    continue
                optional = "" if property_name in required else "?"
                field_type = _schema_to_ts_type(property_schema, component_name_map)
                fields.append(f"  {json.dumps(property_name)}{optional}: {field_type};")
            body = "\n".join(fields)
            sections.append(f"export interface {ts_name} {{\n{body}\n}}")
            continue

        alias_type = _schema_to_ts_type(schema_def, component_name_map)
        sections.append(f"export type {ts_name} = {alias_type};")

    return "\n\n".join(sections) + "\n"


def _resolve_operation_response_type(operation: dict[str, object], component_name_map: dict[str, str]) -> str:
    responses = operation.get("responses")
    if not isinstance(responses, dict):
        return "unknown"

    for status_code in ("200", "201", "202", "204", "default"):
        response = responses.get(status_code)
        if not isinstance(response, dict):
            continue
        content = response.get("content")
        if not isinstance(content, dict):
            if status_code == "204":
                return "void"
            continue
        json_payload = content.get("application/json")
        if not isinstance(json_payload, dict):
            continue
        schema = json_payload.get("schema")
        if not isinstance(schema, dict):
            continue
        return _schema_to_ts_type(schema, component_name_map)
    return "unknown"


def _render_typescript_client(schema: dict[str, object]) -> str:
    paths = schema.get("paths")
    if not isinstance(paths, dict):
        return (
            "export class ApiClient {}\n"
            "export const operations = {} as const;\n"
        )

    components = schema.get("components")
    schemas = components.get("schemas") if isinstance(components, dict) else {}
    component_name_map = {
        name: _to_pascal_case(name)
        for name in schemas
    }

    lines = [
        "export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';",
        "",
        "export interface RequestOptions<TBody = unknown> {",
        "  headers?: Record<string, string>;",
        "  body?: TBody;",
        "  signal?: AbortSignal;",
        "}",
        "",
        "export class ApiClient {",
        "  constructor(private readonly baseUrl: string, private readonly defaultHeaders: Record<string, string> = {}) {}",
        "",
        "  async request<TResponse, TBody = unknown>(method: HttpMethod, path: string, options: RequestOptions<TBody> = {}): Promise<TResponse> {",
        "    const response = await fetch(`${this.baseUrl}${path}`, {",
        "      method,",
        "      headers: { 'content-type': 'application/json', ...this.defaultHeaders, ...(options.headers ?? {}) },",
        "      body: options.body === undefined ? undefined : JSON.stringify(options.body),",
        "      signal: options.signal,",
        "    });",
        "    if (!response.ok) {",
        "      throw new Error(`SDK request failed: ${response.status} ${response.statusText}`);",
        "    }",
        "    if (response.status === 204) {",
        "      return undefined as TResponse;",
        "    }",
        "    return (await response.json()) as TResponse;",
        "  }",
        "}",
        "",
    ]

    operation_lines: list[str] = []
    for raw_path, path_item in sorted(paths.items()):
        if not isinstance(path_item, dict):
            continue
        for method, operation in sorted(path_item.items()):
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            if not isinstance(operation, dict):
                continue

            operation_id = operation.get("operationId")
            if not isinstance(operation_id, str) or not operation_id.strip():
                operation_id = f"{method}_{raw_path}"
            function_name = _to_camel_case(operation_id)

            path_params = re.findall(r"\{([^{}]+)\}", raw_path)
            path_param_signature = ""
            if path_params:
                path_fields = " ".join(f"{_sanitize_identifier(param)}: string;" for param in path_params)
                path_param_signature = f"params: {{ {path_fields} }}, "

            has_request_body = isinstance(operation.get("requestBody"), dict)
            request_body_required = bool(operation.get("requestBody", {}).get("required")) if has_request_body else False
            request_body_signature = ""
            request_body_pass = ""
            if has_request_body:
                optional = "" if request_body_required else "?"
                request_body_signature = f"body{optional}: unknown, "
                request_body_pass = ", { body }"

            method_upper = method.upper()
            path_template = raw_path
            for param in path_params:
                path_template = path_template.replace(
                    "{" + param + "}",
                    f"${{encodeURIComponent(params.{_sanitize_identifier(param)})}}",
                )

            response_type = _resolve_operation_response_type(operation, component_name_map)
            operation_lines.extend(
                [
                    f"export async function {function_name}(",
                    f"  client: ApiClient, {path_param_signature}{request_body_signature}options: RequestOptions = {{}}",
                    f"): Promise<{response_type}> {{",
                    f"  return client.request<{response_type}>('{method_upper}', `{path_template}`{request_body_pass});",
                    "}",
                    "",
                ]
            )

    if not operation_lines:
        operation_lines = ["export const operations = {} as const;", ""]

    lines.extend(operation_lines)
    return "\n".join(lines)


def _render_package_json(package_name: str, version: str) -> str:
    package_json = {
        "name": package_name,
        "version": version,
        "description": "Typed client SDK generated from the Hackathon Service OpenAPI schema.",
        "type": "module",
        "main": "dist/index.js",
        "types": "dist/index.d.ts",
        "files": ["dist", "openapi.json", "README.md"],
        "scripts": {
            "build": "tsc -p tsconfig.json",
            "prepack": "npm run build",
        },
        "devDependencies": {
            "typescript": "^5.6.3",
        },
    }
    return json.dumps(package_json, indent=2, sort_keys=True) + "\n"


def _render_tsconfig() -> str:
    return json.dumps(
        {
            "compilerOptions": {
                "target": "ES2022",
                "module": "ES2022",
                "moduleResolution": "Bundler",
                "declaration": True,
                "outDir": "dist",
                "strict": True,
                "skipLibCheck": True,
            },
            "include": ["src/**/*.ts"],
        },
        indent=2,
        sort_keys=True,
    ) + "\n"


def _render_readme(package_name: str) -> str:
    return (
        f"# {package_name}\n\n"
        "Typed SDK generated from the service OpenAPI schema.\n\n"
        "## Usage\n\n"
        "```ts\n"
        "import { ApiClient } from './dist/index.js';\n"
        "\n"
        "const client = new ApiClient('http://localhost:8000');\n"
        "```\n"
    )


def _build_publishable_tarball(package_dir: Path, package_name: str, version: str) -> Path:
    dist_dir = package_dir / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    tar_name = f"{package_name.lstrip('@').replace('/', '-')}-{version}.tgz"
    tar_path = dist_dir / tar_name

    with tarfile.open(tar_path, "w:gz") as archive:
        for path in sorted(package_dir.rglob("*")):
            if path == tar_path:
                continue
            if path.is_dir():
                continue
            relative = path.relative_to(package_dir)
            archive.add(path, arcname=Path("package") / relative)
    return tar_path


def generate_typed_sdk_package(
    schema: dict[str, object],
    output_dir: Path,
    *,
    package_name: str = "@bengers/hackathon-sdk",
    package_version: str = "0.1.0",
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    src_dir = output_dir / "src"
    src_dir.mkdir(parents=True, exist_ok=True)

    (output_dir / "openapi.json").write_text(json.dumps(schema, indent=2, sort_keys=True), encoding="utf-8")
    (output_dir / "package.json").write_text(_render_package_json(package_name, package_version), encoding="utf-8")
    (output_dir / "tsconfig.json").write_text(_render_tsconfig(), encoding="utf-8")
    (output_dir / "README.md").write_text(_render_readme(package_name), encoding="utf-8")
    (src_dir / "types.ts").write_text(_render_typescript_models(schema), encoding="utf-8")
    (src_dir / "client.ts").write_text(_render_typescript_client(schema), encoding="utf-8")
    (src_dir / "index.ts").write_text("export * from './types';\nexport * from './client';\n", encoding="utf-8")

    return _build_publishable_tarball(output_dir, package_name, package_version)


def generate_sdk_artifacts(
    schema_output_path: Path,
    sdk_output_dir: Path,
    *,
    package_name: str = "@bengers/hackathon-sdk",
    package_version: str = "0.1.0",
) -> tuple[Path, Path]:
    schema = export_openapi_schema(schema_output_path)
    tarball_path = generate_typed_sdk_package(
        schema,
        sdk_output_dir,
        package_name=package_name,
        package_version=package_version,
    )
    return schema_output_path, tarball_path
