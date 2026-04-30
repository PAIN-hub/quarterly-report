# MDA Report Portal API Documentation

Complete reference for all API endpoints, request/response formats, and error handling.

## Base URL
```
http://localhost:8000/api/v1
```

## Authentication

All endpoints (except login) require JWT token in Authorization header:
```
Authorization: Bearer <access_token>
```

---

## Authentication Endpoints

### Login
**POST** `/auth/login/`

Request:
```json
{
  "access_id": "KTS-MDA-001",
  "password": "password123"
}
```

Response (200):
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "access_id": "KTS-MDA-001",
    "name": "John Doe",
    "email": "john@example.com",
    "role": "MDA_USER",
    "mda_name": "Katsina State MDA",
    "is_active": true,
    "date_joined": "2024-01-15T10:30:00Z",
    "last_login": "2024-04-29T16:45:00Z"
  }
}
```

Errors:
```json
{
  "detail": "Invalid credentials"
}
```

### Refresh Token
**POST** `/auth/token/refresh/`

Request:
```json
{
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

Response (200):
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

---

## User Management

### List Users
**GET** `/users/`

Query Parameters:
- `search`: Search by access_id, name, or mda_name
- `ordering`: Order by date_joined or last_login
- `page`: Pagination (default page size: 50)

Response (200):
```json
{
  "count": 25,
  "next": "http://localhost:8000/api/v1/users/?page=2",
  "previous": null,
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "access_id": "KTS-MDA-001",
      "name": "John Doe",
      "email": "john@example.com",
      "role": "MDA_USER",
      "mda_name": "Katsina State MDA",
      "is_active": true,
      "date_joined": "2024-01-15T10:30:00Z",
      "last_login": "2024-04-29T16:45:00Z"
    }
  ]
}
```

### Get Current User
**GET** `/users/me/`

Response (200): Same as individual user object above

### Get User Details
**GET** `/users/{id}/`

Response (200): User object

### Create User
**POST** `/users/` (SYSTEM_ADMIN only)

Request:
```json
{
  "access_id": "KTS-MDA-002",
  "name": "Jane Smith",
  "email": "jane@example.com",
  "password": "SecurePassword123!",
  "password_confirm": "SecurePassword123!",
  "role": "MDA_ADMIN",
  "mda_name": "Katsina State MDA"
}
```

Response (201): User object

Validation:
- access_id: Must be unique, format: `STATE-TYPE-NUMBER`
- password: Minimum 8 characters, must match password_confirm
- role: One of MDA_USER, MDA_ADMIN, REGIONAL_OFFICER, SYSTEM_ADMIN

### Update User
**PATCH** `/users/{id}/`

Request:
```json
{
  "name": "Jane Smith Updated",
  "email": "jane.updated@example.com"
}
```

Response (200): Updated user object

### Change Password
**PATCH** `/users/{id}/change_password/`

Request:
```json
{
  "old_password": "CurrentPassword123!",
  "new_password": "NewPassword456!"
}
```

Response (200):
```json
{
  "message": "Password changed successfully"
}
```

---

## Report Management

### List Reports
**GET** `/reports/`

Query Parameters:
- `search`: Search by mda_name or user name
- `ordering`: -last_modified (default), created_at
- `page`: Pagination

Response (200):
```json
{
  "count": 15,
  "results": [
    {
      "id": "660f9511-f30c-42e5-b827-557766551111",
      "user": "550e8400-e29b-41d4-a716-446655440000",
      "user_name": "John Doe",
      "mda_name": "Katsina State MDA",
      "data": {
        "mdaName": "Katsina State MDA",
        "capexPerformance": 85,
        "stateDevImpact": "Improved service delivery"
      },
      "version": 2,
      "created_at": "2024-04-15T10:30:00Z",
      "updated_at": "2024-04-29T14:20:00Z",
      "last_modified": "2024-04-29T14:20:00Z",
      "last_modified_by": "550e8400-e29b-41d4-a716-446655440000",
      "last_modified_by_name": "John Doe",
      "synced_at": "2024-04-29T14:20:00Z",
      "is_deleted": false,
      "performance_status": "GOOD"
    }
  ]
}
```

### Create Report
**POST** `/reports/`

Request:
```json
{
  "mda_name": "Katsina State MDA",
  "data": {
    "mdaName": "Katsina State MDA",
    "missionStatement": "To deliver quality services",
    "capexPerformance": 85,
    "stateDevImpact": "Improved infrastructure"
  }
}
```

Response (201): Report object with version=1

### Get Report Details
**GET** `/reports/{id}/`

Response (200): Report object

### Update Report
**PATCH** `/reports/{id}/`

Request:
```json
{
  "data": {
    "mdaName": "Katsina State MDA",
    "capexPerformance": 90
  },
  "version": 2
}
```

Response (200): Updated report with incremented version

### Version Conflict Response (409)
When server version is newer than local version:
```json
{
  "error": "Version conflict detected",
  "conflict_id": "770g0622-g41d-53f6-c828-668877662222",
  "server_version": 3,
  "server_data": { "capexPerformance": 92 },
  "options": ["OVERWRITE", "KEEP_SERVER"]
}
```

### Delete Report
**DELETE** `/reports/{id}/`

Response (204): No content (soft delete)

### Get Report Versions
**GET** `/reports/{id}/versions/`

Response (200):
```json
[
  {
    "id": "880h1733-h52e-64g7-d939-779988773333",
    "version_number": 1,
    "data": { "capexPerformance": 80 },
    "modified_by": "550e8400-e29b-41d4-a716-446655440000",
    "modified_by_name": "John Doe",
    "created_at": "2024-04-15T10:30:00Z",
    "change_description": "Initial submission"
  },
  {
    "id": "990i2844-i63f-75h8-e040-880099884444",
    "version_number": 2,
    "data": { "capexPerformance": 85 },
    "modified_by": "550e8400-e29b-41d4-a716-446655440000",
    "modified_by_name": "John Doe",
    "created_at": "2024-04-29T14:20:00Z",
    "change_description": "Updated"
  }
]
```

### Revert to Version
**POST** `/reports/{id}/revert/`

Request:
```json
{
  "version_number": 1
}
```

Response (200): Report object with reverted data and new version number

---

## Sync & Conflict Resolution

### Bulk Sync
**POST** `/sync/bulk_sync/`

Sync multiple offline changes in one request.

Request:
```json
{
  "actions": [
    {
      "action_type": "CREATE_REPORT",
      "data": {
        "mdaName": "New MDA",
        "capexPerformance": 75
      }
    },
    {
      "action_type": "UPDATE_REPORT",
      "report_id": "660f9511-f30c-42e5-b827-557766551111",
      "data": { "capexPerformance": 88 },
      "version": 2
    }
  ],
  "device_id": "device-abc-123",
  "last_sync": "2024-04-29T10:00:00Z"
}
```

Response (200):
```json
{
  "results": [
    {
      "action": "CREATE_REPORT",
      "status": "success",
      "report_id": "aaa1111-bb2222-cc3333",
      "version": 1
    },
    {
      "action": "UPDATE_REPORT",
      "status": "success",
      "report_id": "660f9511-f30c-42e5-b827-557766551111",
      "version": 3
    }
  ],
  "conflicts": [],
  "synced_at": "2024-04-29T16:45:00Z"
}
```

With conflicts:
```json
{
  "results": [...],
  "conflicts": [
    {
      "conflict_id": "770g0622-g41d-53f6-c828-668877662222",
      "report_id": "660f9511-f30c-42e5-b827-557766551111",
      "local_version": 2,
      "server_version": 4
    }
  ]
}
```

### Get Changes Since Timestamp
**GET** `/sync/changes_since/?timestamp=2024-04-29T10:00:00Z`

Response (200):
```json
{
  "updated_reports": [
    { "id": "...", "mda_name": "...", "version": 3 }
  ],
  "deleted_report_ids": ["id1", "id2"],
  "server_timestamp": "2024-04-29T16:45:00Z"
}
```

---

## Audit & Backup

### List Audit Logs
**GET** `/audit-logs/`

Query Parameters:
- `search`: Search by user name, action, resource_type
- `ordering`: -created_at (default)

Response (200):
```json
{
  "count": 100,
  "results": [
    {
      "id": "bbb2222-cc3333-dd4444",
      "user": "550e8400-e29b-41d4-a716-446655440000",
      "user_name": "John Doe",
      "action": "UPDATE",
      "resource_type": "report",
      "resource_id": "660f9511-f30c-42e5-b827-557766551111",
      "changes": {
        "capexPerformance": {
          "old": 80,
          "new": 85
        }
      },
      "description": "Updated report",
      "ip_address": "192.168.1.1",
      "user_agent": "Mozilla/5.0...",
      "created_at": "2024-04-29T14:20:00Z"
    }
  ]
}
```

### Create Manual Backup
**POST** `/backups/` (SYSTEM_ADMIN only)

Request:
```json
{
  "description": "Before system upgrade"
}
```

Response (201):
```json
{
  "id": "ccc3333-dd4444-ee5555",
  "backup_name": "backup_20240429_144500",
  "description": "Before system upgrade",
  "status": "COMPLETED",
  "backup_type": "MANUAL",
  "created_by": "550e8400-e29b-41d4-a716-446655440000",
  "created_by_name": "Admin",
  "created_at": "2024-04-29T14:45:00Z",
  "size_bytes": 524288,
  "restored_at": null,
  "restored_by": null
}
```

### List Backups
**GET** `/backups/` (SYSTEM_ADMIN only)

Response (200): Array of backup objects

### Verify Backup Integrity
**GET** `/backups/{id}/verify/` (SYSTEM_ADMIN only)

Response (200):
```json
{
  "backup_id": "ccc3333-dd4444-ee5555",
  "integrity_valid": true,
  "data_hash": "a1b2c3d4e5f6..."
}
```

### Restore from Backup
**POST** `/backups/{id}/restore/` (SYSTEM_ADMIN only)

Response (200):
```json
{
  "message": "Backup restored successfully"
}
```

---

## Data Export

### Export as JSON
**GET** `/export/export_json/?include_audit=true&include_deleted=false`

Query Parameters:
- `include_audit`: Include audit logs (true/false)
- `include_deleted`: Include soft-deleted records (true/false)

Response (200): JSON file download

File content:
```json
{
  "export_date": "2024-04-29T16:45:00Z",
  "exported_by": "KTS-MDA-001",
  "users": [...],
  "reports": [...],
  "audit_logs": [...]
}
```

---

## Health & Status

### Health Check
**GET** `/health/`

Response (200):
```json
{
  "status": "healthy",
  "timestamp": "2024-04-29T16:45:00Z"
}
```

### API Info
**GET** `/info/`

Response (200):
```json
{
  "name": "MDA Report Portal API",
  "version": "1.0.0",
  "documentation": "/api/v1/docs/"
}
```

---

## Error Handling

### Error Response Format
All errors follow this format:

```json
{
  "error": "Error message",
  "detail": "Detailed explanation"
}
```

### Common Status Codes
- **200**: Successful GET/PATCH/PUT
- **201**: Successful POST (created)
- **204**: Successful DELETE (no content)
- **400**: Bad request (validation error)
- **401**: Unauthorized (missing/invalid token)
- **403**: Forbidden (insufficient permissions)
- **404**: Not found
- **409**: Conflict (version mismatch)
- **500**: Server error

### Example Errors

**401 Unauthorized:**
```json
{
  "detail": "Authentication credentials were not provided."
}
```

**403 Forbidden:**
```json
{
  "error": "Only system administrators can create backups"
}
```

**409 Version Conflict:**
```json
{
  "error": "Version conflict detected",
  "conflict_id": "...",
  "server_version": 3,
  "server_data": {...},
  "options": ["OVERWRITE", "KEEP_SERVER"]
}
```

---

## Rate Limiting

Currently not implemented. To add:
1. Install `djangorestframework-throttling`
2. Configure in `settings.py`
3. Add to views

---

## Pagination

Default page size: 50 records

Request:
```
GET /api/v1/reports/?page=2
```

Response:
```json
{
  "count": 150,
  "next": "http://.../api/v1/reports/?page=3",
  "previous": "http://.../api/v1/reports/?page=1",
  "results": [...]
}
```

---

## Filtering & Search

### Search
```
GET /api/v1/users/?search=john
```

### Ordering
```
GET /api/v1/reports/?ordering=-last_modified
GET /api/v1/audit-logs/?ordering=created_at
```

---

## Performance Tips

1. Use pagination for large datasets
2. Use search/filtering to reduce response size
3. Cache access tokens client-side
4. Batch sync operations with bulk_sync endpoint
5. Archive old audit logs periodically
6. Compress API responses (handled by Django)

---

## Examples

### Complete Workflow: Create and Sync Report

1. **Create report offline (client-side)**
2. **When online, sync:**
```bash
curl -X POST http://localhost:8000/api/v1/sync/bulk_sync/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "actions": [{
      "action_type": "CREATE_REPORT",
      "data": { "mda_name": "Test MDA", "capexPerformance": 75 }
    }],
    "device_id": "device-123",
    "last_sync": "2024-04-29T10:00:00Z"
  }'
```

3. **Handle conflicts if needed**
4. **Get updated reports:**
```bash
curl http://localhost:8000/api/v1/reports/ \
  -H "Authorization: Bearer <token>"
```

---

For more information, see README.md and source code comments.
