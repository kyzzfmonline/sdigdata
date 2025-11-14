"""Seed default form templates into the database."""

import asyncio
import json
import sys
from uuid import uuid4

import asyncpg

# Add parent directory to path
sys.path.insert(0, "/root/workspace/sdigdata")

from app.core.config import get_settings


async def seed_templates():
    """Seed default form templates."""
    settings = get_settings()
    conn = await asyncpg.connect(dsn=settings.DATABASE_URL)

    # Get or create admin user for template ownership
    admin_user = await conn.fetchrow(
        "SELECT id FROM users WHERE role = 'admin' LIMIT 1"
    )

    if not admin_user:
        print("⚠ No admin user found. Creating system user for templates...")
        # Create a system admin user
        admin_id = await conn.fetchval(
            """
            INSERT INTO users (username, password_hash, role, organization_id)
            SELECT 'system', 'unused', 'admin', id
            FROM organizations LIMIT 1
            RETURNING id
            """
        )
    else:
        admin_id = admin_user["id"]

    print(f"✓ Using admin user ID: {admin_id}")

    # Template 1: Community Survey
    community_survey = {
        "name": "Community Survey",
        "description": "Standard community survey template with demographics and feedback",
        "category": "survey",
        "form_schema": {
            "branding": {
                "logo_url": "https://example.com/logo.png",
                "primary_color": "#0066CC",
                "header_text": "Community Survey",
                "footer_text": "Thank you for your participation",
            },
            "fields": [
                {
                    "id": "name",
                    "type": "text",
                    "label": "Full Name",
                    "required": True,
                    "placeholder": "Enter your full name",
                },
                {
                    "id": "age",
                    "type": "number",
                    "label": "Age",
                    "required": True,
                    "placeholder": "Enter your age",
                },
                {
                    "id": "gender",
                    "type": "select",
                    "label": "Gender",
                    "required": True,
                    "options": ["Male", "Female", "Other", "Prefer not to say"],
                },
                {
                    "id": "location",
                    "type": "gps",
                    "label": "Current Location",
                    "required": True,
                },
                {
                    "id": "satisfaction",
                    "type": "select",
                    "label": "Overall Satisfaction",
                    "required": True,
                    "options": [
                        "Very Satisfied",
                        "Satisfied",
                        "Neutral",
                        "Dissatisfied",
                        "Very Dissatisfied",
                    ],
                },
                {
                    "id": "feedback",
                    "type": "textarea",
                    "label": "Additional Feedback",
                    "required": False,
                    "placeholder": "Share your thoughts...",
                },
            ],
        },
        "tags": ["survey", "community", "feedback"],
        "is_public": True,
    }

    # Template 2: Event Registration
    event_registration = {
        "name": "Event Registration",
        "description": "Standard event registration form with participant details",
        "category": "registration",
        "form_schema": {
            "branding": {
                "logo_url": "https://example.com/logo.png",
                "primary_color": "#1976d2",
                "header_text": "Event Registration",
                "footer_text": "We look forward to seeing you!",
            },
            "fields": [
                {
                    "id": "participant_name",
                    "type": "text",
                    "label": "Participant Name",
                    "required": True,
                },
                {
                    "id": "email",
                    "type": "email",
                    "label": "Email Address",
                    "required": True,
                },
                {
                    "id": "phone",
                    "type": "text",
                    "label": "Phone Number",
                    "required": True,
                },
                {
                    "id": "organization",
                    "type": "text",
                    "label": "Organization",
                    "required": False,
                },
                {
                    "id": "dietary_requirements",
                    "type": "select",
                    "label": "Dietary Requirements",
                    "required": False,
                    "options": ["None", "Vegetarian", "Vegan", "Halal", "Other"],
                },
                {
                    "id": "special_needs",
                    "type": "textarea",
                    "label": "Special Needs/Accommodations",
                    "required": False,
                },
            ],
        },
        "tags": ["registration", "event", "participants"],
        "is_public": True,
    }

    # Template 3: Complaint Form
    complaint_form = {
        "name": "Complaint Form",
        "description": "Standard complaint form for citizen feedback",
        "category": "feedback",
        "form_schema": {
            "branding": {
                "logo_url": "https://example.com/logo.png",
                "primary_color": "#d32f2f",
                "header_text": "Submit a Complaint",
                "footer_text": "Your feedback helps us improve",
            },
            "fields": [
                {
                    "id": "complainant_name",
                    "type": "text",
                    "label": "Your Name",
                    "required": True,
                },
                {
                    "id": "contact_info",
                    "type": "text",
                    "label": "Contact Information",
                    "required": True,
                },
                {
                    "id": "complaint_type",
                    "type": "select",
                    "label": "Type of Complaint",
                    "required": True,
                    "options": [
                        "Service Quality",
                        "Staff Behavior",
                        "Facilities",
                        "Sanitation",
                        "Infrastructure",
                        "Other",
                    ],
                },
                {
                    "id": "location",
                    "type": "gps",
                    "label": "Location of Issue",
                    "required": True,
                },
                {
                    "id": "description",
                    "type": "textarea",
                    "label": "Detailed Description",
                    "required": True,
                    "placeholder": "Please provide details about your complaint...",
                },
                {
                    "id": "photo",
                    "type": "photo",
                    "label": "Upload Photo Evidence",
                    "required": False,
                },
            ],
        },
        "tags": ["complaint", "feedback", "citizen-service"],
        "is_public": True,
    }

    # Template 4: Property Inspection
    property_inspection = {
        "name": "Property Inspection",
        "description": "Comprehensive property inspection checklist",
        "category": "inspection",
        "form_schema": {
            "branding": {
                "logo_url": "https://example.com/logo.png",
                "primary_color": "#388e3c",
                "header_text": "Property Inspection",
                "footer_text": "Metropolitan Assembly Inspection",
            },
            "fields": [
                {
                    "id": "property_address",
                    "type": "text",
                    "label": "Property Address",
                    "required": True,
                },
                {
                    "id": "property_location",
                    "type": "gps",
                    "label": "GPS Location",
                    "required": True,
                },
                {
                    "id": "owner_name",
                    "type": "text",
                    "label": "Property Owner Name",
                    "required": True,
                },
                {
                    "id": "property_type",
                    "type": "select",
                    "label": "Property Type",
                    "required": True,
                    "options": [
                        "Residential",
                        "Commercial",
                        "Industrial",
                        "Mixed-Use",
                        "Other",
                    ],
                },
                {
                    "id": "property_photo",
                    "type": "photo",
                    "label": "Property Photo",
                    "required": True,
                },
                {
                    "id": "structural_condition",
                    "type": "select",
                    "label": "Structural Condition",
                    "required": True,
                    "options": ["Excellent", "Good", "Fair", "Poor", "Dangerous"],
                },
                {
                    "id": "notes",
                    "type": "textarea",
                    "label": "Inspection Notes",
                    "required": False,
                },
            ],
        },
        "tags": ["inspection", "property", "assessment"],
        "is_public": True,
    }

    # Template 5: Health Screening
    health_screening = {
        "name": "Health Screening",
        "description": "Basic health screening form with medical history",
        "category": "health",
        "form_schema": {
            "branding": {
                "logo_url": "https://example.com/logo.png",
                "primary_color": "#7b1fa2",
                "header_text": "Health Screening",
                "footer_text": "Your health information is confidential",
            },
            "fields": [
                {
                    "id": "patient_name",
                    "type": "text",
                    "label": "Patient Name",
                    "required": True,
                },
                {
                    "id": "date_of_birth",
                    "type": "date",
                    "label": "Date of Birth",
                    "required": True,
                },
                {
                    "id": "gender",
                    "type": "select",
                    "label": "Gender",
                    "required": True,
                    "options": ["Male", "Female", "Other"],
                },
                {
                    "id": "temperature",
                    "type": "number",
                    "label": "Temperature (°C)",
                    "required": True,
                },
                {
                    "id": "blood_pressure",
                    "type": "text",
                    "label": "Blood Pressure",
                    "required": False,
                },
                {
                    "id": "symptoms",
                    "type": "textarea",
                    "label": "Current Symptoms",
                    "required": False,
                    "placeholder": "List any symptoms you are experiencing...",
                },
                {
                    "id": "consent",
                    "type": "checkbox",
                    "label": "I consent to this health screening",
                    "required": True,
                },
            ],
        },
        "tags": ["health", "screening", "medical"],
        "is_public": True,
    }

    templates = [
        community_survey,
        event_registration,
        complaint_form,
        property_inspection,
        health_screening,
    ]

    inserted_count = 0
    for template in templates:
        # Check if template already exists
        existing = await conn.fetchval(
            "SELECT id FROM form_templates WHERE name = $1", template["name"]
        )

        if existing:
            print(f"  ⏭ Template '{template['name']}' already exists, skipping...")
            continue

        # Insert template
        await conn.execute(
            """
            INSERT INTO form_templates (
                name, description, category, form_schema, tags, is_public, created_by
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            template["name"],
            template["description"],
            template["category"],
            json.dumps(template["form_schema"]),
            template["tags"],
            template["is_public"],
            str(admin_id),
        )
        print(f"  ✓ Inserted template: {template['name']}")
        inserted_count += 1

    print(f"\n✓ Seeded {inserted_count} form templates successfully!")
    await conn.close()


if __name__ == "__main__":
    asyncio.run(seed_templates())
