
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Department, Doctor
from app.auth.security import get_current_user, require_roles
from app.schemas.department import (
    DepartmentCreate,
    DepartmentUpdate,
    DepartmentResponse,
)

router = APIRouter(prefix="/departments", tags=["Departments"])

admin_only = require_roles("admin")


@router.post(
    "",
    response_model=DepartmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_department(
    request: DepartmentCreate,
    db: Session = Depends(get_db),
    current_user=Depends(admin_only),
):
    name = request.name.strip()

    if not name:
        raise HTTPException(status_code=400, detail="Department name cannot be empty")

    existing = db.query(Department).filter(
        Department.name == name
    ).first()

    if existing:
        raise HTTPException(status_code=409, detail="Department already exists")

    department = Department(
        name=name,
        description=request.description,
        is_active=True,
    )

    db.add(department)
    db.commit()
    db.refresh(department)

    return department


@router.get("", response_model=list[DepartmentResponse])
def get_departments(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return (
        db.query(Department)
        .filter(Department.is_active.is_(True))
        .order_by(Department.name)
        .all()
    )


@router.put(
    "/{department_id}",
    response_model=DepartmentResponse,
)
def update_department(
    department_id: int,
    request: DepartmentUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(admin_only),
):
    department = db.query(Department).filter(
        Department.id == department_id
    ).first()

    if not department:
        raise HTTPException(status_code=404, detail="Department not found")

    updates = request.model_dump(exclude_unset=True)

    if "name" in updates and updates["name"] is not None:
        updates["name"] = updates["name"].strip()

        if not updates["name"]:
            raise HTTPException(status_code=400, detail="Department name cannot be empty")

        duplicate = db.query(Department).filter(
            Department.name == updates["name"],
            Department.id != department_id,
        ).first()

        if duplicate:
            raise HTTPException(status_code=409, detail="Department name already exists")

    # Do not deactivate a department that has active doctors.
    if updates.get("is_active") is False:
        active_doctor = db.query(Doctor).filter(
            Doctor.department_id == department_id,
            Doctor.is_active.is_(True),
        ).first()

        if active_doctor:
            raise HTTPException(
                status_code=409,
                detail="Cannot deactivate a department with active doctors",
            )

    for field, value in updates.items():
        setattr(department, field, value)

    db.commit()
    db.refresh(department)

    return department


@router.delete("/{department_id}")
def delete_department(
    department_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(admin_only),
):
    department = db.query(Department).filter(
        Department.id == department_id
    ).first()

    if not department:
        raise HTTPException(status_code=404, detail="Department not found")

    active_doctor = db.query(Doctor).filter(
        Doctor.department_id == department_id,
        Doctor.is_active.is_(True),
    ).first()

    if active_doctor:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete a department with active doctors",
        )

    db.delete(department)
    db.commit()

    return {"message": "Department deleted successfully"}
