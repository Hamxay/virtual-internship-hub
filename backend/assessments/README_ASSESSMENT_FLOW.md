# How the Skill Assessment Works

## How the test is **given** (which questions)

- **Endpoint:** `GET /student/assessments/composed/`
- **Logic:** `assessments/services.py` → `get_composed_questions(user)`

  **If the student has target domains (e.g. Web Development, Graphic Design):**
  - The test is built from those domains only.
  - **10 questions per target domain** are chosen randomly from the domain’s question bank.
  - Example: 2 target domains → up to 20 questions; 3 target domains → up to 30 questions.

  **If the student has no target domains:**
  - The test uses **popular domains** (e.g. GRAPHIC_DESIGN, WEB_DEVELOPMENT, E_COMMERCE_MANAGEMENT, etc.).
  - Up to **50 questions** are chosen randomly from those domains.

- Questions come from **Domain Questions** (admin adds them per domain). Each question has: `text`, `option_a/b/c/d`, `correct_option` (A/B/C/D), `points`, `complexity`.

---

## How the test is **checked** (scoring and result)

- **Endpoint:** `POST /student/assessments/composed/submit/`
- **Body:** `{ "answers": [ { "question_id": 123, "selected_option": "A" }, ... ] }`
- **Logic:** `assessments/services.py` → `compute_composed_score_and_recommend(answers)` (RandomForest + weighted domain profile; rule-based fields kept in `recommendation_meta` for comparison).

  1. **Scoring**
     - For each answer, the backend compares `selected_option` to the question’s `correct_option` (case-insensitive).
     - If they match, the question’s **points** are added to the score.
     - **Total score** = sum of points for correct answers.  
     - **Total points** = sum of points for all questions in the test.

  2. **Percentage and pass/fail**
     - `percentage = (score / total_points) * 100`
     - **Pass** if `percentage >= 70`; otherwise **fail**.

  3. **Domain recommendation (ML-assisted)**
     - Per-domain scores feed `assessments/domain_recommendation/sklearn_domain_classifier.py` (RandomForest + probabilities); rule ranking is `rule_based_ranking.py`.
     - Primary domain is returned in `recommended_domains`; `recommendation_meta` includes `weighted_domain_profile` and `weighted_domain_profile_text`.
     - `assessments/services.py` → `sync_assessment_to_snapshot(attempt_id)` updates `StudentProgressSnapshot` (weights, metadata, strongest domain); weight parsing lives in `projects/services/domain_profile.py`.

- **Response:** `score`, `total_points`, `percentage`, `passed`, `recommended_domains`, plus attempt metadata.

---

## Summary

| What              | Based on |
|-------------------|----------|
| **Which questions** | Student’s target domains (10 per domain) or 50 from popular domains if no targets. |
| **Checking answers** | Compare each `selected_option` to the question’s `correct_option`. |
| **Score**          | Sum of question `points` for correct answers. |
| **Pass**           | `(score / total_points) * 100 >= 60`. |
| **Recommended domain** | Per-domain scores → AI/recommendation logic picks one domain. |
