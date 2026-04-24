# Virtual Internship Hub

AI-supported platform for freelancing careers: role-based auth, skill assessment, and domain recommendation.

## Prerequisites

- **Python 3.12.6** — [Download](https://www.python.org/downloads/)
- **PostgreSQL 17** — [Download](https://www.postgresql.org/download/)
- Node.js 16+
- pip, npm or yarn

## Backend setup

All commands from the **backend** directory with venv activated.

1. **Virtual environment and install**
   ```bash
   cd backend
   python -m venv venv
   ```
   - Windows: `venv\Scripts\activate` · Linux/Mac: `source venv/bin/activate`
   ```bash
   pip install -r requirements.txt
   ```

2. **PostgreSQL** — Create database (psql or pgAdmin):
   ```sql
   CREATE DATABASE virtual_internship_hub;
   ```

3. **Environment** — Create `backend/.env`:
   ```env
   SECRET_KEY=your-secret-key
   DEBUG=True
   DB_NAME=virtual_internship_hub
   DB_USER=postgres
   DB_PASSWORD=1234
   DB_HOST=localhost
   DB_PORT=5432

   EMAIL_HOST_USER=davinciuser702@gmail.com
   EMAIL_HOST_PASSWORD=mfso tfau nmix mwbt
   ```
   Set `EMAIL_HOST_PASSWORD` to your app password if using email (e.g. forgot-password).

4. **Migrations**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

5. **Load data and create admin**
   - **Domains** (required): `backend/accounts/management/commands/populate_domains.py`
     ```bash
     python manage.py populate_domains
     ```
   - **App admin** (frontend dashboard; not Django /admin/): `backend/accounts/management/commands/create_admin.py`
     ```bash
     python manage.py create_admin
     ```
     Prompts for email, username, password. Optional: `python manage.py createsuperuser` for Django admin site.
   - **Assessment questions** (optional): place `domain_questions.json` in `backend/data/`, then:
     ```bash
     python manage.py load_domain_questions
     ```

6. **Run backend**
   ```bash
   python manage.py runserver
   ```
   API: **http://localhost:8000** · Swagger: `/swagger/` · ReDoc: `/redoc/`  
   **Full API list and flows:** [backend/README.md](backend/README.md)

| Action           | Command |
|------------------|--------|
| Run backend      | `python manage.py runserver` |
| Load domains     | `python manage.py populate_domains` |
| Create app admin| `python manage.py create_admin` |
| Load questions   | `python manage.py load_domain_questions` |

## Frontend setup

```bash
cd frontend
npm install
npm start
```

App: **http://localhost:3000**
