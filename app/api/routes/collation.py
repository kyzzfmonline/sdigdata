"""Collation API routes.

Handles result sheets, collation workflow, aggregation, and real-time updates.
"""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.responses import success_response
from app.api.deps import get_current_user
from app.services import result_sheets as sheets_service
from app.services import collation as collation_service

router = APIRouter(prefix="/collation", tags=["Collation"])


# ============================================
# PYDANTIC MODELS
# ============================================


class ResultSheetCreate(BaseModel):
    """Create result sheet request."""

    election_id: UUID
    polling_station_id: UUID | None = None
    collation_center_id: UUID | None = None
    sheet_type: str = Field(
        ...,
        pattern="^(polling_station|electoral_area|constituency|regional|national)$",
    )


class ResultEntryCreate(BaseModel):
    """Create result entry request."""

    position_id: UUID | None = None
    candidate_id: UUID | None = None
    poll_option_id: UUID | None = None
    votes: int = Field(..., ge=0)
    votes_in_words: str | None = None


class BulkEntriesRequest(BaseModel):
    """Bulk entries request."""

    entries: list[ResultEntryCreate]


class SheetTotalsUpdate(BaseModel):
    """Update sheet totals."""

    total_registered_voters: int | None = None
    total_votes_cast: int | None = None
    total_valid_votes: int | None = None
    total_rejected_votes: int | None = None


class AttachmentCreate(BaseModel):
    """Create attachment request."""

    attachment_type: str = Field(..., pattern="^(pink_sheet|photo|signature|other)$")
    file_url: str
    file_name: str | None = None


class WorkflowActionRequest(BaseModel):
    """Workflow action request."""

    notes: str | None = None


class RejectRequest(BaseModel):
    """Reject request with reason."""

    reason: str = Field(..., min_length=10)


class OfficerCreate(BaseModel):
    """Create collation officer request."""

    user_id: UUID
    officer_type: str = Field(
        ...,
        pattern="^(presiding|returning|deputy_returning|collation_clerk)$",
    )
    national_id: str | None = None
    phone: str | None = None


class OfficerAssignRequest(BaseModel):
    """Assign officer request."""

    officer_id: UUID
    election_id: UUID
    polling_station_id: UUID | None = None
    collation_center_id: UUID | None = None
    role: str = Field(
        ...,
        pattern="^(presiding_officer|returning_officer|collation_clerk)$",
    )


class IncidentReport(BaseModel):
    """Report incident request."""

    election_id: UUID
    polling_station_id: UUID | None = None
    collation_center_id: UUID | None = None
    incident_type: str = Field(
        ...,
        pattern="^(violence|equipment_failure|irregularity|protest|other)$",
    )
    severity: str = Field(..., pattern="^(low|medium|high|critical)$")
    description: str = Field(..., min_length=20)
    evidence_urls: list[str] | None = None


class IncidentResolve(BaseModel):
    """Resolve incident request."""

    resolution_notes: str = Field(..., min_length=10)


class CollationCenterCreate(BaseModel):
    """Create collation center request."""

    name: str = Field(..., min_length=2)
    center_type: str = Field(
        ...,
        pattern="^(electoral_area|constituency|regional|national)$",
    )
    electoral_area_id: UUID | None = None
    constituency_id: UUID | None = None
    region_id: UUID | None = None
    address: str | None = None
    gps_coordinates: str | None = None


# ============================================
# RESULT SHEETS
# ============================================


@router.post("/sheets")
async def create_result_sheet(
    request: ResultSheetCreate,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Create a new result sheet."""
    sheet = await sheets_service.create_result_sheet(
        conn,
        election_id=request.election_id,
        polling_station_id=request.polling_station_id,
        collation_center_id=request.collation_center_id,
        sheet_type=request.sheet_type,
        created_by=UUID(current_user["id"]),
    )
    return success_response(data=sheet, message="Result sheet created successfully")


@router.get("/sheets")
async def list_result_sheets(
    election_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    sheet_type: str | None = None,
    status: str | None = None,
    collation_center_id: UUID | None = None,
    constituency_id: UUID | None = None,
    region_id: UUID | None = None,
    limit: int = Query(100, le=500),
    offset: int = 0,
):
    """List result sheets for an election."""
    sheets = await sheets_service.list_result_sheets(
        conn,
        election_id,
        sheet_type=sheet_type,
        status=status,
        collation_center_id=collation_center_id,
        constituency_id=constituency_id,
        region_id=region_id,
        limit=limit,
        offset=offset,
    )
    return success_response(data={"sheets": sheets, "count": len(sheets)})


@router.get("/sheets/{sheet_id}")
async def get_result_sheet(
    sheet_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Get a result sheet with full details."""
    sheet = await sheets_service.get_sheet_summary(conn, sheet_id)
    if not sheet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Result sheet not found",
        )
    return success_response(data=sheet)


@router.patch("/sheets/{sheet_id}/totals")
async def update_sheet_totals(
    sheet_id: UUID,
    request: SheetTotalsUpdate,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Update result sheet totals."""
    updates = request.model_dump(exclude_unset=True)
    sheet = await sheets_service.update_result_sheet(conn, sheet_id, **updates)
    if not sheet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Result sheet not found",
        )
    return success_response(data=sheet, message="Totals updated successfully")


# ============================================
# RESULT ENTRIES
# ============================================


@router.post("/sheets/{sheet_id}/entries")
async def add_result_entry(
    sheet_id: UUID,
    request: ResultEntryCreate,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Add a vote count entry to a result sheet."""
    entry = await sheets_service.add_result_entry(
        conn,
        result_sheet_id=sheet_id,
        position_id=request.position_id,
        candidate_id=request.candidate_id,
        poll_option_id=request.poll_option_id,
        votes=request.votes,
        votes_in_words=request.votes_in_words,
    )
    return success_response(data=entry, message="Entry added successfully")


@router.post("/sheets/{sheet_id}/entries/bulk")
async def bulk_add_entries(
    sheet_id: UUID,
    request: BulkEntriesRequest,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Bulk add/update vote entries."""
    entries = [e.model_dump() for e in request.entries]
    count = await sheets_service.bulk_update_entries(conn, sheet_id, entries)
    return success_response(
        data={"entries_updated": count},
        message=f"{count} entries updated successfully",
    )


@router.get("/sheets/{sheet_id}/entries")
async def get_result_entries(
    sheet_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Get all vote entries for a result sheet."""
    entries = await sheets_service.get_result_entries(conn, sheet_id)
    return success_response(data={"entries": entries, "count": len(entries)})


# ============================================
# ATTACHMENTS
# ============================================


@router.post("/sheets/{sheet_id}/attachments")
async def add_attachment(
    sheet_id: UUID,
    request: AttachmentCreate,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Add an attachment to a result sheet."""
    attachment = await sheets_service.add_attachment(
        conn,
        result_sheet_id=sheet_id,
        attachment_type=request.attachment_type,
        file_url=request.file_url,
        file_name=request.file_name,
        uploaded_by=UUID(current_user["id"]),
    )
    return success_response(data=attachment, message="Attachment added successfully")


@router.get("/sheets/{sheet_id}/attachments")
async def get_attachments(
    sheet_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Get all attachments for a result sheet."""
    attachments = await sheets_service.get_attachments(conn, sheet_id)
    return success_response(data={"attachments": attachments, "count": len(attachments)})


@router.delete("/attachments/{attachment_id}")
async def delete_attachment(
    attachment_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Delete an attachment."""
    success = await sheets_service.delete_attachment(conn, attachment_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found",
        )
    return success_response(message="Attachment deleted successfully")


# ============================================
# WORKFLOW
# ============================================


@router.post("/sheets/{sheet_id}/submit")
async def submit_result_sheet(
    sheet_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Submit a result sheet for verification."""
    try:
        sheet = await sheets_service.submit_result_sheet(
            conn, sheet_id, UUID(current_user["id"])
        )
        if not sheet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Result sheet not found",
            )
        return success_response(data=sheet, message="Result sheet submitted for verification")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/sheets/{sheet_id}/verify")
async def verify_result_sheet(
    sheet_id: UUID,
    request: WorkflowActionRequest,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Verify a submitted result sheet."""
    try:
        sheet = await sheets_service.verify_result_sheet(
            conn, sheet_id, UUID(current_user["id"]), notes=request.notes
        )
        if not sheet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Result sheet not found",
            )
        return success_response(data=sheet, message="Result sheet verified")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/sheets/{sheet_id}/approve")
async def approve_result_sheet(
    sheet_id: UUID,
    request: WorkflowActionRequest,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Approve a verified result sheet."""
    try:
        sheet = await sheets_service.approve_result_sheet(
            conn, sheet_id, UUID(current_user["id"]), notes=request.notes
        )
        if not sheet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Result sheet not found",
            )
        return success_response(data=sheet, message="Result sheet approved")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/sheets/{sheet_id}/certify")
async def certify_result_sheet(
    sheet_id: UUID,
    request: WorkflowActionRequest,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Certify an approved result sheet (final status)."""
    try:
        sheet = await sheets_service.certify_result_sheet(
            conn, sheet_id, UUID(current_user["id"]), notes=request.notes
        )
        if not sheet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Result sheet not found",
            )
        return success_response(data=sheet, message="Result sheet certified")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/sheets/{sheet_id}/reject")
async def reject_result_sheet(
    sheet_id: UUID,
    request: RejectRequest,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Reject a result sheet back to draft."""
    sheet = await sheets_service.reject_result_sheet(
        conn, sheet_id, UUID(current_user["id"]), request.reason
    )
    if not sheet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Result sheet not found",
        )
    return success_response(data=sheet, message="Result sheet rejected")


@router.get("/sheets/{sheet_id}/history")
async def get_workflow_history(
    sheet_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Get workflow history for a result sheet."""
    history = await sheets_service.get_workflow_history(conn, sheet_id)
    return success_response(data={"history": history, "count": len(history)})


# ============================================
# COLLATION OFFICERS
# ============================================


@router.post("/officers")
async def create_officer(
    request: OfficerCreate,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Register a user as a collation officer."""
    officer = await collation_service.create_collation_officer(
        conn,
        user_id=request.user_id,
        officer_type=request.officer_type,
        national_id=request.national_id,
        phone=request.phone,
    )
    return success_response(data=officer, message="Officer registered successfully")


@router.get("/officers")
async def list_officers(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    officer_type: str | None = None,
    is_active: bool | None = None,
    limit: int = 100,
    offset: int = 0,
):
    """List collation officers."""
    officers = await collation_service.list_collation_officers(
        conn,
        officer_type=officer_type,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )
    return success_response(data={"officers": officers, "count": len(officers)})


@router.get("/officers/{officer_id}")
async def get_officer(
    officer_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Get a collation officer by ID."""
    officer = await collation_service.get_collation_officer(conn, officer_id=officer_id)
    if not officer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Officer not found",
        )
    return success_response(data=officer)


@router.post("/officers/assign")
async def assign_officer(
    request: OfficerAssignRequest,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Assign an officer to a polling station or collation center."""
    assignment = await collation_service.assign_officer(
        conn,
        officer_id=request.officer_id,
        election_id=request.election_id,
        polling_station_id=request.polling_station_id,
        collation_center_id=request.collation_center_id,
        role=request.role,
        assigned_by=UUID(current_user["id"]),
    )
    return success_response(data=assignment, message="Officer assigned successfully")


@router.get("/elections/{election_id}/assignments")
async def get_election_assignments(
    election_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    officer_id: UUID | None = None,
    polling_station_id: UUID | None = None,
):
    """Get officer assignments for an election."""
    assignments = await collation_service.get_officer_assignments(
        conn,
        election_id,
        officer_id=officer_id,
        polling_station_id=polling_station_id,
    )
    return success_response(data={"assignments": assignments, "count": len(assignments)})


@router.delete("/assignments/{assignment_id}")
async def remove_assignment(
    assignment_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Remove an officer assignment."""
    success = await collation_service.remove_assignment(conn, assignment_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found",
        )
    return success_response(message="Assignment removed successfully")


# ============================================
# COLLATION CENTERS
# ============================================


@router.post("/centers")
async def create_collation_center(
    request: CollationCenterCreate,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Create a collation center."""
    center = await collation_service.create_collation_center(
        conn,
        name=request.name,
        center_type=request.center_type,
        electoral_area_id=request.electoral_area_id,
        constituency_id=request.constituency_id,
        region_id=request.region_id,
        address=request.address,
        gps_coordinates=request.gps_coordinates,
    )
    return success_response(data=center, message="Collation center created successfully")


@router.get("/centers")
async def list_collation_centers(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    center_type: str | None = None,
    region_id: UUID | None = None,
    constituency_id: UUID | None = None,
    limit: int = 100,
    offset: int = 0,
):
    """List collation centers."""
    centers = await collation_service.list_collation_centers(
        conn,
        center_type=center_type,
        region_id=region_id,
        constituency_id=constituency_id,
        limit=limit,
        offset=offset,
    )
    return success_response(data={"centers": centers, "count": len(centers)})


# ============================================
# AGGREGATION
# ============================================


@router.get("/elections/{election_id}/aggregate")
async def aggregate_results(
    election_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    level: str = Query(..., pattern="^(electoral_area|constituency|regional|national)$"),
    area_id: UUID | None = None,
):
    """Aggregate results at a specific level."""
    results = await collation_service.aggregate_results(
        conn, election_id, level=level, area_id=area_id
    )
    return success_response(data=results)


@router.post("/elections/{election_id}/aggregate/save")
async def save_aggregation(
    election_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    level: str = Query(..., pattern="^(electoral_area|constituency|regional|national)$"),
    electoral_area_id: UUID | None = None,
    constituency_id: UUID | None = None,
    region_id: UUID | None = None,
):
    """Save aggregated results."""
    # First aggregate
    area_id = electoral_area_id or constituency_id or region_id
    results = await collation_service.aggregate_results(
        conn, election_id, level=level, area_id=area_id
    )

    # Then save
    saved = await collation_service.save_collation_result(
        conn,
        election_id=election_id,
        level=level,
        electoral_area_id=electoral_area_id,
        constituency_id=constituency_id,
        region_id=region_id,
        results_data=results,
        collated_by=UUID(current_user["id"]),
    )
    return success_response(data=saved, message="Collation results saved")


@router.get("/elections/{election_id}/results")
async def get_collation_results(
    election_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    level: str | None = None,
):
    """Get saved collation results."""
    results = await collation_service.get_collation_results(conn, election_id, level=level)
    return success_response(data={"results": results, "count": len(results)})


# ============================================
# DASHBOARD & LIVE FEED
# ============================================


@router.get("/elections/{election_id}/dashboard")
async def get_collation_dashboard(
    election_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Get comprehensive collation dashboard data."""
    dashboard = await collation_service.get_collation_dashboard(conn, election_id)
    if not dashboard:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Election not found",
        )
    return success_response(data=dashboard)


@router.get("/elections/{election_id}/progress")
async def get_submission_progress(
    election_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    region_id: UUID | None = None,
    constituency_id: UUID | None = None,
):
    """Get result sheet submission progress."""
    progress = await sheets_service.get_submission_progress(
        conn, election_id, region_id=region_id, constituency_id=constituency_id
    )
    return success_response(data=progress)


@router.get("/elections/{election_id}/live-feed")
async def get_live_feed(
    election_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    limit: int = Query(20, le=100),
):
    """Get live feed of recent collation activities."""
    feed = await collation_service.get_live_feed(conn, election_id, limit=limit)
    return success_response(data={"feed": feed, "count": len(feed)})


# ============================================
# INCIDENTS
# ============================================


@router.post("/incidents")
async def report_incident(
    request: IncidentReport,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Report a collation incident."""
    incident = await collation_service.report_incident(
        conn,
        election_id=request.election_id,
        polling_station_id=request.polling_station_id,
        collation_center_id=request.collation_center_id,
        incident_type=request.incident_type,
        severity=request.severity,
        description=request.description,
        reported_by=UUID(current_user["id"]),
        evidence_urls=request.evidence_urls,
    )
    return success_response(data=incident, message="Incident reported successfully")


@router.get("/elections/{election_id}/incidents")
async def list_incidents(
    election_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    status: str | None = None,
    severity: str | None = None,
    limit: int = 50,
):
    """List incidents for an election."""
    incidents = await collation_service.list_incidents(
        conn, election_id, status=status, severity=severity, limit=limit
    )
    return success_response(data={"incidents": incidents, "count": len(incidents)})


@router.post("/incidents/{incident_id}/resolve")
async def resolve_incident(
    incident_id: UUID,
    request: IncidentResolve,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Resolve an incident."""
    incident = await collation_service.resolve_incident(
        conn, incident_id, UUID(current_user["id"]), request.resolution_notes
    )
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )
    return success_response(data=incident, message="Incident resolved")


# ============================================
# DISCREPANCIES
# ============================================


@router.get("/elections/{election_id}/discrepancies")
async def get_discrepancies(
    election_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    status: str | None = None,
):
    """Get discrepancies detected in result sheets."""
    discrepancies = await collation_service.get_discrepancies(
        conn, election_id, status=status
    )
    return success_response(
        data={"discrepancies": discrepancies, "count": len(discrepancies)}
    )


@router.post("/discrepancies/{discrepancy_id}/resolve")
async def resolve_discrepancy(
    discrepancy_id: UUID,
    request: IncidentResolve,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Resolve a discrepancy."""
    discrepancy = await collation_service.resolve_discrepancy(
        conn, discrepancy_id, UUID(current_user["id"]), request.resolution_notes
    )
    if not discrepancy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discrepancy not found",
        )
    return success_response(data=discrepancy, message="Discrepancy resolved")
