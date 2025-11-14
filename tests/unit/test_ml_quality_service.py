"""
Unit tests for ML quality service functions.
"""

from datetime import datetime, timedelta

from app.services.ml_quality import (
    calculate_completeness_score,
    calculate_consistency_score,
    calculate_gps_accuracy_score,
    calculate_overall_quality,
    calculate_photo_quality_score,
    calculate_response_time_score,
)


class TestMLQualityService:
    """Test ML quality service functions."""

    def test_calculate_completeness_score_no_fields(self):
        """Test completeness score with no fields in schema."""
        response_data = {"name": "John"}
        form_schema = {}

        score = calculate_completeness_score(response_data, form_schema)

        assert score == 1.0

    def test_calculate_completeness_score_no_required_fields(self):
        """Test completeness score with no required fields."""
        response_data = {"name": "John", "age": 30}
        form_schema = {
            "fields": [
                {"id": "name", "required": False},
                {"id": "age", "required": False},
            ]
        }

        score = calculate_completeness_score(response_data, form_schema)

        assert score == 1.0

    def test_calculate_completeness_score_all_required_filled(self):
        """Test completeness score when all required fields are filled."""
        response_data = {"name": "John", "age": 30, "email": "john@example.com"}
        form_schema = {
            "fields": [
                {"id": "name", "required": True},
                {"id": "age", "required": True},
                {"id": "email", "required": False},
            ]
        }

        score = calculate_completeness_score(response_data, form_schema)

        assert score == 1.0

    def test_calculate_completeness_score_partial_required_filled(self):
        """Test completeness score when some required fields are filled."""
        response_data = {"name": "John", "email": "john@example.com"}
        form_schema = {
            "fields": [
                {"id": "name", "required": True},
                {"id": "age", "required": True},
                {"id": "email", "required": False},
            ]
        }

        score = calculate_completeness_score(response_data, form_schema)

        assert score == 0.5  # 1 out of 2 required fields filled

    def test_calculate_completeness_score_no_required_filled(self):
        """Test completeness score when no required fields are filled."""
        response_data = {"email": "john@example.com"}
        form_schema = {
            "fields": [
                {"id": "name", "required": True},
                {"id": "age", "required": True},
            ]
        }

        score = calculate_completeness_score(response_data, form_schema)

        assert score == 0.0

    def test_calculate_gps_accuracy_score_no_location(self):
        """Test GPS accuracy score with no location data."""
        response_data = {"name": "John"}

        score = calculate_gps_accuracy_score(response_data)

        assert score == 0.0

    def test_calculate_gps_accuracy_score_invalid_location(self):
        """Test GPS accuracy score with invalid location data."""
        response_data = {"location": {}}  # Empty location dict

        score = calculate_gps_accuracy_score(response_data)

        assert score == 0.0

    def test_calculate_gps_accuracy_score_high_accuracy(self):
        """Test GPS accuracy score with high accuracy location."""
        response_data = {
            "location": {
                "latitude": 5.6037,
                "longitude": -0.1870,
                "accuracy": 5,  # High accuracy
            }
        }

        score = calculate_gps_accuracy_score(response_data)

        assert score == 1.0

    def test_calculate_gps_accuracy_score_medium_accuracy(self):
        """Test GPS accuracy score with medium accuracy location."""
        response_data = {
            "location": {
                "latitude": 5.6037,
                "longitude": -0.1870,
                "accuracy": 50,  # Medium accuracy
            }
        }

        score = calculate_gps_accuracy_score(response_data)

        assert score == 0.6  # accuracy <= 50 returns 0.6

    def test_calculate_gps_accuracy_score_low_accuracy(self):
        """Test GPS accuracy score with low accuracy location."""
        response_data = {
            "location": {
                "latitude": 5.6037,
                "longitude": -0.1870,
                "accuracy": 200,  # Low accuracy
            }
        }

        score = calculate_gps_accuracy_score(response_data)

        assert score == 0.2  # accuracy > 100 returns 0.2

    def test_calculate_photo_quality_score_no_attachments(self):
        """Test photo quality score with no attachments."""
        attachments = {}

        score = calculate_photo_quality_score(attachments)

        assert score == 0.5  # Returns 0.5 for no attachments

    def test_calculate_photo_quality_score_with_photos(self):
        """Test photo quality score with photo attachments."""
        attachments = {
            "photo1": {"type": "image/jpeg", "size": 1024000},  # 1MB
            "photo2": {"type": "image/png", "size": 512000},  # 512KB
        }

        score = calculate_photo_quality_score(attachments)

        assert score > 0.0  # Should be positive

    def test_calculate_response_time_score_fast_response(self):
        """Test response time score for fast response."""
        submitted_at = datetime.now()
        created_at = submitted_at - timedelta(minutes=5)  # 5 minutes

        score = calculate_response_time_score(submitted_at, created_at)

        assert score == 0.7  # Currently returns fixed 0.7

    def test_calculate_response_time_score_slow_response(self):
        """Test response time score for slow response."""
        submitted_at = datetime.now()
        created_at = submitted_at - timedelta(days=7)  # 7 days

        score = calculate_response_time_score(submitted_at, created_at)

        assert score < 1.0  # Slower response

    def test_calculate_response_time_score_no_created_at(self):
        """Test response time score with no created_at."""
        submitted_at = datetime.now()

        score = calculate_response_time_score(submitted_at)

        assert score == 0.7  # Currently returns fixed 0.7

    def test_calculate_consistency_score(self):
        """Test consistency score calculation."""
        response_data = {
            "age": 25,
            "years_experience": 5,
            "education_level": "bachelor",
        }

        score = calculate_consistency_score(response_data)

        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_calculate_overall_quality(self):
        """Test overall quality calculation."""

        overall = calculate_overall_quality(
            completeness=0.8,
            gps_accuracy=0.9,
            photo_quality=0.7,
            response_time=0.6,
            consistency=0.8,
        )

        assert isinstance(overall, float)
        assert 0.0 <= overall <= 1.0
