"""
drf-spectacular postprocessing: map URL paths to OpenAPI tags (one Django app per group).
"""


def _infer_tag(path: str) -> str:
    """Return a short tag name matching the Django app that owns the route."""
    if path.startswith('/api/chat/'):
        return 'chat'
    if path.startswith('/api/mentor/'):
        return 'mentor'
    if path.startswith('/api/portfolio/'):
        return 'portfolio'
    if path.startswith('/api/reports/') or path.startswith('/api/admin/reports/'):
        return 'reports'
    # assessments: student flows + admin question bank under domains
    if path.startswith('/api/student/assessments/') or path.startswith('/api/student/attempts/'):
        return 'assessments'
    if path.startswith('/api/admin/domains/question-counts'):
        return 'assessments'
    if '/questions/' in path and path.startswith('/api/admin/domains/'):
        return 'assessments'
    # projects: templates, assignments, submissions, evaluations
    if path.startswith('/api/admin/project-templates'):
        return 'projects'
    if path.startswith('/api/admin/projects/'):
        return 'projects'
    if path.startswith('/api/admin/submissions/'):
        return 'projects'
    if path.startswith('/api/admin/evaluations/'):
        return 'projects'
    if path.startswith('/api/student/projects/'):
        return 'projects'
    if path.startswith('/api/student/assignments/'):
        return 'projects'
    if path.startswith('/api/student/submissions/'):
        return 'projects'
    # accounts: auth, profiles, admin user/domain CRUD (non-question routes)
    if path.startswith('/api/'):
        return 'accounts'
    return 'other'


def tag_paths_by_app(result, generator, request, public):
    """Replace default tags (often a single "api") with app-level tags per path."""
    for path, path_item in result.get('paths', {}).items():
        if not isinstance(path_item, dict):
            continue
        tag = _infer_tag(path)
        for method, operation in path_item.items():
            if not method or method.startswith('x-') or not isinstance(operation, dict):
                continue
            if method.lower() not in ('get', 'put', 'patch', 'post', 'delete', 'options', 'head', 'trace'):
                continue
            operation['tags'] = [tag]
    return result
