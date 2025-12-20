"""Question import routes for parsing Word and Excel files."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.core.responses import success_response
from app.services.question_import import (
    ImportResult,
    detect_file_type,
    parse_question_file,
)
from app.services.ai_question_refiner import (
    refine_questions_with_ai,
    extract_text_for_ai,
)

router = APIRouter(prefix="/forms/import", tags=["Form Import"])

# Maximum file size: 10MB
MAX_FILE_SIZE = 10 * 1024 * 1024


@router.post("/questions", response_model=dict)
async def import_questions(
    file: UploadFile = File(...),
    current_user: Annotated[dict[str, Any], Depends(get_current_user)] = None,
):
    """
    Parse a Word document or Excel file and extract questions.

    **Supported formats:**
    - Word documents (.docx)
    - Excel files (.xlsx, .xls)

    **Word Document Format:**
    Questions should be numbered (e.g., "1. What is your name?").
    Options use the ☐ checkbox character.

    Example:
    ```
    SECTION A: PERSONAL INFO
    1. What is your name? __________
    2. Gender:
    ☐ Male ☐ Female ☐ Other
    3. Services used (tick all that apply):
    ☐ Healthcare
    ☐ Education
    ☐ Transportation
    ```

    **Excel Format:**
    Use columns: question, type, options, required, help_text, allow_other, section

    Options should be pipe-separated: "Option 1|Option 2|Option 3"

    **Response:**
    ```json
    {
        "success": true,
        "data": {
            "questions": [...],
            "sections": [...],
            "warnings": [...]
        },
        "message": "Successfully parsed 10 questions"
    }
    ```
    """
    # Validate file is provided
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "message": "No file provided",
                "errors": {"file": ["Please upload a file"]},
            },
        )

    # Validate file type
    file_type = detect_file_type(file.filename, file.content_type)
    if not file_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "message": "Unsupported file format",
                "errors": {
                    "file": [
                        "Please upload a Word document (.docx) or Excel file (.xlsx)"
                    ]
                },
            },
        )

    # Check for old .doc format
    if file.filename and file.filename.lower().endswith(".doc"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "message": "Unsupported file format",
                "errors": {
                    "file": [
                        "Old .doc format is not supported. Please save as .docx"
                    ]
                },
            },
        )

    # Read file content
    try:
        content = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "message": "Failed to read file",
                "errors": {"file": [str(e)]},
            },
        ) from e

    # Check file size
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "success": False,
                "message": "File too large",
                "errors": {
                    "file": [f"File size exceeds maximum allowed ({MAX_FILE_SIZE // 1024 // 1024}MB)"]
                },
            },
        )

    # Check for empty file
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "message": "Empty file",
                "errors": {"file": ["The uploaded file is empty"]},
            },
        )

    # Parse the file
    result: ImportResult = parse_question_file(
        file_content=content,
        filename=file.filename,
        content_type=file.content_type,
    )

    # Check for parse errors
    if not result.questions and result.warnings:
        # All warnings, no questions - likely a parse failure
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "message": "Failed to parse file",
                "errors": {"file": result.warnings},
            },
        )

    # Return success response
    question_count = len(result.questions)
    section_count = len(result.sections)

    message = f"Successfully parsed {question_count} question{'s' if question_count != 1 else ''}"
    if section_count > 0:
        message += f" in {section_count} section{'s' if section_count != 1 else ''}"

    return success_response(
        data={
            "questions": [q.model_dump() for q in result.questions],
            "sections": result.sections,
            "warnings": result.warnings,
        },
        message=message,
    )


@router.get("/template", response_model=dict)
async def get_import_template_info(
    current_user: Annotated[dict[str, Any], Depends(get_current_user)] = None,
):
    """
    Get information about the import template format.

    Returns column descriptions and valid field types for creating an Excel template.
    """
    return success_response(
        data={
            "columns": [
                {
                    "name": "question_number",
                    "required": False,
                    "description": "Optional ordering number for the question",
                },
                {
                    "name": "question",
                    "required": True,
                    "description": "The question text that will be shown to respondents",
                },
                {
                    "name": "type",
                    "required": True,
                    "description": "The field type (see valid_types)",
                },
                {
                    "name": "options",
                    "required": False,
                    "description": "For choice fields. Separate options with | (pipe character)",
                },
                {
                    "name": "required",
                    "required": False,
                    "description": "Whether this field is required. Use: yes, no, true, false",
                },
                {
                    "name": "help_text",
                    "required": False,
                    "description": "Optional help text shown below the question",
                },
                {
                    "name": "allow_other",
                    "required": False,
                    "description": "For choice fields. Allow 'Other' option with text input",
                },
                {
                    "name": "section",
                    "required": False,
                    "description": "Optional section name to group questions",
                },
                {
                    "name": "depends_on",
                    "required": False,
                    "description": "Question number this field depends on (for conditional logic)",
                },
                {
                    "name": "show_when",
                    "required": False,
                    "description": "Value of the dependent question that triggers this field",
                },
            ],
            "valid_types": [
                {"value": "text", "label": "Short text input"},
                {"value": "textarea", "label": "Long text input (paragraph)"},
                {"value": "email", "label": "Email address"},
                {"value": "phone", "label": "Phone number"},
                {"value": "number", "label": "Numeric input"},
                {"value": "date", "label": "Date picker"},
                {"value": "radio", "label": "Single choice (radio buttons)"},
                {"value": "checkbox", "label": "Multiple choice (checkboxes)"},
                {"value": "select", "label": "Dropdown menu"},
                {"value": "rating", "label": "Star rating (1-5)"},
                {"value": "range", "label": "Slider (numeric range)"},
                {"value": "gps", "label": "GPS location capture"},
                {"value": "file", "label": "File upload"},
                {"value": "signature", "label": "Signature capture"},
            ],
            "example_row": {
                "question_number": 1,
                "question": "What is your age group?",
                "type": "radio",
                "options": "18-25|26-35|36-45|46+",
                "required": "yes",
                "help_text": "Select your age bracket",
                "allow_other": "no",
                "section": "Demographics",
                "depends_on": "",
                "show_when": "",
            },
        },
        message="Template information retrieved successfully",
    )


class AIRefineRequest(BaseModel):
    """Request body for AI refinement with raw text."""

    document_text: str
    existing_questions: list[dict] | None = None


@router.post("/refine-with-ai", response_model=dict)
async def refine_questions_with_ai_endpoint(
    file: UploadFile = File(None),
    request_body: AIRefineRequest | None = None,
    current_user: Annotated[dict[str, Any], Depends(get_current_user)] = None,
):
    """
    Use AI (GPT-4o) to extract and refine questions from a document.

    This endpoint provides AI-powered question extraction that is more accurate
    than rule-based parsing, especially for:
    - Complex document structures
    - Ambiguous field types (radio vs checkbox)
    - Conditional logic detection
    - Likert scale identification

    **Two ways to use this endpoint:**

    1. **Upload a file** - Send the document directly
    2. **Send document text** - Send raw text in the request body

    **Request (file upload):**
    ```
    POST /v1/forms/import/refine-with-ai
    Content-Type: multipart/form-data
    file: <your-document.docx>
    ```

    **Request (text body):**
    ```json
    {
        "document_text": "1. What is your name? __________",
        "existing_questions": []  // Optional: previous parsing results
    }
    ```

    **Response:**
    ```json
    {
        "success": true,
        "data": {
            "questions": [...],
            "sections": [...],
            "summary": "Extracted 20 questions across 4 sections"
        },
        "message": "AI successfully refined 20 questions"
    }
    ```

    **Note:** Requires OPENAI_API_KEY environment variable to be set.
    """
    document_text = ""
    existing_questions = None

    # Handle file upload
    if file and file.filename:
        # Validate file type
        file_type = detect_file_type(file.filename, file.content_type)
        if not file_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "success": False,
                    "message": "Unsupported file format",
                    "errors": {
                        "file": [
                            "Please upload a Word document (.docx) or Excel file (.xlsx)"
                        ]
                    },
                },
            )

        # Read file content
        try:
            content = await file.read()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "success": False,
                    "message": "Failed to read file",
                    "errors": {"file": [str(e)]},
                },
            ) from e

        # Check file size
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail={
                    "success": False,
                    "message": "File too large",
                    "errors": {
                        "file": [
                            f"File size exceeds maximum allowed ({MAX_FILE_SIZE // 1024 // 1024}MB)"
                        ]
                    },
                },
            )

        # Extract text for AI
        document_text = await extract_text_for_ai(content, file_type)

    # Handle text body
    elif request_body and request_body.document_text:
        document_text = request_body.document_text
        existing_questions = request_body.existing_questions

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "message": "No input provided",
                "errors": {
                    "file": ["Please upload a file or provide document_text in the request body"]
                },
            },
        )

    # Check if we have text to process
    if not document_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "message": "Empty document",
                "errors": {"file": ["The document appears to be empty"]},
            },
        )

    # Call AI refinement service
    result = await refine_questions_with_ai(document_text, existing_questions)

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "message": "AI refinement failed",
                "errors": {"ai": [result.error or "Unknown error"]},
            },
        )

    # Return success response
    question_count = len(result.questions)
    section_count = len(result.sections)

    message = f"AI successfully refined {question_count} question{'s' if question_count != 1 else ''}"
    if section_count > 0:
        message += f" in {section_count} section{'s' if section_count != 1 else ''}"

    return success_response(
        data={
            "questions": [q.model_dump() for q in result.questions],
            "sections": result.sections,
            "summary": result.summary,
        },
        message=message,
    )
