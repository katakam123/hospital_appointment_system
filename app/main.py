
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.routers.auth import router as auth_router
from app.routers.departments import router as departments_router
from app.routers.doctors import router as doctors_router
from app.routers.schedules import router as schedules_router
from app.routers.consultations import router as consultations_router
from app.routers.medical_files import router as medical_files_router
from app.routers.patient_history import router as patient_history_router
from app.routers.websockets import router as websockets_router
from app.routers.doctor_queue import router as doctor_queue_router
from app.routers import reports
from app.routers import doctor_feedback


app = FastAPI(
    title="Hospital Appointment Booking System",
    description="Hospital management and appointment booking API",
    version="1.0.0",
)


# Register API routers
app.include_router(auth_router)
app.include_router(departments_router)
app.include_router(doctors_router)
app.include_router(schedules_router)
app.include_router(consultations_router)
app.include_router(medical_files_router)
app.include_router(patient_history_router)
app.include_router(websockets_router)
app.include_router(doctor_queue_router)
app.include_router(reports.router)
app.include_router(doctor_feedback.router)


@app.get("/")
async def home():
    return {
        "message": "Hospital Appointment Booking System API is running"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/queue-test", include_in_schema=False)
def queue_test_page():
    html_path = (
        Path(__file__).resolve().parent.parent
        / "static"
        / "queue_test.html"
    )
    return FileResponse(html_path)
