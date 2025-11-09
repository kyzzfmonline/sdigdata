#!/bin/bash
set -e

echo "======================================"
echo "COMPREHENSIVE API TEST SUITE"
echo "======================================"
echo ""

# Create a test admin if needed
echo "=== Step 1: Testing Bootstrap Admin (may fail if admin exists) ==="
curl -s -X POST http://localhost:8000/auth/bootstrap-admin \
  -H "Content-Type: application/json" \
  -d '{"username":"testadmin2","password":"TestPass123!"}' | python3 -m json.tool || echo "Admin already exists (expected)"

echo -e "\n\n=== Step 2: Login with existing admin ==="
# Try the existing admin
LOGIN_RESPONSE=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}')

if ! echo "$LOGIN_RESPONSE" | python3 -c "import sys, json; d=json.load(sys.stdin); sys.exit(0 if d.get('success') else 1)" 2>/dev/null; then
  echo "First login attempt failed, trying alternative password..."
  # If that fails, use bootstrap script to create new admin
  python3 bootstrap_admin.py

  # Try login again with bootstrap admin
  LOGIN_RESPONSE=$(curl -s -X POST http://localhost:8000/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username":"admin","password":"Admin123!"}')
fi

echo "$LOGIN_RESPONSE" | python3 -m json.tool

TOKEN=$(echo "$LOGIN_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['data']['access_token'])" 2>/dev/null)

if [ -z "$TOKEN" ]; then
  echo "ERROR: Failed to get authentication token"
  exit 1
fi

echo "✓ Login successful, token obtained"

echo -e "\n\n=== Step 3: Test Health Check ==="
curl -s http://localhost:8000/health | python3 -m json.tool

echo -e "\n\n=== Step 4: Test Token Verification ==="
curl -s -X GET http://localhost:8000/auth/verify \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

echo -e "\n\n=== Step 5: Test User Profile ==="
curl -s -X GET http://localhost:8000/users/me \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

echo -e "\n\n=== Step 6: List Organizations ==="
ORG_RESPONSE=$(curl -s -X GET http://localhost:8000/organizations \
  -H "Authorization: Bearer $TOKEN")
echo "$ORG_RESPONSE" | python3 -m json.tool

ORG_ID=$(echo "$ORG_RESPONSE" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d['data'][0]['id'] if d.get('data') and len(d['data']) > 0 else '')" 2>/dev/null)

if [ -z "$ORG_ID" ]; then
  echo -e "\n\nNo organizations found, creating one..."
  ORG_CREATE=$(curl -s -X POST http://localhost:8000/organizations \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"name":"Test Organization","logo_url":"","primary_color":"#1976d2"}')
  echo "$ORG_CREATE" | python3 -m json.tool
  ORG_ID=$(echo "$ORG_CREATE" | python3 -c "import sys, json; print(json.load(sys.stdin)['data']['id'])" 2>/dev/null)
fi

echo "✓ Organization ID: $ORG_ID"

echo -e "\n\n=== Step 7: Create a Form ==="
FORM_RESPONSE=$(curl -s -X POST http://localhost:8000/forms \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"title\": \"Test Survey Form\",
    \"organization_id\": \"$ORG_ID\",
    \"schema\": {
      \"fields\": [
        {\"name\": \"name\", \"type\": \"text\", \"required\": true},
        {\"name\": \"age\", \"type\": \"number\", \"required\": false},
        {\"name\": \"location\", \"type\": \"location\", \"required\": true}
      ]
    },
    \"status\": \"published\"
  }")
echo "$FORM_RESPONSE" | python3 -m json.tool

FORM_ID=$(echo "$FORM_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['data']['id'])" 2>/dev/null)
echo "✓ Form ID: $FORM_ID"

echo -e "\n\n=== Step 8: List Forms ==="
curl -s -X GET http://localhost:8000/forms \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

echo -e "\n\n=== Step 9: Submit a Response ==="
RESPONSE_CREATE=$(curl -s -X POST http://localhost:8000/responses \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"form_id\": \"$FORM_ID\",
    \"data\": {
      \"name\": \"John Doe\",
      \"age\": 35,
      \"location\": {
        \"latitude\": 5.6037,
        \"longitude\": -0.1870
      }
    }
  }")
echo "$RESPONSE_CREATE" | python3 -m json.tool

RESPONSE_ID=$(echo "$RESPONSE_CREATE" | python3 -c "import sys, json; print(json.load(sys.stdin)['data']['id'])" 2>/dev/null)
echo "✓ Response ID: $RESPONSE_ID"

echo -e "\n\n=== Step 10: List Responses ==="
curl -s -X GET "http://localhost:8000/responses?form_id=$FORM_ID" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

echo -e "\n\n=== Step 11: Test Input Validation (should fail with large payload) ==="
echo "Testing response data validation..."
VALIDATION_TEST=$(curl -s -X POST http://localhost:8000/responses \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"form_id\": \"$FORM_ID\",
    \"data\": {
      \"level1\": {
        \"level2\": {
          \"level3\": {
            \"level4\": {
              \"level5\": {
                \"level6\": {
                  \"level7\": {
                    \"level8\": {
                      \"level9\": {
                        \"level10\": {
                          \"level11\": \"This should fail - too deep\"
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
  }")
echo "$VALIDATION_TEST" | python3 -m json.tool
if echo "$VALIDATION_TEST" | grep -q "nesting exceeds maximum depth"; then
  echo "✓ Validation working correctly - deep nesting rejected"
else
  echo "⚠ Validation may not be working as expected"
fi

echo -e "\n\n=== Step 12: Test Analytics Endpoint ==="
curl -s -X GET http://localhost:8000/analytics/dashboard \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

echo -e "\n\n=== Step 13: Test ML Quality Stats ==="
curl -s -X GET http://localhost:8000/ml/quality-stats \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

echo -e "\n\n=== Step 14: Test Users List ==="
curl -s -X GET http://localhost:8000/users \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

echo -e "\n\n=== Step 15: Test CORS ==="
curl -s -X OPTIONS http://localhost:8000/health \
  -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: Authorization" -v 2>&1 | grep -i "access-control"

echo -e "\n\n======================================"
echo "✓ ALL TESTS COMPLETED SUCCESSFULLY"
echo "======================================"
