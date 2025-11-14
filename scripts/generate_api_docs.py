#!/usr/bin/env python3
"""
Generate comprehensive API documentation from FastAPI OpenAPI schema.

This script reads the OpenAPI schema from the running FastAPI app and generates
a comprehensive Markdown documentation file with all endpoints, request/response
models, and authentication requirements.

Usage:
    python scripts/generate_api_docs.py

Or with custom URL:
    python scripts/generate_api_docs.py --url http://localhost:8000
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


def fetch_openapi_schema(base_url: str) -> dict[str, Any]:
    """Fetch OpenAPI schema from running FastAPI app."""
    try:
        response = requests.get(f"{base_url}/openapi.json", timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching OpenAPI schema: {e}")
        print(f"Make sure the app is running at {base_url}")
        sys.exit(1)


def format_method(method: str) -> str:
    """Format HTTP method with color coding."""
    colors = {
        "get": "🟢",
        "post": "🟡",
        "put": "🔵",
        "delete": "🔴",
        "patch": "🟣",
    }
    return f"{colors.get(method, '⚪')} **{method.upper()}**"


def format_schema_type(schema: dict) -> str:
    """Format schema type for display."""
    if "$ref" in schema:
        return schema["$ref"].split("/")[-1]

    if "type" in schema:
        type_str = schema["type"]
        if type_str == "array" and "items" in schema:
            item_type = format_schema_type(schema["items"])
            return f"Array<{item_type}>"
        elif type_str == "object":
            return "Object"
        return type_str.capitalize()

    if "anyOf" in schema:
        types = [format_schema_type(s) for s in schema["anyOf"]]
        return " | ".join(types)

    if "allOf" in schema:
        types = [format_schema_type(s) for s in schema["allOf"]]
        return " & ".join(types)

    return "Any"


def format_parameters(parameters: list[dict]) -> str:
    """Format parameters table."""
    if not parameters:
        return "_No parameters_\n"

    lines = ["| Parameter | Type | Location | Required | Description |"]
    lines.append("|-----------|------|----------|----------|-------------|")

    for param in parameters:
        name = param.get("name", "")
        location = param.get("in", "")
        required = "✅ Yes" if param.get("required", False) else "❌ No"

        schema = param.get("schema", {})
        param_type = format_schema_type(schema)

        description = param.get("description", "")
        if "enum" in schema:
            description += f" (Options: {', '.join(map(str, schema['enum']))})"

        lines.append(f"| `{name}` | {param_type} | {location} | {required} | {description} |")

    return "\n".join(lines) + "\n"


def format_request_body(request_body: dict, components: dict) -> str:
    """Format request body documentation."""
    if not request_body:
        return "_No request body_\n"

    content = request_body.get("content", {})
    if not content:
        return "_No request body_\n"

    lines = []

    for content_type, schema_info in content.items():
        lines.append(f"**Content-Type:** `{content_type}`\n")

        schema = schema_info.get("schema", {})

        if "$ref" in schema:
            schema_name = schema["$ref"].split("/")[-1]
            lines.append(f"**Schema:** `{schema_name}`\n")

            # Get schema definition
            schema_def = components.get("schemas", {}).get(schema_name, {})
            properties = schema_def.get("properties", {})
            required_fields = schema_def.get("required", [])

            if properties:
                lines.append("**Fields:**\n")
                lines.append("| Field | Type | Required | Description |")
                lines.append("|-------|------|----------|-------------|")

                for field_name, field_schema in properties.items():
                    field_type = format_schema_type(field_schema)
                    is_required = "✅ Yes" if field_name in required_fields else "❌ No"
                    description = field_schema.get("description", "")

                    lines.append(f"| `{field_name}` | {field_type} | {is_required} | {description} |")
        else:
            schema_type = format_schema_type(schema)
            lines.append(f"**Type:** {schema_type}\n")

    return "\n".join(lines) + "\n"


def format_responses(responses: dict, components: dict) -> str:
    """Format response documentation."""
    if not responses:
        return "_No documented responses_\n"

    lines = []

    for status_code, response_info in sorted(responses.items()):
        description = response_info.get("description", "")
        lines.append(f"#### {status_code} - {description}\n")

        content = response_info.get("content", {})
        for content_type, schema_info in content.items():
            schema = schema_info.get("schema", {})

            if "$ref" in schema:
                schema_name = schema["$ref"].split("/")[-1]
                lines.append(f"**Schema:** `{schema_name}`\n")
            else:
                schema_type = format_schema_type(schema)
                lines.append(f"**Type:** {schema_type}\n")

        lines.append("")

    return "\n".join(lines)


def generate_endpoint_docs(path: str, method: str, endpoint: dict, components: dict) -> str:
    """Generate documentation for a single endpoint."""
    lines = []

    # Header
    summary = endpoint.get("summary", "")
    lines.append(f"### {format_method(method)} `{path}`")
    lines.append(f"\n**Summary:** {summary}\n")

    # Description
    description = endpoint.get("description", "")
    if description:
        lines.append(f"{description}\n")

    # Tags
    tags = endpoint.get("tags", [])
    if tags:
        tag_badges = " ".join([f"`{tag}`" for tag in tags])
        lines.append(f"**Tags:** {tag_badges}\n")

    # Security
    security = endpoint.get("security", [])
    if security:
        lines.append("**Authentication:** 🔒 Required\n")
    else:
        lines.append("**Authentication:** 🔓 Not required\n")

    # Parameters
    parameters = endpoint.get("parameters", [])
    if parameters:
        lines.append("#### Parameters\n")
        lines.append(format_parameters(parameters))

    # Request Body
    request_body = endpoint.get("requestBody", {})
    if request_body:
        lines.append("#### Request Body\n")
        lines.append(format_request_body(request_body, components))

    # Responses
    responses = endpoint.get("responses", {})
    if responses:
        lines.append("#### Responses\n")
        lines.append(format_responses(responses, components))

    lines.append("---\n")

    return "\n".join(lines)


def organize_by_tags(paths: dict, components: dict) -> dict[str, list[tuple[str, str, dict]]]:
    """Organize endpoints by tags."""
    organized = {}

    for path, methods in paths.items():
        for method, endpoint in methods.items():
            if method in ["get", "post", "put", "delete", "patch"]:
                tags = endpoint.get("tags", ["Uncategorized"])

                for tag in tags:
                    if tag not in organized:
                        organized[tag] = []
                    organized[tag].append((path, method, endpoint))

    return organized


def generate_documentation(schema: dict) -> str:
    """Generate complete API documentation."""
    info = schema.get("info", {})
    paths = schema.get("paths", {})
    components = schema.get("components", {})

    lines = [
        "# SDIGdata API Documentation",
        "",
        f"**Version:** {info.get('version', 'N/A')}",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Overview",
        "",
        info.get("description", "SDIGdata Backend API"),
        "",
        "## Base URL",
        "",
        "```",
        "http://localhost:8000",
        "```",
        "",
        "## Authentication",
        "",
        "Most endpoints require JWT authentication. Include the token in the Authorization header:",
        "",
        "```",
        "Authorization: Bearer <your_jwt_token>",
        "```",
        "",
        "Some endpoints support API key authentication via the `X-API-Key` header.",
        "",
        "## Response Format",
        "",
        "All responses follow this standard format:",
        "",
        "```json",
        "{",
        '  "success": true,',
        '  "message": "Operation completed successfully",',
        '  "data": { ... },',
        '  "errors": null',
        "}",
        "```",
        "",
        "## Error Codes",
        "",
        "| Code | Description |",
        "|------|-------------|",
        "| 200 | Success |",
        "| 201 | Created |",
        "| 204 | No Content |",
        "| 400 | Bad Request |",
        "| 401 | Unauthorized |",
        "| 403 | Forbidden |",
        "| 404 | Not Found |",
        "| 422 | Validation Error |",
        "| 500 | Internal Server Error |",
        "",
        "## Table of Contents",
        "",
    ]

    # Organize endpoints by tags
    organized = organize_by_tags(paths, components)

    # Generate TOC
    for tag in sorted(organized.keys()):
        tag_id = tag.lower().replace(" ", "-")
        endpoint_count = len(organized[tag])
        lines.append(f"- [{tag}](#{tag_id}) ({endpoint_count} endpoints)")

    lines.append("")
    lines.append("---")
    lines.append("")

    # Generate endpoint documentation by tag
    for tag in sorted(organized.keys()):
        tag_id = tag.lower().replace(" ", "-")
        lines.append(f"## {tag}")
        lines.append("")

        endpoints = organized[tag]

        # Sort endpoints by path and method
        endpoints.sort(key=lambda x: (x[0], x[1]))

        for path, method, endpoint in endpoints:
            lines.append(generate_endpoint_docs(path, method, endpoint, components))

    # Schemas section
    schemas = components.get("schemas", {})
    if schemas:
        lines.append("## Data Models")
        lines.append("")

        for schema_name in sorted(schemas.keys()):
            schema_def = schemas[schema_name]
            lines.append(f"### {schema_name}")
            lines.append("")

            description = schema_def.get("description", "")
            if description:
                lines.append(f"{description}\n")

            properties = schema_def.get("properties", {})
            required_fields = schema_def.get("required", [])

            if properties:
                lines.append("| Field | Type | Required | Description |")
                lines.append("|-------|------|----------|-------------|")

                for field_name, field_schema in properties.items():
                    field_type = format_schema_type(field_schema)
                    is_required = "✅ Yes" if field_name in required_fields else "❌ No"
                    description = field_schema.get("description", "")

                    lines.append(f"| `{field_name}` | {field_type} | {is_required} | {description} |")

                lines.append("")

            lines.append("---")
            lines.append("")

    return "\n".join(lines)


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Generate API documentation from OpenAPI schema")
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Base URL of the running API (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--output",
        default="API_DOCUMENTATION.md",
        help="Output file path (default: API_DOCUMENTATION.md)"
    )

    args = parser.parse_args()

    print(f"Fetching OpenAPI schema from {args.url}...")
    schema = fetch_openapi_schema(args.url)

    print("Generating documentation...")
    documentation = generate_documentation(schema)

    output_path = Path(args.output)
    output_path.write_text(documentation, encoding="utf-8")

    print(f"✅ Documentation generated successfully: {output_path}")
    print(f"📄 File size: {len(documentation)} bytes")

    # Count endpoints
    paths = schema.get("paths", {})
    endpoint_count = sum(
        1 for methods in paths.values()
        for method in methods.keys()
        if method in ["get", "post", "put", "delete", "patch"]
    )
    print(f"📊 Total endpoints documented: {endpoint_count}")


if __name__ == "__main__":
    main()
