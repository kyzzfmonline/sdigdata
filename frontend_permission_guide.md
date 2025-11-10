# Frontend Permission Enforcement Guide

## Overview

The SDIGdata frontend should implement a comprehensive permission enforcement system that works alongside the backend RBAC (Role-Based Access Control) system. This guide outlines the best practices for implementing frontend permissions.

## Core Principles

### 1. **Backend-First Security**
- **Backend enforces ALL permissions** - Frontend is for UX only
- **Never trust client-side permission checks** for security decisions
- **Always validate permissions on the server** for any sensitive operations

### 2. **Progressive Enhancement**
- **Hide/disable UI elements** based on permissions for better UX
- **Show appropriate interfaces** based on user capabilities
- **Graceful degradation** when permissions change

### 3. **Performance Considerations**
- **Cache permissions** in frontend state to avoid repeated API calls
- **Use efficient data structures** (Sets for O(1) lookups)
- **Lazy load permission-dependent features**

## Implementation Strategy

### 1. Permission Context Management

```javascript
// PermissionContext.jsx
import { createContext, useContext, useEffect, useState } from 'react';

const PermissionContext = createContext();

export const usePermissions = () => {
  const context = useContext(PermissionContext);
  if (!context) {
    throw new Error('usePermissions must be used within PermissionProvider');
  }
  return context;
};

export const PermissionProvider = ({ children }) => {
  const [permissions, setPermissions] = useState(new Set());
  const [roles, setRoles] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchUserPermissions = async () => {
    try {
      const token = localStorage.getItem('access_token');
      if (!token) return;

      const [permsResponse, rolesResponse] = await Promise.all([
        fetch('/users/permissions', {
          headers: { Authorization: `Bearer ${token}` }
        }),
        fetch('/users/roles', {
          headers: { Authorization: `Bearer ${token}` }
        })
      ]);

      if (permsResponse.ok && rolesResponse.ok) {
        const permsData = await permsResponse.json();
        const rolesData = await rolesResponse.json();

        // Store as Set for O(1) permission checks
        setPermissions(new Set(permsData.data.map(p => p.name)));
        setRoles(rolesData.data);
      }
    } catch (error) {
      console.error('Failed to fetch permissions:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUserPermissions();
  }, []);

  // Permission checking functions
  const hasPermission = (permission) => permissions.has(permission);
  const hasAnyPermission = (permissionList) => permissionList.some(p => permissions.has(p));
  const hasAllPermissions = (permissionList) => permissionList.every(p => permissions.has(p));
  const hasRole = (roleName) => roles.some(r => r.name === roleName);

  const value = {
    permissions: Array.from(permissions),
    roles,
    loading,
    hasPermission,
    hasAnyPermission,
    hasAllPermissions,
    hasRole,
    refreshPermissions: fetchUserPermissions
  };

  return (
    <PermissionContext.Provider value={value}>
      {children}
    </PermissionContext.Provider>
  );
};
```

### 2. Permission-Based Components

```javascript
// PermissionGuard.jsx
const PermissionGuard = ({ permission, fallback = null, children }) => {
  const { hasPermission, loading } = usePermissions();

  if (loading) return <div>Loading permissions...</div>;
  if (!hasPermission(permission)) return fallback;

  return children;
};

const RoleGuard = ({ role, fallback = null, children }) => {
  const { hasRole, loading } = usePermissions();

  if (loading) return <div>Loading permissions...</div>;
  if (!hasRole(role)) return fallback;

  return children;
};

// Conditional rendering hook
const useConditionalRender = () => {
  const { hasPermission, hasAnyPermission, hasAllPermissions, hasRole } = usePermissions();

  return {
    // Show element only if user has permission
    ifPerm: (permission) => hasPermission(permission),
    ifAnyPerm: (permissions) => hasAnyPermission(permissions),
    ifAllPerms: (permissions) => hasAllPermissions(permissions),
    ifRole: (role) => hasRole(role),

    // Hide element if user has permission (inverse)
    unlessPerm: (permission) => !hasPermission(permission),
    unlessRole: (role) => !hasRole(role),
  };
};
```

### 3. Route Protection

```javascript
// ProtectedRoute.jsx
import { Navigate } from 'react-router-dom';
import { usePermissions } from './PermissionContext';

const ProtectedRoute = ({ permission, children }) => {
  const { hasPermission, loading } = usePermissions();

  if (loading) {
    return <div>Loading...</div>;
  }

  if (!hasPermission(permission)) {
    return <Navigate to="/unauthorized" replace />;
  }

  return children;
};

// App.jsx - Route Configuration
const App = () => {
  return (
    <PermissionProvider>
      <Routes>
        <Route path="/dashboard" element={<Dashboard />} />

        {/* User Management - requires users.read */}
        <Route
          path="/users"
          element={
            <ProtectedRoute permission="users.read">
              <UserManagement />
            </ProtectedRoute>
          }
        />

        {/* Form Creation - requires forms.create */}
        <Route
          path="/forms/create"
          element={
            <ProtectedRoute permission="forms.create">
              <FormBuilder />
            </ProtectedRoute>
          }
        />

        {/* Admin Panel - requires system.admin */}
        <Route
          path="/admin"
          element={
            <ProtectedRoute permission="system.admin">
              <AdminPanel />
            </ProtectedRoute>
          }
        />

        {/* Analytics - requires analytics.view */}
        <Route
          path="/analytics"
          element={
            <ProtectedRoute permission="analytics.view">
              <AnalyticsDashboard />
            </ProtectedRoute>
          }
        />
      </Routes>
    </PermissionProvider>
  );
};
```

### 4. Component-Level Permission Checks

```javascript
// UserManagement.jsx
const UserManagement = () => {
  const { ifPerm } = useConditionalRender();

  return (
    <div>
      <h1>User Management</h1>

      {/* Create button - only for users with users.create permission */}
      {ifPerm('users.create') && (
        <button className="btn-primary">
          <UserPlusIcon /> Create New User
        </button>
      )}

      {/* Bulk actions - only for users with users.admin permission */}
      {ifPerm('users.admin') && (
        <div className="bulk-actions">
          <button>Bulk Delete</button>
          <button>Bulk Assign Roles</button>
        </div>
      )}

      {/* User table with conditional action columns */}
      <UserTable />

      {/* Admin panel - only for admins */}
      <RoleGuard role="admin" fallback={<div>Admin access required</div>}>
        <AdminPanel />
      </RoleGuard>
    </div>
  );
};

// UserTable.jsx
const UserTable = () => {
  const { hasPermission } = usePermissions();

  return (
    <table>
      <thead>
        <tr>
          <th>Name</th>
          <th>Email</th>
          <th>Role</th>
          {hasPermission('users.update') && <th>Actions</th>}
        </tr>
      </thead>
      <tbody>
        {users.map(user => (
          <tr key={user.id}>
            <td>{user.name}</td>
            <td>{user.email}</td>
            <td>{user.role}</td>
            {hasPermission('users.update') && (
              <td>
                <button>Edit</button>
                {hasPermission('users.delete') && (
                  <button className="danger">Delete</button>
                )}
              </td>
            )}
          </tr>
        ))}
      </tbody>
    </table>
  );
};
```

### 5. Form-Level Permissions

```javascript
// UserForm.jsx
const UserForm = ({ user, onSave }) => {
  const { hasPermission } = usePermissions();
  const [formData, setFormData] = useState(user || {});

  const canEditRole = hasPermission('users.admin');
  const canEditProfile = hasPermission('users.update') || user?.id === currentUserId;
  const canDelete = hasPermission('users.delete');

  const handleSubmit = async (e) => {
    e.preventDefault();

    // Backend will validate permissions, but we can provide early feedback
    if (!canEditProfile) {
      alert('You do not have permission to edit this user');
      return;
    }

    try {
      await onSave(formData);
    } catch (error) {
      // Handle API errors (including permission errors)
      console.error('Save failed:', error);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <div>
        <label>Name:</label>
        <input
          type="text"
          value={formData.name || ''}
          onChange={(e) => setFormData({...formData, name: e.target.value})}
          disabled={!canEditProfile}
        />
      </div>

      <div>
        <label>Email:</label>
        <input
          type="email"
          value={formData.email || ''}
          onChange={(e) => setFormData({...formData, email: e.target.value})}
          disabled={!canEditProfile}
        />
      </div>

      {/* Role selection - only for admins */}
      {canEditRole && (
        <div>
          <label>Role:</label>
          <select
            value={formData.role || ''}
            onChange={(e) => setFormData({...formData, role: e.target.value})}
          >
            <option value="viewer">Viewer</option>
            <option value="agent">Agent</option>
            <option value="supervisor">Supervisor</option>
            {hasPermission('users.admin') && (
              <option value="admin">Admin</option>
            )}
          </select>
        </div>
      )}

      <div className="form-actions">
        <button type="submit" disabled={!canEditProfile}>
          Save Changes
        </button>

        {canDelete && (
          <button
            type="button"
            className="danger"
            onClick={() => {
              if (confirm('Are you sure you want to delete this user?')) {
                // Handle delete
              }
            }}
          >
            Delete User
          </button>
        )}
      </div>
    </form>
  );
};
```

## Permission Mapping

### SDIGdata Permission Structure

| Resource | Actions | Description |
|----------|---------|-------------|
| `users` | `admin`, `create`, `read`, `update`, `delete` | User management |
| `forms` | `admin`, `assign`, `create`, `read`, `update`, `delete`, `publish` | Form management |
| `responses` | `admin`, `create`, `read`, `update`, `delete`, `export` | Response management |
| `files` | `admin`, `upload`, `download`, `delete` | File management |
| `organizations` | `admin`, `create`, `read`, `update`, `delete` | Organization management |
| `system` | `admin`, `audit`, `cleanup`, `settings` | System administration |
| `analytics` | `admin`, `export`, `view` | Analytics and reporting |

### Common Permission Patterns

```javascript
// Check multiple permissions (OR condition)
const canManageUsers = hasAnyPermission(['users.admin', 'users.update']);

// Check all permissions required (AND condition)
const canPublishForm = hasAllPermissions(['forms.update', 'forms.publish']);

// Check role-based access
const isAdmin = hasRole('admin');
const isSuperAdmin = hasRole('super_admin');

// Complex conditions
const canEditForm = hasPermission('forms.update') ||
                   (hasPermission('forms.read') && form.createdBy === currentUserId);
```

## Best Practices

### 1. **Security First**
- **Never rely on frontend permissions** for security decisions
- **Always validate on backend** for any data-changing operations
- **Use HTTPS** for all API communications
- **Store tokens securely** (HttpOnly cookies preferred over localStorage)

### 2. **User Experience**
- **Hide unavailable features** rather than showing disabled buttons
- **Provide clear feedback** when actions are not permitted
- **Use loading states** during permission checks
- **Handle permission changes gracefully** (e.g., after role updates)

### 3. **Performance**
- **Cache permissions** in memory to avoid repeated API calls
- **Refresh permissions** after login/logout and role changes
- **Use optimistic updates** where appropriate
- **Lazy load permission-dependent components**

### 4. **Error Handling**
- **Handle API errors gracefully** (network issues, token expiry)
- **Provide fallback UI** when permissions can't be loaded
- **Log permission violations** for security monitoring
- **Clear sensitive data** on logout

### 5. **Testing**
- **Test permission logic** in isolation
- **Test UI behavior** with different permission sets
- **Mock permission context** in component tests
- **Test route protection** with unauthorized users

## Implementation Checklist

- [ ] Set up PermissionContext and PermissionProvider
- [ ] Implement permission fetching on login
- [ ] Create PermissionGuard and RoleGuard components
- [ ] Add route protection for sensitive pages
- [ ] Implement conditional rendering in components
- [ ] Add permission checks to forms and actions
- [ ] Handle permission refresh after role changes
- [ ] Add loading states and error handling
- [ ] Test with different user roles
- [ ] Document permission requirements for each feature

## Security Considerations

1. **Token Security**: Use HttpOnly cookies for JWT storage
2. **Permission Refresh**: Refresh permissions on token refresh
3. **Logout Handling**: Clear permissions and sensitive data on logout
4. **Error Boundaries**: Handle permission loading failures gracefully
5. **Audit Logging**: Log permission checks for security monitoring
6. **Rate Limiting**: Implement rate limiting for permission API calls

This approach ensures that your frontend provides an excellent user experience while maintaining security through backend enforcement.</content>
<parameter name="filePath">frontend_permission_guide.md