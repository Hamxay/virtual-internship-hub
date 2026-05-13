# Virtual Internship Hub

To-the-point setup guide for both local (without Docker) and Docker.

For detailed API docs, see `backend/README.md`.

---

## 1) Setup without Docker (local)

### Prerequisites
- Python 3.12+
- PostgreSQL
- Node.js 18+ and npm
- Redis (required for Celery + WebSockets)

### A. Backend
```bash
cd backend
python -m venv venv
```

- Windows (PowerShell):
  ```bash
  .\venv\Scripts\Activate.ps1
  ```
- Linux/macOS:
  ```bash
  source venv/bin/activate
  ```

Install packages:
```bash
pip install -r requirements.txt
```

Create database in PostgreSQL:
```sql
CREATE DATABASE virtual_internship_hub;
```

Create env file:
- Copy `backend/.env.example` to `backend/.env`
- Fill DB, JWT, email, OpenRouter, and optional Copyleaks values.

Run migrations:
```bash
python manage.py migrate
```

Initial data/setup:
```bash
python manage.py populate_domains
python manage.py load_project_templates_json --file projects/data/project_templates_five_domains.json
python manage.py load_domain_questions
python manage.py create_admin
```

Run backend (ASGI for WebSockets):
```bash
daphne -b 0.0.0.0 -p 8000 config.asgi:application
```

Run Celery worker (new terminal, still in `backend` with venv active):
```bash
celery -A config worker -l info
```

### B. Frontend
```bash
cd frontend
npm install
npm start
```

### Local URLs
- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000/api`
- Swagger: `http://localhost:8000/swagger/`
- ReDoc: `http://localhost:8000/redoc/`

---

## 2) Setup with Docker

### Prerequisites
- Docker Desktop
- Docker Compose

### Steps
From project root:
```bash
docker compose build
docker compose up -d
```

### Environment files (Docker)

Create `.env` files from examples on host machine:
```bash
copy backend\.env.example backend\.env
copy frontend\.env.example frontend\.env
```

Open and edit them in your editor (recommended from host):
```bash
code backend\.env
code frontend\.env
```

Access running containers:
```bash
docker compose exec backend sh
docker compose exec frontend sh
```

Check env files inside containers:
```bash
docker compose exec backend sh -c "ls -la /app && printenv | sort"
docker compose exec frontend sh -c "ls -la /app && printenv | sort"
```

If you update `.env` or `.env.example`, rebuild/restart:
```bash
docker compose up -d --build backend frontend celery
```

Update `.env.example` templates (host side) to keep team defaults in sync:
```bash
code backend\.env.example
code frontend\.env.example
```

Check running services:
```bash
docker compose ps
```

View logs:
```bash
docker compose logs -f backend
docker compose logs -f celery
```

If you need to run migrations manually:
```bash
docker compose exec backend python manage.py migrate
```

Initial data/setup (inside backend container):
```bash
docker compose exec backend python manage.py populate_domains
docker compose exec backend python manage.py load_project_templates_json --file projects/data/project_templates_five_domains.json
docker compose exec backend python manage.py load_domain_questions
docker compose exec backend python manage.py create_admin
```

Stop:
```bash
docker compose down
```

Stop + remove volumes (full reset):
```bash
docker compose down -v
```

---

## 3) Command Cheat Sheet (custom commands)

Run from `backend/` (local) or with `docker compose exec backend` (Docker).

### Core
```bash
python manage.py populate_domains
python manage.py create_admin
python manage.py load_domain_questions
python manage.py load_project_templates_json --file projects/data/project_templates_five_domains.json
```

Docker equivalents:
```bash
docker compose exec backend python manage.py populate_domains
docker compose exec backend python manage.py create_admin
docker compose exec backend python manage.py load_domain_questions
docker compose exec backend python manage.py load_project_templates_json --file projects/data/project_templates_five_domains.json
```

### Student history generators
```bash
python manage.py generate_student_history
python manage.py generate_student_history --file "path/to/student_data.csv"

python manage.py generate_random_student_history
python manage.py generate_random_student_history --students 10 --projects-per-domain 3 --password "Student@123"
```

Docker equivalents:
```bash
docker compose exec backend python manage.py generate_student_history
docker compose exec backend python manage.py generate_student_history --file "path/to/student_data.csv"

docker compose exec backend python manage.py generate_random_student_history
docker compose exec backend python manage.py generate_random_student_history --students 10 --projects-per-domain 3 --password "Student@123"
```

### Common Django
```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Docker equivalents:
```bash
docker compose exec backend python manage.py makemigrations
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py createsuperuser
```

---

## 4) Notes

- Backend container command already runs migrations and starts ASGI server in Docker.
- WebSockets/notifications require ASGI (`daphne`) and Redis.
- Celery must be running for async submission evaluation.
