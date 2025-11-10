# Prompt for Frontend Claude Instance

## Context

You are building a Next.js frontend for **SDIGdata** - a **government Metropolitan Assembly data collection system**. This is a **production-critical application** where reliability and data integrity are paramount. The government is extremely particular about software quality - there is **zero tolerance for flaky or unreliable software**.

## Your Task

Build a robust, production-ready Next.js frontend that integrates with the FastAPI backend for field data collection by government agents.

## Critical Documents to Review

I'm providing you with the complete backend integration guide. **READ THIS THOROUGHLY** before writing any code:

```
FRONTEND_INTEGRATION_GUIDE.md
```

This document contains:
- Complete API documentation with examples
- Authentication flow (JWT-based)
- All endpoints with request/response formats
- Form schema structure
- File upload process (presigned URLs)
- GPS capture requirements
- Error handling protocols
- Security requirements
- Testing checklist
- Production deployment coordination

## Key Requirements

### 1. User Roles
- **Admin**: Create forms, assign to agents, view all data, export CSV
- **Agent**: View assigned forms, submit responses, upload files

### 2. Core Features
- Dynamic form builder (admin)
- Form rendering from JSON schema
- GPS coordinate capture
- File uploads (photos, signatures)
- Offline support (optional but recommended)
- CSV export (admin)
- Responsive design (mobile-first)

### 3. Critical Technical Requirements

**Authentication**:
- JWT tokens with 24-hour expiration
- Store in httpOnly cookies or localStorage
- Auto-redirect to login on 401
- Clear session on logout

**File Uploads** (CRITICAL):
- Use presigned URLs - **DO NOT upload through API**
- Process: Request presigned URL → Upload directly to storage → Submit file URL in response
- See detailed flow in integration guide

**GPS Capture**:
- Request location permission
- Capture: latitude, longitude, accuracy
- Requires HTTPS in production
- Provide manual input fallback

**Error Handling**:
- 401: Redirect to login
- 403: Show permission denied
- 422: Display validation errors
- 429: Rate limit message
- 500: User-friendly error

### 4. Form Schema

Forms are defined in JSON with branding and fields:

```json
{
  "branding": {
    "logo_url": "...",
    "primary_color": "#0066CC",
    "header_text": "...",
    "footer_text": "..."
  },
  "fields": [
    { "id": "name", "type": "text", "label": "Full Name", "required": true },
    { "id": "location", "type": "gps", "label": "Location", "required": true },
    { "id": "photo", "type": "file", "label": "Photo", "accept": "image/*" }
  ]
}
```

**Supported Types**: text, textarea, email, number, date, select, radio, checkbox, gps, file

### 5. API Connection

**Local Development**:
```
API: http://localhost:8000
Docs: http://localhost:8000/docs
```

**Environment Variables**:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_ENVIRONMENT=development
```

### 6. Security (NON-NEGOTIABLE)

- ✅ HTTPS only in production
- ✅ Validate all inputs
- ✅ Sanitize user content
- ✅ Never expose tokens in URLs
- ✅ Clear tokens on logout
- ✅ Request geolocation permission
- ✅ Implement CSRF protection

### 7. Testing Requirements

Before considering the project complete, you MUST:
- [ ] Test all authentication flows
- [ ] Test form creation and publishing
- [ ] Test form submission with all field types
- [ ] Test file upload end-to-end
- [ ] Test GPS capture on mobile
- [ ] Test error scenarios (network, auth, validation)
- [ ] Test with slow network (3G simulation)
- [ ] Test responsive design on mobile/tablet
- [ ] Test CSV export
- [ ] Verify role-based access control

### 8. Code Quality Standards

**This is government software - quality is critical**:

- Use TypeScript for all API interactions
- Create reusable API client wrapper
- Implement proper error boundaries
- Add loading states for all async operations
- Write unit tests for critical components
- Use proper form validation (client AND server)
- Handle edge cases (no network, expired token, etc.)
- Add meaningful error messages
- Implement retry logic for failed requests
- Log errors to console (or monitoring service)

### 9. Performance Requirements

- Forms must render in < 1 second
- Support forms with 50+ fields
- Optimize images before upload (compress to < 2MB)
- Cache forms locally to reduce API calls
- Implement pagination for large datasets
- Show upload progress for files
- Lazy load form fields if needed

### 10. User Experience Requirements

**Remember: Field agents use this in rural areas with poor connectivity**

- Clear loading indicators
- Offline indicator when no network
- Save draft responses locally
- Sync when connection restored
- Show clear validation errors
- Provide helpful error messages
- Mobile-friendly (agents use phones)
- Support landscape/portrait
- Large touch targets (mobile)
- Clear call-to-action buttons

## Development Approach

1. **Start by reading FRONTEND_INTEGRATION_GUIDE.md thoroughly**
2. Set up Next.js project with TypeScript
3. Create API client wrapper with authentication
4. Build authentication pages (login/register)
5. Build admin dashboard (forms, users, analytics)
6. Build agent interface (view assigned forms, submit)
7. Implement dynamic form renderer
8. Implement file upload with presigned URLs
9. Add GPS capture functionality
10. Test extensively with the backend
11. Add error handling and loading states
12. Optimize for mobile
13. Add offline support (if time permits)
14. Final testing with all scenarios

## Common Pitfalls to Avoid

1. ❌ Don't upload files through the API - use presigned URLs
2. ❌ Don't store form data in component state for large forms - use form library
3. ❌ Don't forget to handle token expiration
4. ❌ Don't trust frontend validation alone - backend validates too
5. ❌ Don't ignore loading states - users need feedback
6. ❌ Don't hardcode API URLs - use environment variables
7. ❌ Don't assume good network - test on slow connections
8. ❌ Don't forget mobile - agents primarily use phones
9. ❌ Don't skip error handling - show user-friendly messages
10. ❌ Don't deploy without thorough testing - government has zero tolerance

## Technology Stack Recommendations

**Core**:
- Next.js 14+ (App Router)
- TypeScript
- Tailwind CSS

**Forms**:
- React Hook Form (recommended)
- Zod for validation

**State Management**:
- React Context or Zustand

**API Calls**:
- Native fetch with custom wrapper
- Or Axios with interceptors

**File Handling**:
- react-dropzone
- Image compression library

**Maps** (for GPS):
- react-leaflet or Mapbox

**UI Components**:
- shadcn/ui (recommended)
- Or Headless UI

## Questions to Ask Before Starting

If anything is unclear:
1. Check FRONTEND_INTEGRATION_GUIDE.md first
2. Test the endpoint in the API docs (http://localhost:8000/docs)
3. Look at the Postman collection if available
4. Ask specific questions with endpoint details

## Success Criteria

The frontend is complete when:
- ✅ All authentication flows work
- ✅ Admins can create, publish, and assign forms
- ✅ Agents can view assigned forms and submit responses
- ✅ File uploads work end-to-end
- ✅ GPS coordinates are captured correctly
- ✅ CSV export works
- ✅ All error scenarios are handled gracefully
- ✅ Mobile experience is excellent
- ✅ Code is clean, typed, and tested
- ✅ Performance meets requirements
- ✅ No console errors in production
- ✅ Government team would be proud to use it

## Remember

This system collects critical government data. Lives and livelihoods may depend on accurate data collection. Build with reliability, integrity, and user experience in mind.

**Zero tolerance for flaky software. Quality is non-negotiable.**

---

Now, read `FRONTEND_INTEGRATION_GUIDE.md` completely and begin building the frontend with excellence.

Good luck! 🚀
