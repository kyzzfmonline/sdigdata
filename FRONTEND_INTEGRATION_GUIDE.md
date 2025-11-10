# Frontend Integration Guide

This guide provides instructions for integrating your frontend application with the SDIGdata API.

## CORS Configuration

The API is configured to allow requests from `http://localhost:3000` (development) and production domains. If you're getting CORS errors:

### 1. Ensure Frontend Runs on Correct Port
- Development: Run your frontend on `http://localhost:3000`
- For other ports, update the CORS origins in `app/main.py`

### 2. Include Credentials in Fetch Requests

**JavaScript (fetch API):**
```javascript
const response = await fetch('http://localhost:8000/api/responses', {
  method: 'GET',
  credentials: 'include',  // Required for cookies/authentication
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`  // If using token auth
  }
});
```

**Axios:**
```javascript
import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000/api',
  withCredentials: true,  // Required for cookies
  headers: {
    'Content-Type': 'application/json'
  }
});
```

**React (with useEffect):**
```javascript
useEffect(() => {
  const fetchData = async () => {
    try {
      const response = await fetch('/api/responses', {
        credentials: 'include'
      });
      const data = await response.json();
      setData(data);
    } catch (error) {
      console.error('Error fetching data:', error);
    }
  };

  fetchData();
}, []);
```

### 3. Authentication Headers
For protected endpoints, include the Authorization header:
```javascript
headers: {
  'Authorization': `Bearer ${your_jwt_token}`
}
```

## API Endpoints

### Authentication
- `POST /auth/login` - Login with credentials
- `POST /auth/logout` - Logout
- `GET /auth/me` - Get current user info

### Forms
- `GET /forms` - List forms (admin/agent)
- `POST /forms` - Create form
- `GET /forms/{id}` - Get form details
- `PUT /forms/{id}` - Update form
- `DELETE /forms/{id}` - Delete form

### Responses
- `GET /responses` - List responses (admin/agent)
- `POST /responses` - Submit response
- `GET /responses/{id}` - Get response details
- `GET /responses?view_mode=table|chart|time_series|map|summary` - View responses in different formats

### Public Forms
- `GET /public/forms/{uuid}` - Access public form
- `POST /public/forms/{uuid}/responses` - Submit response to public form

## Error Handling

The API returns structured error responses:
```json
{
  "detail": "Error message",
  "errors": ["Specific error details"]
}
```

Handle common HTTP status codes:
- `200` - Success
- `400` - Bad Request (validation errors)
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `422` - Validation Error
- `500` - Internal Server Error

## Testing CORS

Use the provided `test_frontend_cors.html` file to test CORS from your browser:

1. Start the backend server
2. Open `test_frontend_cors.html` in your browser
3. Click "Test CORS" buttons to verify connectivity

## Development Setup

1. Backend: `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
2. Frontend: Run on `http://localhost:3000`
3. Ensure `credentials: 'include'` in all API calls

## Deletion and Data Management

### Soft Delete Behavior

The SDIGdata API implements **soft deletes** for data safety:
- Deleted records are marked as `deleted = TRUE` with a `deleted_at` timestamp
- Soft-deleted records are **excluded** from all normal API queries
- Soft-deleted records can be **permanently removed** via cleanup endpoints
- This prevents accidental data loss and allows recovery if needed

### Delete Endpoints

#### Soft Delete Individual Records

**Delete a Response** (Admin only)
```
DELETE /api/responses/{response_id}
Authorization: Bearer {admin_token}
```

**Delete a Form** (Admin only)
```
DELETE /api/forms/{form_id}
Authorization: Bearer {admin_token}
```

**Delete a User** (Admin only)
```
DELETE /api/users/{user_id}
Authorization: Bearer {admin_token}
```

**Delete a Notification** (User can delete own)
```
DELETE /api/notifications/{notification_id}
Authorization: Bearer {user_token}
```

**Response:**
```json
{
  "success": true,
  "message": "Response deleted successfully"
}
```

#### Hard Delete Cleanup (Admin Only)

Permanently remove all soft-deleted records:

**Clean up deleted responses:**
```
DELETE /api/responses/cleanup
Authorization: Bearer {admin_token}
```

**Clean up deleted forms:**
```
DELETE /api/forms/cleanup
Authorization: Bearer {admin_token}
```

**Clean up deleted users:**
```
DELETE /api/users/cleanup
Authorization: Bearer {admin_token}
```

**Response:**
```json
{
  "success": true,
  "message": "Cleaned up 5 deleted responses",
  "data": {
    "deleted_count": 5
  }
}
```

### Deletion Rules and Permissions

| Resource | Soft Delete | Hard Delete | Who Can Delete |
|----------|-------------|-------------|----------------|
| Responses | ✅ Admin only | ✅ Admin only | Admin users |
| Forms | ✅ Admin only | ✅ Admin only | Admin users |
| Users | ✅ Admin only | ✅ Admin only | Admin users |
| Notifications | ✅ Own only | N/A | Users (own notifications) |

### Important Notes

1. **Soft deletes are reversible** - records can be restored by setting `deleted = FALSE`
2. **Hard deletes are permanent** - use cleanup endpoints with caution
3. **Deleted records don't appear** in any list or search operations
4. **Cascade behavior** - deleting a form soft-deletes associated responses
5. **Audit trail** - all deletions are logged for compliance

### JavaScript Examples

**Soft Delete a Response:**
```javascript
const deleteResponse = async (responseId) => {
  const response = await fetch(`/api/responses/${responseId}`, {
    method: 'DELETE',
    credentials: 'include',
    headers: {
      'Authorization': `Bearer ${adminToken}`
    }
  });

  if (response.ok) {
    console.log('Response deleted successfully');
  } else {
    console.error('Failed to delete response');
  }
};
```

**Clean up deleted records:**
```javascript
const cleanupDeleted = async (resourceType) => {
  const response = await fetch(`/api/${resourceType}/cleanup`, {
    method: 'DELETE',
    credentials: 'include',
    headers: {
      'Authorization': `Bearer ${adminToken}`
    }
  });

  const result = await response.json();
  console.log(`Cleaned up ${result.data.deleted_count} records`);
};
```

### Error Handling

**Common error responses:**
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Record doesn't exist or already deleted
- `500 Internal Server Error` - Database error

## Production Deployment

- Update CORS origins in `app/main.py` to match your production domain
- Use HTTPS in production
- Configure proper session/cookie settings for production
- **Regular cleanup**: Schedule periodic cleanup of soft-deleted records</content>
<parameter name="filePath">/root/workspace/sdigdata/FRONTEND_INTEGRATION_GUIDE.md