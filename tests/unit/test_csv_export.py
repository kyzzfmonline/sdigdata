"""
Unit tests for CSV export utilities.
"""

from uuid import uuid4

from app.utils.csv_export import flatten_response_data, responses_to_csv


class TestCSVExport:
    """Test CSV export utilities."""

    def test_flatten_response_data_simple(self):
        """Test flattening simple flat data."""
        data = {"name": "John", "age": 30, "city": "Accra"}

        result = flatten_response_data(data)

        assert result == data

    def test_flatten_response_data_nested(self):
        """Test flattening nested dictionary data."""
        data = {
            "name": "John",
            "address": {
                "street": "Main St",
                "city": "Accra",
                "coordinates": {"lat": 5.6037, "lng": -0.1870},
            },
            "hobbies": ["reading", "coding"],
        }

        result = flatten_response_data(data)

        expected = {
            "name": "John",
            "address.street": "Main St",
            "address.city": "Accra",
            "address.coordinates.lat": 5.6037,
            "address.coordinates.lng": -0.1870,
            "hobbies": "reading, coding",
        }

        assert result == expected

    def test_flatten_response_data_empty(self):
        """Test flattening empty data."""
        data = {}

        result = flatten_response_data(data)

        assert result == {}

    def test_flatten_response_data_with_prefix(self):
        """Test flattening with custom prefix."""
        data = {"street": "Main St", "city": "Accra"}

        result = flatten_response_data(data, "address")

        expected = {"address.street": "Main St", "address.city": "Accra"}

        assert result == expected

    def test_responses_to_csv_empty_list(self):
        """Test CSV export with empty responses list."""
        responses = []
        form_schema = {"fields": []}

        result = responses_to_csv(responses, form_schema)

        assert result == ""

    def test_responses_to_csv_single_response(self):
        """Test CSV export with single response."""
        responses = [
            {
                "id": str(uuid4()),
                "submitted_by": str(uuid4()),
                "submitted_by_username": "testuser",
                "submitted_at": "2023-01-01T10:00:00Z",
                "data": {
                    "name": "John Doe",
                    "age": 30,
                    "location": {"city": "Accra", "country": "Ghana"},
                },
                "attachments": {"photo": "photo.jpg", "document": "doc.pdf"},
            }
        ]
        form_schema = {"fields": []}

        result = responses_to_csv(responses, form_schema)

        # Check that CSV contains header and data
        lines = result.strip().split("\n")
        assert len(lines) == 2  # Header + 1 data row

        # Check header contains expected columns
        header = lines[0]
        assert "response_id" in header
        assert "submitted_by" in header
        assert "submitted_at" in header
        assert "name" in header
        assert "age" in header
        assert "location.city" in header
        assert "location.country" in header
        assert "attachment_photo" in header
        assert "attachment_document" in header

    def test_responses_to_csv_multiple_responses(self):
        """Test CSV export with multiple responses having different fields."""
        responses = [
            {
                "id": str(uuid4()),
                "submitted_by_username": "user1",
                "submitted_at": "2023-01-01T10:00:00Z",
                "data": {"name": "John", "age": 30},
            },
            {
                "id": str(uuid4()),
                "submitted_by_username": "user2",
                "submitted_at": "2023-01-02T11:00:00Z",
                "data": {
                    "name": "Jane",
                    "email": "jane@example.com",
                    "department": "IT",
                },
            },
        ]
        form_schema = {"fields": []}

        result = responses_to_csv(responses, form_schema)

        lines = result.strip().split("\n")
        assert len(lines) == 3  # Header + 2 data rows

        # Check that all fields from both responses are included
        header = lines[0]
        assert "name" in header
        assert "age" in header
        assert "email" in header
        assert "department" in header

    def test_responses_to_csv_metadata_fields_order(self):
        """Test that metadata fields appear first in CSV."""
        responses = [
            {
                "id": str(uuid4()),
                "submitted_by_username": "testuser",
                "submitted_at": "2023-01-01T10:00:00Z",
                "data": {"name": "John", "age": 30},
            }
        ]
        form_schema = {"fields": []}

        result = responses_to_csv(responses, form_schema)

        lines = result.strip().split("\n")
        header = lines[0].split(",")

        # Check that metadata fields are at the beginning
        assert header[0] == "response_id"
        assert header[1] == "submitted_by"
        assert header[2] == "submitted_at"

    def test_responses_to_csv_no_attachments(self):
        """Test CSV export without attachments."""
        responses = [
            {
                "id": str(uuid4()),
                "submitted_by_username": "testuser",
                "submitted_at": "2023-01-01T10:00:00Z",
                "data": {"name": "John", "age": 30},
            }
        ]
        form_schema = {"fields": []}

        result = responses_to_csv(responses, form_schema)

        # Should not contain attachment columns
        assert "attachment_" not in result

    def test_responses_to_csv_special_characters(self):
        """Test CSV export with special characters and commas."""
        responses = [
            {
                "id": str(uuid4()),
                "submitted_by_username": "test,user",
                "submitted_at": "2023-01-01T10:00:00Z",
                "data": {"name": "John, Doe", "notes": "Line 1\nLine 2"},
            }
        ]
        form_schema = {"fields": []}

        result = responses_to_csv(responses, form_schema)

        # CSV should handle special characters properly
        # Check that the result contains the expected data
        assert "test,user" in result  # Comma in username should be quoted
        assert "John, Doe" in result  # Comma in name should be quoted
        assert "Line 1" in result and "Line 2" in result  # Newlines should be handled
