# Hospital Appointment Management System

A backend application built with **FastAPI** for managing hospital appointments and related healthcare workflows. This repository is intended as a learning/project implementation; verify each endpoint and feature against the current source code before using it in production.

## Contents

- [Features](#features)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Requirements](#requirements)
- [Setup and Installation](#setup-and-installation)
- [Environment Configuration](#environment-configuration)
- [Run the Application](#run-the-application)
- [API Documentation](#api-documentation)
- [Database Migrations](#database-migrations)
- [Testing](#testing)
- [GitHub Workflow](#github-workflow)
- [Security Notes](#security-notes)
- [Troubleshooting](#troubleshooting)

## Features

The project structure and available routers may include the following areas. Confirm implementation status in the source code and Swagger docs:

- User authentication and current-user endpoints
- Role-based access patterns for hospital users
- Departments and doctors
- Patient records
- Doctor schedules and leave management
- Appointment booking and appointment status/history
- Consultation records and files
- Doctor feedback
- Database persistence with SQLAlchemy
- Database schema migrations with Alembic

## Technology Stack

- **Python** 3.9+
- **FastAPI** — REST API framework
- **Pydantic** — request and response validation
- **SQLAlchemy** — ORM/database access
- **MySQL** — relational database (if configured in your environment)
- **Alembic** — database migrations
- **Uvicorn** — ASGI development server
- **Pytest** — tests, if configured

> Check `requirements.txt`, `app/config.py`, and `alembic/env.py` for the exact versions and configuration used by your copy of the project.

## Project Structure

```text
hospital_appointment_system/
├── app/
│   ├── main.py
│   ├── database.py
│   ├── models/
│   ├── schemas/
│   ├── routers/
│   ├── services/
│   ├── auth/
│   └── utils/
├── alembic/
├── static/
├── .env.example
├── .gitignore
├── alembic.ini
├── requirements.txt
└── README.md
```

Some folders or modules may differ depending on the current version of the project.

## Requirements

Install the following before starting:

- Python 3.9 or later
- Git
- MySQL Server, if the application is configured to use MySQL
- Visual Studio Code (recommended)

Check your Python installation:

```powershell
python --version
```

## Setup and Installation

### 1. Clone the repository

```powershell
git clone https://github.com/katakam123/hospital_appointment_system.git
cd hospital_appointment_system
```

### 2. Create a virtual environment

```powershell
python -m venv .venv
```

### 3. Activate the virtual environment (Windows PowerShell)

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, you can run the following for the current terminal session, if permitted by your device policy:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### 4. Install dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Environment Configuration

1. Copy `.env.example` to a new file named `.env`.
2. Fill in values appropriate for your local machine.
3. Keep `.env` private; do not commit it to GitHub.

Example configuration (the variable names must match those read by your application's settings/configuration module):

```env
DATABASE_URL=mysql+pymysql://DB_USER:DB_PASSWORD@localhost:3306/hospital_appointment_db
SECRET_KEY=replace_with_a_long_random_secret
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

The example above is illustrative. Use the database driver and environment variable names expected by your actual code. If your MySQL password contains URL-reserved characters, URL-encode the password in the database URL or construct the URL using SQLAlchemy's URL utilities.

Create the database in MySQL if your application does not create it automatically. For example:

```sql
CREATE DATABASE hospital_appointment_db;
```

Do not use the example secret or credentials in a real deployment.

## Run the Application

From the project root, with the virtual environment active:

```powershell
python -m uvicorn app.main:app --reload
```

If startup succeeds, the API is typically available at:

- API root: `http://127.0.0.1:8000/`
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

The root endpoint and available routes depend on your implementation.

## API Documentation

Open Swagger UI:

```text
http://127.0.0.1:8000/docs
```

Use it to inspect the routes, schemas, response codes, and authentication requirements currently registered by the application.

For protected endpoints, first authenticate using the mechanism configured by your app. Do not assume a default administrator account exists; use the project's approved user/admin creation process.

## Database Migrations

If Alembic is configured, review your database URL and model imports before running migrations.

Check the current migration state:

```powershell
alembic current
alembic history
```

Create a migration after model changes:

```powershell
alembic revision --autogenerate -m "describe your schema change"
```

Review the generated migration file before applying it. Then run:

```powershell
alembic upgrade head
```

If the `alembic` command is not found, try:

```powershell
python -m alembic current
```

Do not run migrations against a database containing important data until you have reviewed the migration and made a backup.

## Testing

If tests are included in the repository, run:

```powershell
python -m pytest
```

To run tests with more detailed output:

```powershell
python -m pytest -v
```

If Pytest is not installed, check `requirements.txt` and install the project's development dependencies.

## GitHub Workflow

After changing code, review what will be committed:

```powershell
git status
git diff
```

Then commit and push:

```powershell
git add .
git commit -m "Describe your changes"
git push
```

Ensure `.env`, virtual environments, cache folders, and other local secrets are excluded by `.gitignore`.

## Security Notes

- Never commit `.env`, database passwords, API keys, access tokens, or real patient information.
- Use a strong, randomly generated secret key outside development.
- Use HTTPS and secure deployment settings in production.
- Enforce authentication and authorization on protected endpoints.
- Validate inputs and avoid returning sensitive data in API responses or logs.
- Back up the database and review migrations before applying them.
- This project should not be used to handle real patient data until security, privacy, access controls, auditing, and applicable healthcare requirements have been reviewed.

## Troubleshooting

### `ModuleNotFoundError`

Make sure the virtual environment is activated and install dependencies:

```powershell
python -m pip install -r requirements.txt
```

### Database connection error

- Confirm MySQL is running.
- Confirm the database exists.
- Check the host, port, username, password, and driver in `.env`.
- Ensure the variable names match your app configuration.

### `alembic` command not found

```powershell
python -m alembic current
```

### Port 8000 is already in use

Run the application on another port:

```powershell
python -m uvicorn app.main:app --reload --port 8001
```

Then open `http://127.0.0.1:8001/docs`.

## License

No license has been specified yet. Add a `LICENSE` file if you intend to publish this project for reuse.
