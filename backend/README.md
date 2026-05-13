# Virtual Internship Hub — Backend

Django REST API. Base URL (local): **`http://localhost:8000`**. JSON API under **`/api/`** (except paths noted below).

## Authentication

| Item | Detail |
|------|--------|
| **Mechanism** | JWT (`Authorization: Bearer <access>`) |
| **Login** | `POST /api/auth/login/` → returns `access`, `refresh` |
| **Refresh** | `POST /api/auth/token/refresh/` with body `{ "refresh": "<refresh_token>" }` |
| **Logout** | `POST /api/auth/logout/` (authenticated; blacklists refresh if configured) |
| **Default** | `REST_FRAMEWORK` defaults to `IsAuthenticated` unless a view sets `AllowAny` |

**Role checks:** `STUDENT` / `MENTOR` / `ADMINISTRATOR` come from `accounts.User.role`. Some admin UI APIs use **`IsAdministrator`** (role). **Reports** admin analytics/export use **`IsAdminUser`** (Django **`user.is_staff`** is usually required—align staff flags with who should call those endpoints).

---

## URL map (how routes are mounted)

| Mount in `config/urls.py` | App routes |
|---------------------------|------------|
| `path('api/', include('accounts.urls'))` | Accounts (below) |
| `path('api/', include('assessments.urls'))` | Assessments |
| `path('api/', include('projects.urls'))` | Projects |
| `path('api/mentor/', include('mentor.urls'))` | Mentor (**prefix `/api/mentor/`**) |
| `path('api/portfolio/', include('portfolio.urls'))` | Portfolio (**prefix `/api/portfolio/`**) |
| `path('api/', include('chat.urls'))` | Chat |
| `path('api/reports/', include('reports.urls'))` | Reports |
| `path('api/admin/reports/', include('reports.urls'))` | Same reports routes (duplicate prefix for admin clients) |

Full path = base + table path (e.g. `GET http://localhost:8000/api/auth/profile/`).

---

## API reference (method → path → who → what)

### Auth & registration (`accounts`)

| Method | Path | Permission | Purpose |
|--------|------|------------|---------|
| POST | `/api/auth/register/send-otp/` | AllowAny | Start signup; send OTP to email |
| POST | `/api/auth/register/verify/` | AllowAny | Verify OTP + create user |
| POST | `/api/auth/login/` | AllowAny | JWT login |
| POST | `/api/auth/logout/` | Authenticated | Logout / blacklist refresh |
| POST | `/api/auth/token/refresh/` | AllowAny (refresh body) | New access token |
| POST | `/api/auth/forgot-password/send-otp/` | AllowAny | Password reset OTP |
| POST | `/api/auth/forgot-password/verify-otp/` | AllowAny | Check OTP |
| POST | `/api/auth/forgot-password/reset/` | AllowAny | Set new password |
| POST | `/api/auth/forgot-password/resend-otp/` | AllowAny | Resend reset OTP |
| GET, PUT, PATCH | `/api/auth/profile/` | Authenticated | Current user (any role) |

### Students & mentors (directory + profiles)

| Method | Path | Permission | Purpose |
|--------|------|------------|---------|
| GET, PUT, PATCH | `/api/students/profile/` | Authenticated (**student only** in handlers) | Student profile + target domains |
| GET | `/api/students/` | Authenticated | **Admin:** all students · **Mentor:** students whose target domains include mentor expertise · **Student:** empty |
| GET, PUT, PATCH | `/api/mentors/profile/` | Authenticated (**mentor only** in handlers) | Mentor profile + expertise domain |
| GET | `/api/mentors/` | Authenticated | **Student:** available mentors · **Others:** all mentor profiles |

### Domains

| Method | Path | Permission | Purpose |
|--------|------|------------|---------|
| GET | `/api/domains/` | **AllowAny** | List domains (no JWT) |
| GET, POST | `/api/admin/domains/` | Authenticated + **Administrator** | Paginated list / create |
| GET, PUT, PATCH, DELETE | `/api/admin/domains/<pk>/` | Authenticated + **Administrator** | One domain CRUD |

### Admin users (`accounts`)

| Method | Path | Permission | Purpose |
|--------|------|------------|---------|
| POST | `/api/admin/administrators/` | Authenticated + **Superuser** | Create another admin user |
| GET | `/api/admin/users/students/` | Authenticated + **Administrator** | Paginated student list |
| GET | `/api/admin/users/mentors/` | Authenticated + **Administrator** | Paginated mentor list |

### Assessments (`assessments`)

| Method | Path | Permission | Purpose |
|--------|------|------------|---------|
| GET | `/api/admin/domains/question-counts/` | Administrator | Question counts per domain |
| GET, POST | `/api/admin/domains/<domain_id>/questions/` | Administrator | List / create MCQs (paginated) |
| GET, PUT, PATCH, DELETE | `/api/admin/domains/<domain_id>/questions/<pk>/` | Administrator | One question |
| GET | `/api/student/assessments/composed/` | Student | Build composed quiz (needs 2–3 target domains; daily attempt cap) |
| POST | `/api/student/assessments/composed/submit/` | Student | Submit answers → score, attempt row, recommendations |
| GET | `/api/student/attempts/` | Student | List own past attempts |

**Typical student assessment flow:** ensure profile has **2–3 target domains** → `GET composed` (receives `submission_token` + questions) → `POST submit` with answers → optional `GET attempts` history.

### Projects (`projects`)

| Method | Path | Permission | Purpose |
|--------|------|------------|---------|
| GET, POST | `/api/admin/project-templates/` | Administrator | List / create templates (+ nested instruction/rubric in serializer) |
| GET, PUT, PATCH, DELETE | `/api/admin/project-templates/<pk>/` | Administrator | One template |
| POST | `/api/admin/projects/assign/` | Administrator | Assign template to student → `IN_PROGRESS` assignment |
| GET | `/api/admin/submissions/pending/` | Administrator | Submissions in `SUBMITTED` / `FLAGGED` |
| GET | `/api/admin/evaluations/summary/` | Administrator | Aggregate stats (counts, averages) |
| GET | `/api/student/projects/recommended/` | Student | Refreshes recommendations; returns `content_based` + `collaborative` recommended assignments |
| GET | `/api/student/assignments/` | Student | Own assignments + submissions + evaluations |
| GET | `/api/student/assignments/progress/` | Student | Recompute/return progress snapshot |
| POST | `/api/student/projects/<pk>/accept/` | Student | Accept recommended assignment `pk` → `IN_PROGRESS` |
| POST | `/api/student/assignments/<pk>/submissions/` | Student | Create submission (multipart/JSON); sets assignment `SUBMITTED`; **queues async evaluation** (Celery) |
| GET | `/api/student/submissions/<pk>/feedback/` | Student | One submission + evaluations (own only) |

**Typical student project flow:** `GET recommended` → `POST accept` with assignment id → `POST submissions` on that assignment id → poll `GET feedback` on submission id until evaluations exist → if mentor path, mentor completes review → assignment may become `COMPLETED`.

### Mentor (`mentor`) — prefix `/api/mentor/`

| Method | Path | Permission | Purpose |
|--------|------|------------|---------|
| GET | `/api/mentor/queue/` | Authenticated + **IsMentor** | Submissions needing review in mentor’s **expertise domain** (FCFS among mentors in domain) |
| POST, PATCH | `/api/mentor/reviews/` | Authenticated + **IsMentor** | Submit review (approve → completed, or needs revision); sets evaluation **`reviewed_by`**, `is_human_reviewed`, mentor feedback |

**Typical mentor flow:** set **expertise domain** on mentor profile → `GET queue` → `POST` or `PATCH reviews` with `submission_id`, `approved`, `mentor_feedback`.

### Portfolio (`portfolio`) — prefix `/api/portfolio/`

| Method | Path | Permission | Purpose |
|--------|------|------------|---------|
| GET | `/api/portfolio/<username>/` | **AllowAny** | Public profile + top completed, human-reviewed projects |

### Chat (`chat`)

| Method | Path | Permission | Purpose |
|--------|------|------------|---------|
| GET | `/api/chat/sessions/` | Student | List own chat sessions |
| POST | `/api/chat/message/` | Student | Send message; optional `session_id` (creates session if omitted); returns assistant reply |
| GET | `/api/chat/sessions/<session_id>/messages/` | Student | Messages for that session (chronological) |

### Reports (`reports`) — under **`/api/reports/`** and **`/api/admin/reports/`** (same paths)

| Method | Path | Permission | Purpose |
|--------|------|------------|---------|
| GET | `.../analytics/` | **IsAdminUser** (staff) | FR9-style JSON: KPIs, clusters, platform skill progress |
| GET | `.../export/` | **IsAdminUser** | Streaming CSV audit (completed assignments) |
| GET | `.../student/me/` | Authenticated + **role STUDENT** | Personal baseline, project average, skill delta %, time series |
| GET | `.../mentor/cohort/` | Authenticated + **role MENTOR** | Cohort avg score, at-risk count, top 3 students (from submissions **human-reviewed** by this mentor via **`SubmissionEvaluation.reviewed_by`**) |

---

## Other endpoints

| Path | Purpose |
|------|---------|
| `/admin/` | Django admin (Jazzmin) |
| `/api/schema/` | OpenAPI schema |
| `/swagger/`, `/redoc/` | API docs UI |

---

## Cross-cutting flows (end-to-end)

1. **Signup:** `send-otp` → `verify` (creates user + profile) → optional `login`.
2. **Student onboarding:** `students/profile` (domains) → `composed` GET → `composed/submit` POST → `student/projects/recommended` GET → `accept` POST → `assignments/<id>/submissions` POST → `submissions/<id>/feedback` GET.
3. **Mentor review:** profile domain → `mentor/queue` GET → `mentor/reviews` POST/PATCH (domain on submission must match).
4. **Admin operations:** `admin/domains`, `admin/project-templates`, `admin/projects/assign`, `admin/submissions/pending`, assessment questions under `admin/domains/<id>/questions/`.
5. **Analytics:** staff user → `reports/analytics` + `reports/export`; student → `reports/student/me`; mentor → `reports/mentor/cohort`.

---

## Celery

Async tasks (e.g. **`async_evaluate_submission`**) require a worker:

```bash
celery -A config worker -l info
```

---

## Libraries & stack (from `requirements.txt` + stdlib)

| Library | Role in this project |
|---------|----------------------|
| **Django** | ORM, admin, routing, auth user model hook |
| **djangorestframework** | `APIView`, generics, serializers, permissions, pagination |
| **djangorestframework-simplejwt** | Access/refresh JWT, blacklist on logout/rotation |
| **django-cors-headers** | Browser CORS for the React origin |
| **psycopg2-binary** | PostgreSQL driver |
| **python-decouple** | `settings.py` reads `SECRET_KEY`, DB, Celery, and OpenRouter settings from `.env` |
| **Pillow** | Image handling where uploads need validation/thumbnails |
| **drf-spectacular** | OpenAPI schema + Swagger/ReDoc |
| **django-jazzmin** | Themed Django `/admin/` UI |
| **scikit-learn** | TF–IDF + cosine similarity (evaluation heuristics, hybrid recommender); **KMeans** in `reports` |
| **pandas** | DataFrames for student cluster matrix in `reports` |
| **scikit-surprise** | **SVD** collaborative filtering in `hybrid_recommender` (when enough ratings) |
| **joblib** | Typical sklearn companion (serialization / parallelism if used) |
| **nltk** | Tokenization for text features in evaluation (with regex fallback if import fails) |
| **celery** + **redis** | Async task broker/result (`async_evaluate_submission`); broker URL in settings |
| **python-docx** / **openpyxl** | Extract text/tables from student `.docx` / Excel uploads for prompts |
| **requests** | HTTP to **OpenRouter** for career coach chat and FR4 project evaluation |

**Not always in `requirements.txt` but used in code paths:** standard library (`json`, `re`, `logging`, `pathlib`, `statistics`, etc.).

---

## Internal “services” (where business logic lives)

Logic is **not** only in views: heavy work is split into modules below. Views validate auth, deserialize input, then call services/tasks.

| Module / package | Responsibility | Used by (typical) |
|------------------|------------------|-------------------|
| **`projects/services/evaluation.py`** | FR4 pipeline: build submission bundle, local TF-IDF plagiarism check, gatekeepers (empty / Python syntax), **OpenRouter** JSON eval, write **`SubmissionEvaluation`**, update assignment / snapshot | `evaluate_submission_logic()` ← **`projects/tasks.async_evaluate_submission`** (Celery) after student `POST …/submissions/` |
| **`projects/services/evaluation_gatekeepers.py`** | Pre-LLM checks: empty bundle, Python ``ast`` syntax for CODE | `evaluation.py` |
| **`projects/services/extractor.py`** | Typed extraction result for gatekeepers / bundle | `evaluation.py` |
| **`projects/utils/code_flattener.py`** | GitHub repo → text bundle for prompts | `evaluation.py` |
| **`projects/utils/document_extractor.py`** | Local file → markdown text / binary artifact note (PDF/images) and text extraction for docx/xlsx/csv | `evaluation.py` |
| **`projects/utils/prompt_builder.py`** | Build evaluation prompt for the model | `evaluation.py` |
| **`projects/services/recommendation.py`** | **`update_student_progress_snapshot`**, **`refresh_recommended_assignments`**, **`apply_fr4_recommended_difficulty_if_higher`**, tag union from completed work | Student **recommended** GET; evaluation completion; mentor review completion |
| **`projects/services/hybrid_recommender.py`** | **FR3** dual feed: **content-based** (cold start + TF–IDF on tags vs “successful” tags) and **collaborative** (**Surprise SVD**) when enough completed projects; respects snapshot difficulty bands | `recommendation.refresh_recommended_assignments` |
| **`projects/services/domain_profile.py`** | Domain weights on snapshot / assessment meta keys | `recommendation`, `assessments` sync |
| **`assessments/services.py`** | Composed session, question draw, daily attempt cap, **`compute_composed_score_and_recommend`**, persist **`StudentAssessmentAttempt`**, sync snapshot | `assessments/views` composed GET/POST |
| **`assessments/domain_recommendation/`** | **RandomForest** + rule-based ranking, `build_ml_recommendation_meta` | `assessments/services.py` on submit |
| **`accounts/services/registration.py`** | Signup / profile wiring | `accounts/views` verify flow |
| **`accounts/services/email.py`** | OTP / transactional email | registration + password reset views |
| **`mentor/views.py`** | Queue query + transactional review (no separate `services/` package) | `GET queue`, `POST/PATCH reviews` |
| **`chat/utils.py`** | **`build_career_coach_prompt`**, **`run_career_coach`** → **OpenRouter** `requests.post` | `chat/views` send message |
| **`reports/utils.py`** | **`get_student_clusters`** (pandas + **KMeans**), **`calculate_skill_improvement`**, student/mentor aggregates | `reports/views` |

---

## How the code works (main APIs → services)

### 1) Student submits a project (`POST /api/student/assignments/<pk>/submissions/`)

1. **`StudentSubmissionCreateView`** validates with **`ProjectSubmissionCreateSerializer`**, saves **`ProjectSubmission`**, sets assignment **`SUBMITTED`**.  
2. **`async_evaluate_submission.delay(submission.pk)`** enqueues Celery.  
3. Worker runs **`evaluate_submission_logic(submission_id)`** in **`evaluation.py`**:  
   - Builds text/media bundle (**`UniversalRepositoryFlattener`**, **`UniversalDocumentExtractor`**, notes/text).  
   - Gatekeepers in **`evaluation_gatekeepers`**.  
   - **OpenRouter** JSON rubric response (model from **`OPENROUTER_PROJECT_EVAL_MODEL`**). If the API key is missing or the call fails, a **`openrouter_unavailable`** evaluation is stored. Plagiarism uses a local TF-IDF similarity gate (offline).  
   - Persists **`SubmissionEvaluation`**, updates **assignment** status / **`latest_evaluation_score`**, submission status.  
4. Task **`finally`** runs janitor to delete uploaded file from disk after evaluation.

### 2) Student loads recommendations (`GET /api/student/projects/recommended/`)

1. **`refresh_recommended_assignments(request.user)`** in **`recommendation.py`**.  
2. **`HybridRecommender`** in **`hybrid_recommender.py`** builds **content_based** and **collaborative** candidate lists (sklearn TF–IDF; Surprise SVD when thresholds met).  
3. Serializer returns existing **`StudentProjectAssignment`** rows in groups `content_based` / `collaborative`.

### 3) Student takes skill assessment (`GET/POST …/assessments/composed/`)

1. **`assessments/services.get_composed_questions`** picks MCQs from profile target domains.  
2. **`create_composed_session`** stores allowed question IDs for submit.  
3. **`StudentComposedSubmitView`** → **`compute_composed_score_and_recommend`** → **`assessments/domain_recommendation`** (ML + rules) → creates **`StudentAssessmentAttempt`**, **`sync_assessment_to_snapshot`**.

### 4) Mentor reviews (`/api/mentor/reviews/`)

1. Loads **`ProjectSubmission`** + latest **`SubmissionEvaluation`**.  
2. Writes **`mentor_feedback`**, **`is_human_reviewed=True`**, **`reviewed_by=request.user`**, updates assignment **`COMPLETED`** or **`NEEDS_REVISION`**.  
3. **`update_student_progress_snapshot(assignment.student)`** from **`recommendation.py`**.

### 5) Career coach (`POST /api/chat/message/`)

1. **`build_career_coach_prompt(user)`** pulls domains + completed project titles from ORM.  
2. **`run_career_coach`** → **`requests`** to **OpenRouter** `/chat/completions` using **`OPENROUTER_*`** settings.  
3. Persists **`ChatMessage`** rows.

### 6) Admin analytics / export (`/api/reports/` or `/api/admin/reports/`)

1. **`get_student_clusters`**: ORM → pandas matrix → **KMeans**.  
2. **`calculate_skill_improvement`**: aggregates attempts + completed submission scores.  
3. **`PlatformAuditExportView`**: ORM iterator + **`csv`** → **`StreamingHttpResponse`**.

### 7) Mentor cohort (`GET …/mentor/cohort/`)

1. **`get_mentor_cohort_summary`**: submissions with an evaluation where **`reviewed_by`** is the mentor and **`is_human_reviewed`**, distinct per submission; per-student averages for KPIs.

---

## Environment variables (high-signal)

| Variable | Used for |
|----------|----------|
| `SECRET_KEY`, `DEBUG`, `DB_*` | Django + PostgreSQL |
| `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `CELERY_TASK_ALWAYS_EAGER` | Celery (Redis broker; eager = sync for dev) |
| `OPENROUTER_API_KEY`, `OPENROUTER_PROJECT_EVAL_MODEL`, `OPENROUTER_CHAT_MODEL`, `OPENROUTER_BASE_URL`, `OPENROUTER_HTTP_REFERER`, `OPENROUTER_APP_TITLE` | FR4 project evaluation + FR7 career coach |
| Email `EMAIL_*` | OTP / mail from `accounts` services |

See **`config/settings.py`** for defaults and full list.

---

For OpenAPI details and request/response schemas, use **Swagger** at `/swagger/` or **ReDoc** at `/redoc/`.

---

## FR10: Live notifications (Channels + Redis)

- **Run server with ASGI:** `daphne -b 127.0.0.1 -p 8000 config.asgi:application` (WebSockets are not served by Django’s development WSGI server.)
- **Redis:** `CHANNEL_LAYERS` defaults to `redis://localhost:6379/1` (override with **`REDIS_URL`** in `.env`). Celery defaults to **db `0`** so Channels and Celery do not share the same Redis logical DB by default.
- **WebSocket:** `ws://<host>/ws/notifications/?token=<access_jwt>` — JWT is read from the query string by **`config.middleware.TokenAuthMiddleware`**.
- **REST:** `GET /api/notifications/`, `POST /api/notifications/<id>/read/`, `POST /api/notifications/read-all/` (authenticated).
- **Signals:** `projects/signals.py` — new **`ProjectSubmission`** notifies domain mentors; **`StudentProjectAssignment`** transition to **`COMPLETED`** / **`NEEDS_REVISION`** notifies the student. All WS `group_send` calls are wrapped in **`transaction.on_commit`**.
