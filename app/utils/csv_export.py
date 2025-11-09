"""CSV export utilities for form responses."""

import csv
import io
from typing import List, Dict, Any


def flatten_response_data(data: dict, prefix: str = "") -> dict:
    """
    Flatten nested JSON data for CSV export.

    Args:
        data: The nested dictionary to flatten
        prefix: Prefix for nested keys

    Returns:
        Flattened dictionary
    """
    flattened = {}

    for key, value in data.items():
        new_key = f"{prefix}.{key}" if prefix else key

        if isinstance(value, dict):
            flattened.update(flatten_response_data(value, new_key))
        elif isinstance(value, list):
            flattened[new_key] = ", ".join(str(v) for v in value)
        else:
            flattened[new_key] = value

    return flattened


def responses_to_csv(responses: List[Dict[str, Any]], form_schema: dict) -> str:
    """
    Convert form responses to CSV format.

    Args:
        responses: List of response dictionaries
        form_schema: Form schema to extract field information

    Returns:
        CSV string
    """
    if not responses:
        return ""

    # Create in-memory CSV file
    output = io.StringIO()

    # Flatten all response data
    flattened_responses = []
    all_keys = set()

    for response in responses:
        # Add metadata fields
        flat_data = {
            "response_id": response.get("id", ""),
            "submitted_by": response.get(
                "submitted_by_username", response.get("submitted_by", "")
            ),
            "submitted_at": response.get("submitted_at", ""),
        }

        # Flatten response data
        response_data = response.get("data", {})
        flat_data.update(flatten_response_data(response_data))

        # Add attachments info if present
        if response.get("attachments"):
            attachments = response.get("attachments", {})
            for att_key, att_value in attachments.items():
                flat_data[f"attachment_{att_key}"] = att_value

        flattened_responses.append(flat_data)
        all_keys.update(flat_data.keys())

    # Sort keys for consistent column ordering
    fieldnames = sorted(all_keys)

    # Move metadata fields to the front
    metadata_fields = ["response_id", "submitted_by", "submitted_at"]
    for field in reversed(metadata_fields):
        if field in fieldnames:
            fieldnames.remove(field)
            fieldnames.insert(0, field)

    # Write CSV
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(flattened_responses)

    return output.getvalue()
