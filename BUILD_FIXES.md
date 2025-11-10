# Build Fixes Applied

This document tracks all the build-related fixes applied to the SDIGdata backend.

---

## ✅ Issues Fixed

### 1. **uv Configuration Update**

**Problem:** Deprecated `[tool.uv.dev-dependencies]` in `pyproject.toml`

**Solution:**
```toml
# Old (deprecated)
[tool.uv]
dev-dependencies = [...]

# New (current)
[dependency-groups]
dev = [...]
```

**Files Changed:** `pyproject.toml`

---

### 2. **Hatchling Build Configuration**

**Problem:** `Unable to determine which files to ship inside the wheel`

**Solution:** Added build configuration to `pyproject.toml`:
```toml
[tool.hatch.build.targets.wheel]
packages = ["app"]
```

**Files Changed:** `pyproject.toml`

---

### 3. **Pydantic Field Name Conflict**

**Problem:** `UserWarning: Field name 'schema' in 'FormCreate' shadows an attribute in parent 'BaseModel'`

**Solution:** Renamed field in API request model:
```python
# Old
class FormCreate(BaseModel):
    schema: dict

# New
class FormCreate(BaseModel):
    form_schema: dict
```

**Important:** Database column and response objects still use `schema`. Only the creation request uses `form_schema`.

**Files Changed:**
- `app/api/routes/forms.py`
- Created `API_NOTES.md` to document this

---

### 4. **Docker Build Process**

**Problem:** Docker build failed because it tried to install dependencies before copying the app code

**Solution:** Updated Dockerfile to copy all files first:
```dockerfile
# Old
COPY pyproject.toml ./
RUN uv sync --frozen --no-dev || uv sync --no-dev
COPY . .

# New
COPY . .
RUN uv sync --no-dev
```

**Why:** Hatchling needs the full project structure to build the package.

**Files Changed:** `Dockerfile`

---

### 5. **Docker Compose Version Warning**

**Problem:** `version` attribute is obsolete in docker-compose.yml

**Solution:** Removed version line:
```yaml
# Old
version: "3.9"
services:

# New
services:
```

**Files Changed:** `docker-compose.yml`

---

## 🧪 Verification

All fixes have been verified:

```bash
# Local build
✓ uv sync                          # Successful
✓ uv run python -c "from app.main import app"  # No warnings
✓ ./verify_setup.sh                # 29/29 checks passed

# Docker build
✓ docker build -t sdigdata-test .  # Successful
✓ docker-compose config            # Valid configuration
```

---

## 📋 Current Build Status

**Local Development:**
- ✅ Dependencies install cleanly
- ✅ No Python warnings
- ✅ App imports successfully
- ✅ All 29 verification checks pass

**Docker:**
- ✅ Dockerfile builds successfully
- ✅ docker-compose configuration valid
- ✅ All services configured correctly

---

## 🔧 Build Commands

### Local Development
```bash
# Install dependencies
uv sync

# Verify installation
uv run python -c "from app.main import app"

# Run verification
./verify_setup.sh
```

### Docker
```bash
# Build image
docker build -t sdigdata-backend .

# Start with docker-compose
docker-compose up -d

# Check status
docker-compose ps
```

---

## 📝 Notes for Future Maintenance

1. **Keep using `[dependency-groups]`** - This is the current uv standard
2. **Always include `[tool.hatch.build.targets.wheel]`** - Required for hatchling
3. **API uses `form_schema`** - Document any new fields that might conflict with Pydantic
4. **Docker copies everything first** - Don't try to optimize with separate dependency layer
5. **No version in docker-compose** - Modern docker-compose doesn't need it

---

## 🔗 Related Documentation

- **[claude.md](claude.md)** - Context for AI, includes common issues
- **[IMPORTANT.md](IMPORTANT.md)** - Critical info, includes troubleshooting
- **[API_NOTES.md](API_NOTES.md)** - API-specific details about field naming

---

**Last Updated:** 2025-11-03
**Build Status:** ✅ All Issues Resolved
