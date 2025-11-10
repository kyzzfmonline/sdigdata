# SDIGdata Backend - Postman Collection Guide

This guide will help you get started with testing the SDIGdata Backend API using Postman.

## Quick Start

### 1. Import the Postman Collection

1. Open Postman
2. Click on **Import** button (top left)
3. Select the `postman_collection.json` file from this repository
4. The collection will be imported with all endpoints organized into folders

### 2. Set Base URL (Optional)

The collection is pre-configured with `base_url = http://localhost:8000`. If your API is running on a different host/port:

1. Click on the collection name "SDIGdata Backend API"
2. Go to the **Variables** tab
3. Update the `base_url` value
4. Click **Save**

## Authentication Workflow

### Option 1: Bootstrap First Admin (Fresh Installation)

If you're setting up the system for the first time and no admin users exist:

1. **Run: Authentication → Bootstrap Admin (First Admin)**
   - Request Body:
   ```json
   {
     "username": "admin",
     "password": "SecurePass123!"
   }
   ```
   - This will automatically save the `admin_id` and `organization_id` to collection variables
   - ⚠️ This endpoint only works when NO admin users exist in the database

2. **Run: Authentication → Login**
   - Use the same credentials to login and get your JWT token
   - The token will be automatically saved to the `access_token` variable
   - All subsequent requests will use this token automatically

### Option 2: Login with Existing Admin

If admin users already exist in the system:

1. **Run: Authentication → Login**
   - Request Body:
   ```json
   {
     "username": "admin",
     "password": "your_password"
   }
   ```
   - The JWT token will be automatically saved and used for authenticated requests

## Testing Flow

After authentication, follow this recommended testing flow:

### 1. Organizations

```
1. Create Organization (optional - default org exists)
2. List Organizations
3. Get Organization by ID
4. Update Organization
```

### 2. User Management

```
1. Register Agent (Admin Only) - Creates an agent user
   - The agent_id is automatically saved to variables
```

### 3. Forms

```
1. Create Form - Create a data collection form
2. List Forms - View all forms
3. Get Form by ID - View specific form
4. Assign Form to Agent - Allow agents to collect data
5. Get Assigned Agents - See who can submit responses
```

### 4. Data Collection

```
1. Submit Response - Submit form data with GPS and attachments
   - Automatic ML quality scoring is applied
2. List Responses - View all submitted responses
3. Get Response by ID - View specific response
```

### 5. ML & AI Features

```
1. Get Training Data - Export high-quality data for ML training
2. Get Spatial Data (GeoJSON) - Export geospatial data
3. Get Quality Statistics - View data quality metrics
4. Bulk Export for ML - Export data in JSON/JSONL format
5. Get Temporal Trends - View time-series data
6. List ML Datasets - View available datasets
```

## Collection Variables

The collection uses variables to automatically pass data between requests:

| Variable | Description | Auto-populated |
|----------|-------------|----------------|
| `base_url` | API base URL | No (default: http://localhost:8000) |
| `access_token` | JWT authentication token | Yes (from login) |
| `admin_id` | Admin user ID | Yes (from login/bootstrap) |
| `organization_id` | Organization UUID | Yes (from bootstrap/org creation) |
| `form_id` | Form UUID | Yes (from form creation) |
| `agent_id` | Agent user ID | Yes (from agent registration) |
| `response_id` | Response UUID | Yes (from response submission) |

These variables are automatically populated by test scripts in the requests, so you don't need to copy/paste IDs manually.

## Password Requirements

When creating users (admin or agent), passwords must meet these requirements:

- Minimum 8 characters
- At least 1 uppercase letter
- At least 1 lowercase letter
- At least 1 digit
- At least 1 special character (!@#$%^&*()_+-=[]{}|;:,.<>?)
- Not a common password (e.g., "password", "123456", etc.)
- No long sequential patterns (e.g., "abcd", "1234")

✅ Valid example: `SecurePass123!`
❌ Invalid examples: `password`, `12345678`, `Abcd1234`

## Username Requirements

Usernames must meet these requirements:

- Minimum 3 characters, maximum 50 characters
- Only alphanumeric characters, dots, hyphens, and underscores
- Cannot start or end with special characters
- Cannot have consecutive special characters

✅ Valid examples: `admin`, `john_doe`, `agent-1`, `user.name`
❌ Invalid examples: `.admin`, `user..name`, `a`, `user@name`

## Advanced Features

### File Upload Workflow

To upload files (photos, signatures, etc.):

1. **Run: Files → Get Presigned Upload URL**
   - Specify filename and content type
   - Receive `upload_url` (for uploading) and `file_url` (for storing in DB)

2. **Upload the file** (not in collection, use your own client):
   - PUT request to the `upload_url` with the file data

3. **Store the `file_url`** in your form response attachments

### ML Data Export

The ML endpoints support various export formats:

- **JSON**: Structured data with metadata
- **JSONL**: JSON Lines format (one object per line) for streaming
- **GeoJSON**: Standard geospatial format with Point geometries
- **CSV**: Tabular format (via form export endpoint)

Quality filtering options:
- `min_quality`: Minimum quality score (0.0-1.0)
- `suitable_only`: Only include data suitable for ML training
- `form_id`: Filter by specific form

## API Documentation

Interactive API documentation is available at:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Troubleshooting

### "Cannot create bootstrap admin: admin users already exist"

This is expected if you've already created an admin user. Use the **Login** endpoint instead, or use the **Register Agent** endpoint (requires admin authentication) to create new users.

### "Invalid authentication credentials"

Your JWT token may have expired. Run the **Login** endpoint again to get a fresh token.

### "Admin access required"

You're trying to access an admin-only endpoint with an agent account. Login with an admin account instead.

### "Form not found" / "Response not found"

Make sure you've run the prerequisite requests in order. The collection variables need to be populated with valid IDs.

## Support

For issues or questions:
- Check the API docs at http://localhost:8000/docs
- Review the `README.md` in the repository
- Check application logs: `docker-compose logs -f api`

## Example Complete Workflow

Here's a complete workflow from start to finish:

```
1. Bootstrap Admin (First Admin) → Creates first admin user
2. Login → Get JWT token
3. Create Organization → Create new organization (optional)
4. Register Agent → Create agent user
5. Create Form → Create data collection form
6. Assign Form to Agent → Allow agent to submit responses
7. Submit Response → Submit form data (as agent or admin)
8. Get Quality Statistics → View ML quality metrics
9. Get Training Data → Export high-quality data for ML
10. Bulk Export for ML → Download complete dataset
```

Each step automatically populates variables for the next step, making the workflow seamless.
