# SDIGdata Backend - API Endpoints Summary

## Base URL
```
Development: http://localhost:8000
Production: https://api.sdigdata.gov.gh
```

## Authentication
All endpoints except `/auth/login` and `/auth/bootstrap-admin` require:
```
Authorization: Bearer <JWT_TOKEN>
```

---

## 🔐 Authentication & Authorization (`/auth`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/auth/login` | ❌ | Login with username/password |
| POST | `/auth/logout` | ✅ | Logout (client-side token removal) |
| GET | `/auth/verify` | ✅ | Verify token validity |
| POST | `/auth/register` | ✅ Admin | Register new user |
| POST | `/auth/bootstrap-admin` | ❌ | Create first admin (one-time only) |
| POST | `/auth/password-reset` | ❌ | Request password reset email (placeholder - email service not configured) |
| POST | `/auth/password-reset/confirm` | ❌ | Confirm password reset with token (placeholder - email service not configured) |
| POST | `/users/me/password` | ✅ | Change password (logged-in users only) |

---

## 🔑 Password Management

### Change Password (Logged-in Users)
**Endpoint:** `POST /users/me/password`  
**Auth:** Required (Bearer token)

**Request:**
```json
{
  "current_password": "CurrentPass123!",
  "new_password": "NewSecurePass456!"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Password changed successfully"
}
```

**Password Requirements:**
- Minimum 8 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one number
- At least one special character (!@#$%^&*)

**Security Features:**
- ✅ Current password verification required
- ✅ Password strength validation
- ✅ Secure password hashing (Argon2)
- ✅ Audit logging
- ✅ Automatic logout of other sessions (token invalidation)

**Example:**
```bash
curl -X POST http://localhost:8000/users/me/password \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "current_password": "OldPass123!",
    "new_password": "NewSecurePass456!"
  }'
```

**Note:** Password reset via email is not currently implemented. Users must be logged in to change their password.

---

## 👥 User Management (`/users`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/users` | ✅ Admin | List all users (paginated) |
| GET | `/users/me` | ✅ | Get current user profile |
| PUT | `/users/me` | ✅ | Update current user profile |
| POST | `/users/me/password` | ✅ | Change password |
| GET | `/users/{id}` | ✅ | Get user by ID (admin or self) |
| PUT | `/users/{id}` | ✅ Admin | Update user |
| DELETE | `/users/{id}` | ✅ Admin | Delete user |

**Query Parameters for `/users`:**
- `role`: Filter by role (admin, agent)
- `page`: Page number (default: 1)
- `limit`: Items per page (default: 50, max: 100)

---

## 📝 Forms Management (`/forms`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/forms` | ✅ | List all forms |
| POST | `/forms` | ✅ Admin | Create new form |
| GET | `/forms/assigned` | ✅ Agent | Get agent's assigned forms |
| GET | `/forms/{id}` | ✅ | Get form by ID |
| PUT | `/forms/{id}` | ✅ Admin | Update form |
| DELETE | `/forms/{id}` | ✅ Admin | Delete form (soft delete) |
| POST | `/forms/{id}/publish` | ✅ Admin | Publish form |
| POST | `/forms/{id}/assign` | ✅ Admin | Assign form to agents (bulk) |
| GET | `/forms/{id}/assignments` | ✅ Admin | Get form assignments |
| GET | `/forms/{id}/agents` | ✅ Admin | Get assigned agents |
| GET | `/forms/{id}/export` | ✅ Admin | Export responses as CSV |

**Query Parameters for `/forms`:**
- `organization_id`: Filter by organization
- `status`: Filter by status (draft, published)

**Form Assignment Request:**
```json
{
  "agent_ids": ["agent-uuid-1", "agent-uuid-2"],
  "due_date": "2025-02-01T00:00:00Z",
  "target_responses": 100
}
```

---

## 📊 Responses Management (`/responses`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/responses` | ✅ | List responses (agents: own only) |
| POST | `/responses` | ✅ | Submit response |
| GET | `/responses/{id}` | ✅ | Get response by ID |
| PUT | `/responses/{id}` | ✅ | Update response |
| DELETE | `/responses/{id}` | ✅ | Delete response |

**Query Parameters for `/responses`:**
- `form_id`: Filter by form
- `page`: Page number
- `limit`: Items per page

---

## 📈 Analytics & Dashboard (`/analytics`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/analytics/dashboard` | ✅ | Dashboard statistics |
| GET | `/analytics/forms/{id}` | ✅ Admin | Form analytics |
| GET | `/analytics/agents/{id}` | ✅ | Agent performance (admin or self) |

**Query Parameters for `/analytics/dashboard`:**
- `period`: Time period (24h, 7d, 30d, 90d) - default: 7d

**Dashboard Response:**
```json
{
  "success": true,
  "data": {
    "stats": {
      "total_forms": 24,
      "total_responses": 1580,
      "total_agents": 45,
      "avg_completion_rate": 82
    },
    "response_trend": [...],
    "top_forms": [...],
    "recent_activity": [...]
  }
}
```

---

## 🔔 Notifications (`/notifications`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/notifications` | ✅ | Get user notifications |
| PUT | `/notifications/{id}/read` | ✅ | Mark notification as read |
| PUT | `/notifications/read-all` | ✅ | Mark all as read |
| DELETE | `/notifications/{id}` | ✅ | Delete notification |

**Query Parameters for `/notifications`:**
- `unread_only`: Boolean (default: false)
- `page`: Page number
- `limit`: Items per page

---

## 🏢 Organizations (`/organizations`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/organizations` | ✅ | List organizations |
| POST | `/organizations` | ✅ Admin | Create organization |
| GET | `/organizations/{id}` | ✅ | Get organization |
| PUT | `/organizations/{id}` | ✅ Admin | Update organization |

---

## 📁 File Management (`/files`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/files/presign` | ✅ | Get presigned upload URL |
| DELETE | `/files` | ✅ | Delete file |

**Presigned URL Request:**
```json
{
  "filename": "logo.png",
  "content_type": "image/png",
  "file_type": "logo",
  "form_id": "form-uuid"
}
```

**Upload Flow:**
1. Request presigned URL from `/files/presign`
2. Upload file directly to returned `upload_url`
3. Store returned `file_url` in your form data

---

## 🤖 ML/AI Features (`/ml`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/ml/training-data` | ✅ Admin | Export ML training data |
| GET | `/ml/quality-stats` | ✅ Admin | Quality statistics |

**Query Parameters for `/ml/training-data`:**
- `format`: Export format (json, jsonl, geojson)
- `min_quality`: Minimum quality score (0-100)

---

## 🏥 Health & Monitoring

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/` | ❌ | Root endpoint |
| GET | `/health` | ❌ | Health check |
| GET | `/docs` | ❌ | Swagger UI documentation |
| GET | `/redoc` | ❌ | ReDoc documentation |
| GET | `/openapi.json` | ❌ | OpenAPI specification |

---

## 📝 Standard Responses

### Success Response
```json
{
  "success": true,
  "data": { ... },
  "message": "Operation successful"
}
```

### Error Response
```json
{
  "detail": "Error message"
}
```

### Validation Error
```json
{
  "detail": [
    {
      "loc": ["body", "field_name"],
      "msg": "Error message",
      "type": "error_type"
    }
  ]
}
```

### Pagination Response
```json
{
  "success": true,
  "data": [...],
  "pagination": {
    "page": 1,
    "limit": 50,
    "total": 150,
    "total_pages": 3
  }
}
```

---

## 🔑 Authentication Example

### 1. Login
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "user-uuid",
    "username": "admin",
    "role": "admin",
    "organization_id": "org-uuid"
  }
}
```

### 2. Use Token in Requests
```bash
curl -X GET http://localhost:8000/users/me \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

---

## 🚀 Quick Start

### 1. Start Services
```bash
docker-compose up -d
```

### 2. Create Admin User
```bash
curl -X POST http://localhost:8000/auth/bootstrap-admin \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "AdminPass@123"}'
```

### 3. Login
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "AdminPass@123"}'
```

### 4. Access Documentation
Open browser to: http://localhost:8000/docs

---

## 📊 Rate Limits

| Endpoint | Limit |
|----------|-------|
| `/auth/login` | 5 attempts per username per 5 minutes |
| `/auth/login` | 10 attempts per IP per 5 minutes |
| All other endpoints | 100 requests per minute |
| File uploads | 10 requests per minute |

---

## 🔒 Security Features

- ✅ JWT token authentication
- ✅ Password strength validation
- ✅ Rate limiting
- ✅ Input sanitization
- ✅ SQL injection protection
- ✅ XSS protection
- ✅ CORS configuration
- ✅ Security audit logging
- ✅ Last login tracking

---

## 📦 Total Endpoints: 50+

- **Authentication**: 7 endpoints
- **User Management**: 7 endpoints
- **Forms Management**: 11 endpoints
- **Responses**: 5 endpoints
- **Analytics**: 3 endpoints
- **Notifications**: 4 endpoints
- **Organizations**: 4 endpoints
- **Files**: 2 endpoints
- **ML/AI**: 2 endpoints
- **Health**: 5 endpoints

---

*For detailed request/response examples, visit: http://localhost:8000/docs*
