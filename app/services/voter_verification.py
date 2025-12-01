"""Voter verification service functions."""

import hashlib
import secrets
from datetime import datetime, timedelta
from uuid import UUID

import asyncpg

from app.services.voting import hash_identifier


# ============================================
# OTP GENERATION & VERIFICATION
# ============================================


def generate_otp(length: int = 6) -> str:
    """Generate a numeric OTP code."""
    return "".join(secrets.choice("0123456789") for _ in range(length))


async def create_otp_token(
    conn: asyncpg.Connection,
    election_id: UUID,
    phone: str,
    expires_minutes: int = 10,
) -> tuple[str, datetime]:
    """Create an OTP token for phone verification."""
    phone_hash = hash_identifier(phone)
    otp = generate_otp()
    token_hash = hash_identifier(otp)
    expires_at = datetime.utcnow() + timedelta(minutes=expires_minutes)

    # Invalidate any existing tokens for this phone
    await conn.execute(
        """
        UPDATE election_otp_tokens
        SET used = TRUE
        WHERE election_id = $1 AND phone_hash = $2 AND used = FALSE
        """,
        str(election_id),
        phone_hash,
    )

    # Create new token
    await conn.execute(
        """
        INSERT INTO election_otp_tokens (election_id, phone_hash, token_hash, expires_at)
        VALUES ($1, $2, $3, $4)
        """,
        str(election_id),
        phone_hash,
        token_hash,
        expires_at,
    )

    return otp, expires_at


async def verify_otp_token(
    conn: asyncpg.Connection,
    election_id: UUID,
    phone: str,
    otp: str,
) -> tuple[bool, str]:
    """Verify an OTP token. Returns (success, message)."""
    phone_hash = hash_identifier(phone)
    token_hash = hash_identifier(otp)

    # Find matching token
    token = await conn.fetchrow(
        """
        SELECT id, expires_at, used, attempts
        FROM election_otp_tokens
        WHERE election_id = $1 AND phone_hash = $2 AND token_hash = $3
        ORDER BY created_at DESC
        LIMIT 1
        """,
        str(election_id),
        phone_hash,
        token_hash,
    )

    if not token:
        # Check if there's a token with too many attempts
        existing = await conn.fetchrow(
            """
            SELECT id, attempts
            FROM election_otp_tokens
            WHERE election_id = $1 AND phone_hash = $2 AND used = FALSE
            ORDER BY created_at DESC
            LIMIT 1
            """,
            str(election_id),
            phone_hash,
        )

        if existing:
            # Increment attempts
            await conn.execute(
                """
                UPDATE election_otp_tokens
                SET attempts = attempts + 1
                WHERE id = $1
                """,
                existing["id"],
            )

            if existing["attempts"] >= 5:
                return False, "Too many failed attempts. Please request a new code."

        return False, "Invalid verification code"

    if token["used"]:
        return False, "This code has already been used"

    if token["expires_at"] < datetime.utcnow():
        return False, "Verification code has expired"

    # Mark token as used
    await conn.execute(
        """
        UPDATE election_otp_tokens
        SET used = TRUE, used_at = CURRENT_TIMESTAMP
        WHERE id = $1
        """,
        token["id"],
    )

    return True, "Verification successful"


async def get_otp_rate_limit_status(
    conn: asyncpg.Connection,
    election_id: UUID,
    phone: str,
    window_minutes: int = 5,
    max_requests: int = 3,
) -> tuple[bool, int]:
    """Check OTP rate limit. Returns (can_request, remaining_requests)."""
    phone_hash = hash_identifier(phone)
    window_start = datetime.utcnow() - timedelta(minutes=window_minutes)

    count = await conn.fetchval(
        """
        SELECT COUNT(*)
        FROM election_otp_tokens
        WHERE election_id = $1 AND phone_hash = $2 AND created_at >= $3
        """,
        str(election_id),
        phone_hash,
        window_start,
    )

    remaining = max(0, max_requests - count)
    can_request = count < max_requests

    return can_request, remaining


# ============================================
# NATIONAL ID VERIFICATION
# ============================================


async def verify_national_id(
    conn: asyncpg.Connection,
    election_id: UUID,
    national_id: str,
) -> tuple[bool, str, dict | None]:
    """
    Verify a national ID.

    In production, this would integrate with a government ID verification API.
    For now, this is a placeholder that validates format.

    Returns (success, message, voter_data).
    """
    # Basic format validation (adjust based on actual ID format)
    if not national_id or len(national_id) < 6:
        return False, "Invalid national ID format", None

    # Check if this national ID has already voted in this election
    id_hash = hash_identifier(national_id)
    existing = await conn.fetchrow(
        """
        SELECT id, has_voted
        FROM voters
        WHERE election_id = $1 AND national_id_hash = $2
        """,
        str(election_id),
        id_hash,
    )

    if existing and existing["has_voted"]:
        return False, "This national ID has already voted in this election", None

    # In production, call external verification API here
    # For now, assume valid and extract mock demographic data
    voter_data = {
        "national_id_hash": id_hash,
        "verified": True,
        # Mock demographic data (would come from ID verification service)
        "region": None,  # Would be extracted from ID
        "age_group": None,  # Would be calculated from DOB on ID
    }

    return True, "National ID verified successfully", voter_data


# ============================================
# COMBINED VERIFICATION FLOW
# ============================================


async def verify_voter_eligibility(
    conn: asyncpg.Connection,
    election_id: UUID,
    national_id: str | None = None,
    phone: str | None = None,
    otp: str | None = None,
    user_id: UUID | None = None,
) -> tuple[bool, str, str | None]:
    """
    Verify voter eligibility based on election requirements.

    Returns (success, message, voter_token).
    """
    # Get election verification requirements
    election = await conn.fetchrow(
        """
        SELECT verification_level, require_national_id, require_phone_otp, status
        FROM elections
        WHERE id = $1 AND deleted = FALSE
        """,
        str(election_id),
    )

    if not election:
        return False, "Election not found", None

    if election["status"] not in ("active", "scheduled"):
        return False, f"Election is {election['status']}", None

    verification_level = election["verification_level"]

    # Anonymous verification
    if verification_level == "anonymous":
        # Generate anonymous voter token
        voter_token = hash_identifier(f"anon:{secrets.token_hex(16)}")
        return True, "Anonymous voting enabled", voter_token

    # Registered user verification
    if verification_level == "registered":
        if not user_id:
            return False, "User authentication required", None

        # Check if user has already voted
        existing = await conn.fetchrow(
            """
            SELECT id, has_voted
            FROM voters
            WHERE election_id = $1 AND user_id = $2
            """,
            str(election_id),
            str(user_id),
        )

        if existing and existing["has_voted"]:
            return False, "You have already voted in this election", None

        voter_token = hash_identifier(f"user:{user_id}:{election_id}")
        return True, "User verified", voter_token

    # Verified (National ID / Phone OTP) verification
    if verification_level == "verified":
        require_national_id = election["require_national_id"]
        require_phone_otp = election["require_phone_otp"]

        # Verify national ID if required
        if require_national_id:
            if not national_id:
                return False, "National ID required", None

            success, msg, _ = await verify_national_id(conn, election_id, national_id)
            if not success:
                return False, msg, None

        # Verify phone OTP if required
        if require_phone_otp:
            if not phone or not otp:
                return False, "Phone verification required", None

            success, msg = await verify_otp_token(conn, election_id, phone, otp)
            if not success:
                return False, msg, None

        # Generate voter token based on primary identifier
        if national_id:
            voter_token = hash_identifier(f"national_id:{national_id}:{election_id}")
        elif phone:
            voter_token = hash_identifier(f"phone:{phone}:{election_id}")
        else:
            return False, "No valid identifier provided", None

        return True, "Voter verified", voter_token

    return False, "Unknown verification level", None


# ============================================
# VOTER REGISTRATION
# ============================================


async def register_verified_voter(
    conn: asyncpg.Connection,
    election_id: UUID,
    voter_token: str,
    national_id: str | None = None,
    phone: str | None = None,
    user_id: UUID | None = None,
    region: str | None = None,
    age_group: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict | None:
    """Register a verified voter."""
    national_id_hash = hash_identifier(national_id) if national_id else None
    phone_hash = hash_identifier(phone) if phone else None

    # Determine verification method
    if national_id and phone:
        verification_method = "both"
    elif national_id:
        verification_method = "national_id"
    elif phone:
        verification_method = "phone_otp"
    elif user_id:
        verification_method = "user_account"
    else:
        verification_method = None

    result = await conn.fetchrow(
        """
        INSERT INTO voters (
            election_id, national_id_hash, phone_hash, user_id,
            verified_at, verification_method,
            region, age_group, ip_address, user_agent
        )
        VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP, $5, $6, $7, $8, $9)
        ON CONFLICT (election_id, national_id_hash) DO UPDATE
        SET verified_at = CURRENT_TIMESTAMP, verification_method = EXCLUDED.verification_method
        RETURNING *
        """,
        str(election_id),
        national_id_hash,
        phone_hash,
        str(user_id) if user_id else None,
        verification_method,
        region,
        age_group,
        ip_address,
        user_agent,
    )

    if result:
        result_dict = dict(result)
        if result_dict.get("ip_address"):
            result_dict["ip_address"] = str(result_dict["ip_address"])
        return result_dict

    return None


# ============================================
# SMS SENDING (PLACEHOLDER)
# ============================================


async def send_sms_otp(phone: str, otp: str, election_title: str) -> tuple[bool, str]:
    """
    Send OTP via SMS.

    This is a placeholder - implement with actual SMS provider
    (Twilio, AWS SNS, Africa's Talking, etc.)
    """
    # TODO: Implement actual SMS sending
    # Example with Twilio:
    # from twilio.rest import Client
    # client = Client(account_sid, auth_token)
    # message = client.messages.create(
    #     body=f"Your verification code for {election_title} is: {otp}. Valid for 10 minutes.",
    #     from_="+1234567890",
    #     to=phone
    # )

    # For development, just log
    print(f"[SMS] Sending OTP {otp} to {phone} for election: {election_title}")

    return True, "SMS sent successfully"


async def request_phone_verification(
    conn: asyncpg.Connection,
    election_id: UUID,
    phone: str,
) -> tuple[bool, str]:
    """Request phone verification (create and send OTP)."""
    # Check rate limit
    can_request, remaining = await get_otp_rate_limit_status(conn, election_id, phone)

    if not can_request:
        return False, "Too many verification requests. Please try again later."

    # Get election title for SMS
    election = await conn.fetchrow(
        "SELECT title FROM elections WHERE id = $1",
        str(election_id),
    )

    if not election:
        return False, "Election not found"

    # Create OTP
    otp, expires_at = await create_otp_token(conn, election_id, phone)

    # Send SMS
    success, msg = await send_sms_otp(phone, otp, election["title"])

    if not success:
        return False, f"Failed to send verification code: {msg}"

    return True, f"Verification code sent. Expires at {expires_at.isoformat()}"
