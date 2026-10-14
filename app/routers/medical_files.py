import os
import uuid
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.auth.security import get_current_user
from app.database import get_db
from app.models import Appointment, ConsultationFile

router = APIRouter(tags=["Medical Files"])

MAX_FILE_SIZE = 5 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}

UPLOAD_DIR = Path("uploads") / "medical_files"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def check_appointment_access(appointment, user):
    if user.role == "admin":
        return True

    if (
        user.role == "patient"
        and appointment.patient
        and appointment.patient.user_id == user.id
    ):
        return True

    if (
        user.role == "doctor"
        and appointment.doctor
        and appointment.doctor.user_id == user.id
    ):
        return True

    return False


@router.post("/appointments/{appointment_id}/files")
async def upload_medical_file(
    appointment_id: int,
    file_type: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    appointment = (
        db.query(Appointment)
        .filter(Appointment.id == appointment_id)
        .first()
    )

    if not appointment:
        raise HTTPException(404, "Appointment not found")

    if not check_appointment_access(appointment, current_user):
        raise HTTPException(403, "You cannot access this appointment")

    # Patients may upload lab reports.
    if current_user.role == "patient":
        if file_type != "Lab Report":
            raise HTTPException(
                403,
                "Patients may upload Lab Report files only",
            )

    # Doctors may upload prescriptions and scans.
    elif current_user.role == "doctor":
        if (
            file_type not in {"Prescription", "Scan"}
            or not appointment.doctor
            or appointment.doctor.user_id != current_user.id
        ):
            raise HTTPException(
                403,
                "Doctors may upload Prescription or Scan files for their appointments",
            )

    else:
        raise HTTPException(
            403,
            "Only patients and doctors can upload medical files",
        )

    original_name = Path(file.filename or "").name
    extension = Path(original_name).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            400,
            "Only PDF, JPG, and PNG files are allowed",
        )

    # Read at most 5 MB plus one byte, to detect oversized files.
    contents = await file.read(MAX_FILE_SIZE + 1)

    if not contents:
        raise HTTPException(400, "The uploaded file is empty")

    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(413, "Maximum file size is 5 MB")

    # The stored name is unique; original names never determine storage paths.
    stored_name = f"{uuid.uuid4().hex}{extension}"
    destination = UPLOAD_DIR / stored_name

    try:
        with destination.open("xb") as output:
            output.write(contents)

        record = ConsultationFile(
            appointment_id=appointment_id,
            uploaded_by=current_user.id,
            file_type=file_type,
            original_name=original_name,
            stored_name=stored_name,
            size_kb=max(1, (len(contents) + 1023) // 1024),
        )

        db.add(record)
        db.commit()
        db.refresh(record)

    except Exception:
        db.rollback()
        destination.unlink(missing_ok=True)
        raise HTTPException(
            500,
            "Could not save the uploaded file",
        )
    finally:
        await file.close()

    return {
        "message": "File uploaded successfully",
        "file_id": record.id,
        "original_name": record.original_name,
        "file_type": record.file_type,
        "size_kb": record.size_kb,
    }


@router.get("/appointments/{appointment_id}/files")
async def list_appointment_files(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    appointment = (
        db.query(Appointment)
        .filter(Appointment.id == appointment_id)
        .first()
    )

    if not appointment:
        raise HTTPException(404, "Appointment not found")

    if not check_appointment_access(appointment, current_user):
        raise HTTPException(403, "You cannot view these files")

    records = (
        db.query(ConsultationFile)
        .filter(ConsultationFile.appointment_id == appointment_id)
        .order_by(ConsultationFile.id.desc())
        .all()
    )

    return [
        {
            "id": record.id,
            "appointment_id": record.appointment_id,
            "uploaded_by": record.uploaded_by,
            "file_type": record.file_type,
            "original_name": record.original_name,
            "size_kb": record.size_kb,
        }
        for record in records
    ]


@router.get("/files/{file_id}/download")
async def download_medical_file(
    file_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    record = (
        db.query(ConsultationFile)
        .filter(ConsultationFile.id == file_id)
        .first()
    )

    if not record:
        raise HTTPException(404, "File record not found")

    appointment = (
        db.query(Appointment)
        .filter(Appointment.id == record.appointment_id)
        .first()
    )

    if not appointment:
        raise HTTPException(404, "Appointment not found")

    if not check_appointment_access(appointment, current_user):
        raise HTTPException(403, "You cannot download this file")

    # Resolve the generated filename within the storage directory.
    base_dir = UPLOAD_DIR.resolve()
    stored_path = (base_dir / record.stored_name).resolve()

    if stored_path.parent != base_dir or not stored_path.is_file():
        raise HTTPException(404, "Stored file not found")

    return FileResponse(
        path=stored_path,
        filename=record.original_name,
        media_type="application/octet-stream",
    )