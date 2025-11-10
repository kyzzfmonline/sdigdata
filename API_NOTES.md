# API Implementation Notes

## Field Naming

### Form Creation Endpoint

**Important:** The API uses `form_schema` (not `schema`) in request bodies to avoid conflicts with Pydantic's internal `schema` attribute.

**Correct payload:**
```json
POST /forms
{
  "title": "Household Survey 2025",
  "organization_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "draft",
  "form_schema": {
    "branding": {
      "logo_url": "https://example.com/logo.png",
      "primary_color": "#0066CC",
      "header_text": "KMA",
      "footer_text": "Thank you!"
    },
    "fields": [...]
  }
}
```

**Note:** In the database and response objects, this is still stored as `schema` (the JSON column). Only the creation request uses `form_schema` to avoid the Pydantic conflict.

## Database Schema

In PostgreSQL, the forms table uses:
- Column name: `schema` (JSONB type)
- This is fine because SQL doesn't have the same naming conflicts as Python/Pydantic

## Why This Matters

Pydantic v2's `BaseModel` has a reserved `schema` attribute for JSON schema generation. Using `schema` as a field name causes a `UserWarning`. By using `form_schema` in the API request model, we avoid this conflict while maintaining backward compatibility at the database level.
