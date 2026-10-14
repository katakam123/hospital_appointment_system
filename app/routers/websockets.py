
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.auth.security import decode_token
from app.database import SessionLocal
from app.models import User, Doctor, Appointment
from app.services.websocket_manager import manager
from app.services.live_queue_service import build_queue_snapshot

router = APIRouter(tags=["WebSockets"])


def get_websocket_user(token: str, db: Session):
    payload = decode_token(token)

    if not payload or payload.get("type") != "access":
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    try:
        user_id = int(user_id)
    except (ValueError, TypeError):
        return None

    user = db.query(User).filter(User.id == user_id).first()

    if not user or not getattr(user, "is_active", True):
        return None

    return user


@router.websocket("/ws/queue/{doctor_id}")
async def doctor_live_queue(websocket: WebSocket, doctor_id: int, token: str):
    db = SessionLocal()
    user = None

    try:
        try:
            user = get_websocket_user(token, db)
        except Exception:
            user = None

        if user is None:
            await websocket.close(code=1008, reason="Invalid access token")
            return

        role = str(user.role).lower()

        # Patients may only connect to the queue of their own doctor appointment.
        if role == "patient":
            has_appointment = (
                db.query(Appointment)
                .filter(
                    Appointment.doctor_id == doctor_id,
                    Appointment.patient.has(user_id=user.id),
                    Appointment.appointment_date
                    == __import__("datetime").date.today(),
                )
                .first()
            )

            if not has_appointment:
                await websocket.close(
                    code=1008,
                    reason="Not authorized for this doctor's queue",
                )
                return

        elif role == "doctor":
            doctor = (
                db.query(Doctor)
                .filter(
                    Doctor.id == doctor_id,
                    Doctor.user_id == user.id,
                )
                .first()
            )
            if not doctor:
                await websocket.close(
                    code=1008,
                    reason="Not authorized for this doctor's queue",
                )
                return

        elif role != "admin":
            await websocket.close(code=1008, reason="Access denied")
            return

        await manager.connect_queue(doctor_id, websocket)
        await websocket.send_json(build_queue_snapshot(db, doctor_id))

        while True:
            # Keep the connection alive; the client can send "ping".
            await websocket.receive_text()

    except WebSocketDisconnect:
        pass
    except Exception:
        try:
            await websocket.close(code=1011, reason="WebSocket error")
        except Exception:
            pass
    finally:
        await manager.disconnect_queue(doctor_id, websocket)
        db.close()


@router.websocket("/ws/notifications")
async def personal_notifications(websocket: WebSocket, token: str):
    db = SessionLocal()
    user = None

    try:
        try:
            user = get_websocket_user(token, db)
        except Exception:
            user = None

        if user is None:
            await websocket.close(code=1008, reason="Invalid access token")
            return

        await manager.connect_user(user.id, websocket)

        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        pass
    except Exception:
        try:
            await websocket.close(code=1011, reason="WebSocket error")
        except Exception:
            pass
    finally:
        if user is not None:
            await manager.disconnect_user(user.id, websocket)
        db.close()
