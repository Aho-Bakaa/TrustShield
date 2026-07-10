"""Analysis endpoints: text/URL/social, image/PDF, .eml email, and audio upload."""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from .. import store
from ..documents import pdf_to_text_or_image
from ..email_parser import parse_eml
from ..fusion import analyze
from ..intake import build_request
from ..llm import analyze_email_screenshot, describe_image
from ..log import get_logger
from ..schemas import AnalysisResult, AnalyzeTextRequest, ChannelType, Evidence

router = APIRouter(prefix="/api", tags=["analyze"])
_log = get_logger("api")

_UPLOADS = Path("uploads")
_UPLOADS.mkdir(exist_ok=True)
_AUDIO_EXT = {".wav", ".flac", ".ogg", ".mp3", ".m4a", ".aac", ".opus"}
_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
_DOC_EXT = _IMAGE_EXT | {".pdf", ".eml"}
_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
         ".webp": "image/webp", ".gif": "image/gif", ".bmp": "image/bmp"}


@router.post("/analyze/text", response_model=AnalysisResult)
async def analyze_text(body: AnalyzeTextRequest) -> AnalysisResult:
    if not body.raw_input.strip():
        raise HTTPException(400, "raw_input is empty")
    _log.info("POST /analyze/text channel_hint=%s len=%d", body.channel_hint, len(body.raw_input))
    req = build_request(
        text=body.raw_input,
        channel_hint=body.channel_hint,
        claimed_source=body.claimed_source,
    )
    result = await run_in_threadpool(analyze, req)
    await run_in_threadpool(store.save, result)
    return result


@router.post("/analyze/audio", response_model=AnalysisResult)
async def analyze_audio(
    file: UploadFile = File(...),
    claimed_source: str | None = Form(None),
    context: str | None = Form(None),
) -> AnalysisResult:
    ext = Path(file.filename or "clip.wav").suffix.lower()
    if ext not in _AUDIO_EXT:
        raise HTTPException(400, f"Unsupported audio type '{ext}'. Use {sorted(_AUDIO_EXT)}")
    dest = _UPLOADS / f"{uuid.uuid4().hex[:10]}{ext}"
    data = await file.read()
    dest.write_bytes(data)

    req = build_request(
        text=context or "",
        audio_path=str(dest),
        channel_hint=ChannelType.AUDIO,
        claimed_source=claimed_source,
        original_filename=file.filename,
    )
    result = await run_in_threadpool(analyze, req)
    await run_in_threadpool(store.save, result)
    return result


@router.post("/analyze/image", response_model=AnalysisResult)
async def analyze_image(
    file: UploadFile = File(...),
    claimed_source: str | None = Form(None),
    context: str | None = Form(None),
) -> AnalysisResult:
    """Analyze an uploaded image, PDF, or .eml email file.

    - Images: vision model extracts text + context
    - PDFs: embedded text preferred, scanned pages go to vision
    - .eml: parsed MIME headers (DKIM/SPF/DMARC) + body extracted, then
      screenshot-style vision analysis for visual authenticity
    """
    ext = Path(file.filename or "shot.png").suffix.lower()
    if ext not in _DOC_EXT:
        raise HTTPException(400, f"Unsupported file type '{ext}'. Use images {sorted(_IMAGE_EXT)}, .pdf, or .eml")
    data = await file.read()
    _log.info("POST /analyze/image file=%s ext=%s bytes=%d", file.filename, ext, len(data))

    transcript = ""
    description = ""
    source_label = "Content extracted"
    email_auth = None

    if ext == ".pdf":
        text, page_png = await run_in_threadpool(pdf_to_text_or_image, data)
        if text and len(text) >= 40:
            transcript = text
            source_label = "PDF text extracted"
        elif page_png:
            vision, used_vision = await run_in_threadpool(describe_image, page_png, "image/png")
            if not used_vision:
                raise HTTPException(503, _vision_unconfigured_msg(vision))
            transcript = (vision.get("transcript") or "").strip()
            description = (vision.get("description") or "").strip()
            source_label = "Scanned PDF read by vision model"
    elif ext == ".eml":
        eml_data = await run_in_threadpool(parse_eml, data)
        email_auth = eml_data.get("auth_results", {})
        from_addr = eml_data.get("from_addr", "")
        subject = eml_data.get("subject", "")
        body = eml_data.get("body", "")
        urls = eml_data.get("urls", [])

        headers_text = f"From: {from_addr}\nSubject: {subject}\n"
        if email_auth.get("dkim_pass"):
            headers_text += "DKIM: PASS\n"
        if email_auth.get("spf_pass"):
            headers_text += "SPF: PASS\n"
        if email_auth.get("dmarc_pass"):
            headers_text += "DMARC: PASS\n"

        transcript = headers_text + "\n" + body
        if urls:
            transcript += "\n\nURLs found:\n" + "\n".join(urls)
        description = f"From: {from_addr} | Subject: {subject} | Auth: {'✓' if email_auth.get('dkim_pass') else '✗'}"
        source_label = ".eml parsed with DKIM/SPF/DMARC headers"
    else:
        vision, used_vision = await run_in_threadpool(describe_image, data, _MIME.get(ext, "image/png"))
        if not used_vision:
            raise HTTPException(503, _vision_unconfigured_msg(vision))
        transcript = (vision.get("transcript") or "").strip()
        description = (vision.get("description") or "").strip()
        source_label = "Screenshot analyzed by vision model"

    combined = "\n".join(p for p in [context, transcript] if p)
    if not combined.strip():
        raise HTTPException(422, "No readable text found in the file.")

    req = build_request(text=combined, claimed_source=claimed_source, original_filename=file.filename)

    if email_auth and (email_auth.get("dkim_pass") or email_auth.get("spf_pass")):
        if not req.claimed_source and eml_data.get("from_addr"):
            req.claimed_source = eml_data.get("from_addr", "")

    result = await run_in_threadpool(analyze, req)

    evidence_items = []
    evidence_items.append(Evidence(
        source="file", label=source_label,
        detail=(description or "Extracted text from upload") + f" · text: {transcript[:180]}",
        weight=0.0, severity="info"))

    if email_auth:
        auth_detail = (f"DKIM: {'PASS' if email_auth.get('dkim_pass') else 'FAIL'}, "
                       f"SPF: {'PASS' if email_auth.get('spf_pass') else 'FAIL'}, "
                       f"DMARC: {'PASS' if email_auth.get('dmarc_pass') else 'FAIL'}")
        evidence_items.append(Evidence(
            source="email_auth", label="Email authentication",
            detail=auth_detail,
            weight=-0.2 if email_auth.get("dkim_pass") else 0.15,
            severity="info" if email_auth.get("dkim_pass") else "medium"))

    result.evidence = evidence_items + result.evidence
    await run_in_threadpool(store.save, result)
    return result


def _vision_unconfigured_msg(vision: dict) -> str:
    return ("Vision model not configured. Set a key for LLM_VISION_MODEL "
            f"(note: {vision.get('_note', 'no vision key')}).")


@router.get("/analysis/{analysis_id}", response_model=AnalysisResult)
async def get_analysis(analysis_id: str) -> AnalysisResult:
    result = await run_in_threadpool(store.get, analysis_id)
    if not result:
        raise HTTPException(404, "Not found")
    return result


@router.get("/recent")
async def recent(limit: int = 25):
    return await run_in_threadpool(store.recent, limit)
