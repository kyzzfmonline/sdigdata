# CORS Troubleshooting Guide

## Backend CORS Configuration ✅

The SDIGdata backend has proper CORS configuration:

### Development Mode
- **Allow Origins**: `*` (all origins)
- **Allow Credentials**: `true`
- **Allow Methods**: `GET, POST, PUT, DELETE, OPTIONS, PATCH`
- **Allow Headers**: `*` (all headers)
- **Expose Headers**: `*` (all headers)

### Production Mode
- **Allow Origins**: Configured list from `CORS_ORIGINS` environment variable
- **Allow Credentials**: `true`
- **Allow Methods**: `GET, POST, PUT, DELETE, OPTIONS, PATCH`
- **Allow Headers**: `Authorization, Content-Type, Accept, Origin, User-Agent`

## Common Frontend CORS Issues

### 1. Missing `credentials: true`

**Problem**: Browser blocks requests due to missing credentials flag.

**Solution**: Always include `credentials: 'include'` in fetch requests:

```javascript
// ❌ Wrong
fetch('/api/endpoint', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(data)
})

// ✅ Correct
fetch('/api/endpoint', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  credentials: 'include',  // Required for CORS with credentials
  body: JSON.stringify(data)
})
```

### 2. Wrong Origin/Port

**Problem**: Frontend running on different port than expected.

**Common Issues**:
- Frontend on `http://localhost:3001` but CORS test uses `http://localhost:3000`
- HTTPS frontend calling HTTP backend
- Different protocols (http vs https)

**Solution**: 
1. Check your frontend's running port
2. Update CORS test to match your frontend's origin
3. Or configure backend to allow your specific origin

### 3. Preflight Request Failures

**Problem**: OPTIONS preflight requests are blocked.

**Symptoms**:
- POST/PUT/DELETE requests fail with CORS error
- GET requests with custom headers fail

**Debug Steps**:
1. Check browser Network tab for OPTIONS requests
2. Verify OPTIONS request gets 200 response
3. Check CORS headers in OPTIONS response

### 4. Authorization Header Issues

**Problem**: Authorization header not allowed by CORS.

**Solution**: The backend allows `Authorization` header, but ensure your request includes it correctly:

```javascript
const token = localStorage.getItem('access_token');
fetch('/api/protected-endpoint', {
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  credentials: 'include'
})
```

## Frontend Code Examples

### React with Fetch API

```javascript
// api.js
const API_BASE = 'http://localhost:8000';

export const apiRequest = async (endpoint, options = {}) => {
  const url = `${API_BASE}${endpoint}`;
  const token = localStorage.getItem('access_token');
  
  const defaultOptions = {
    headers: {
      'Content-Type': 'application/json',
      ...(token && { 'Authorization': `Bearer ${token}` })
    },
    credentials: 'include'  // Important for CORS
  };
  
  const response = await fetch(url, { ...defaultOptions, ...options });
  
  if (!response.ok) {
    throw new Error(`API Error: ${response.status}`);
  }
  
  return response.json();
};

// Usage
import { apiRequest } from './api';

const login = async (username, password) => {
  const response = await apiRequest('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password })
  });
  
  localStorage.setItem('access_token', response.data.access_token);
  return response;
};

const getResponses = async (formId, viewMode = 'table') => {
  return apiRequest(`/responses?form_id=${formId}&view=${viewMode}`);
};
```

### React with Axios

```javascript
// api.js
import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000',
  withCredentials: true,  // Important for CORS
  headers: {
    'Content-Type': 'application/json'
  }
});

// Request interceptor to add auth token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Handle unauthorized - redirect to login
      localStorage.removeItem('access_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default api;

// Usage
import api from './api';

const login = async (username, password) => {
  const response = await api.post('/auth/login', { username, password });
  localStorage.setItem('access_token', response.data.data.access_token);
  return response.data;
};

const getResponses = async (formId, viewMode = 'table') => {
  const response = await api.get('/responses', {
    params: { form_id: formId, view: viewMode }
  });
  return response.data;
};
```

### Vue.js with Fetch

```javascript
// api.js
const API_BASE = 'http://localhost:8000';

export const api = {
  async request(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    const token = localStorage.getItem('access_token');
    
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...(token && { 'Authorization': `Bearer ${token}` })
      },
      credentials: 'include',  // Important for CORS
      ...options
    });
    
    if (!response.ok) {
      throw new Error(`API Error: ${response.status}`);
    }
    
    return response.json();
  },
  
  get(endpoint, params = {}) {
    const queryString = new URLSearchParams(params).toString();
    const url = queryString ? `${endpoint}?${queryString}` : endpoint;
    return this.request(url);
  },
  
  post(endpoint, data) {
    return this.request(endpoint, {
      method: 'POST',
      body: JSON.stringify(data)
    });
  }
};

// Usage in Vue component
export default {
  data() {
    return {
      responses: [],
      loading: false,
      error: null
    };
  },
  methods: {
    async loadResponses(formId) {
      this.loading = true;
      this.error = null;
      
      try {
        const result = await api.get('/responses', { 
          form_id: formId, 
          view: 'table' 
        });
        this.responses = result.data.data;
      } catch (error) {
        this.error = error.message;
        console.error('Failed to load responses:', error);
      } finally {
        this.loading = false;
      }
    }
  }
};
```

## Browser-Specific Issues

### Chrome
- **Issue**: Strict CORS enforcement
- **Solution**: Use `--disable-web-security` flag for development (not recommended for production)
- **Better Solution**: Configure proper CORS headers

### Firefox
- **Issue**: Different CORS handling for localhost
- **Solution**: Ensure backend allows the specific origin

### Safari
- **Issue**: Strict preflight requirements
- **Solution**: Ensure all headers are properly allowed

## Testing CORS

### 1. Browser Dev Tools
1. Open Network tab
2. Make the failing request
3. Look for OPTIONS preflight requests
4. Check response headers for CORS headers

### 2. Command Line Testing

```bash
# Test preflight
curl -X OPTIONS -H "Origin: http://localhost:3000" \
     -H "Access-Control-Request-Method: POST" \
     -H "Access-Control-Request-Headers: Authorization,Content-Type" \
     -v http://localhost:8000/auth/login

# Test actual request
curl -X POST -H "Content-Type: application/json" \
     -H "Origin: http://localhost:3000" \
     -d '{"username":"admin","password":"admin123"}' \
     -v http://localhost:8000/auth/login
```

### 3. Online CORS Testers
- Use tools like `test-cors.org` or `cors-test.codehappy.net`
- Input your API endpoints and test from different origins

## Environment Variables

Make sure your `.env` file has correct CORS settings:

```env
# Development
ENVIRONMENT=development
CORS_ORIGINS=http://localhost:3000,http://localhost:3001,http://127.0.0.1:3000

# Production
ENVIRONMENT=production
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

## Quick Fixes

1. **Add `credentials: 'include'` to all fetch requests**
2. **Clear browser cache and cookies**
3. **Restart both frontend and backend servers**
4. **Check that ports match between frontend and backend**
5. **Verify no VPN/proxy is interfering**
6. **Test with a simple GET request first**

## Still Having Issues?

If CORS errors persist:

1. **Check server logs** for any CORS-related errors
2. **Verify environment variables** are loaded correctly
3. **Test with different browsers**
4. **Try disabling browser extensions**
5. **Check if firewall/antivirus is blocking requests**
6. **Verify backend is actually running on the expected port**

The backend CORS configuration is working correctly based on automated tests. Most CORS issues are frontend configuration problems.
