-- Database Initialization Script
-- Run this script in your PostgreSQL database BEFORE running migrations
-- This ensures all required extensions are available

-- Enable UUID support (required for primary keys)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable PostGIS for geospatial features (required for location tracking)
-- CREATE EXTENSION IF NOT EXISTS postgis;  -- Not available on this server

-- Enable pg_trgm for fuzzy text matching (required for search features)
-- CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- Optional for now

-- Verify extensions are installed
SELECT
    extname AS "Extension",
    extversion AS "Version"
FROM pg_extension
WHERE extname IN ('uuid-ossp', 'postgis', 'pg_trgm')
ORDER BY extname;
