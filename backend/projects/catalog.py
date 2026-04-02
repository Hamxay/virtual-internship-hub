from projects.serializers import DEFAULT_RUBRIC_CRITERIA


COMPLEXITY_PRESETS = {
    'BEGINNER': {
        'hours': 8,
        'scope': 'a guided starter task',
        'deliverable_hint': 'a concise but complete first solution',
    },
    'INTERMEDIATE': {
        'hours': 16,
        'scope': 'a multi-step applied project',
        'deliverable_hint': 'a polished solution with clear explanation',
    },
    'ADVANCED': {
        'hours': 24,
        'scope': 'an end-to-end portfolio-style project',
        'deliverable_hint': 'a production-style submission with reflection',
    },
}


TYPE_KEYWORDS = {
    'CODE': ['implementation', 'testing', 'documentation', 'requirements'],
    'DOCUMENT': ['structure', 'insight', 'clarity', 'originality'],
    'DESIGN': ['research', 'visual quality', 'usability', 'handoff'],
}


def _detect_submission_type(domain):
    name = domain.name.lower()
    if any(term in name for term in ['design', 'graphic', 'video', 'autocad', 'ui/ux']):
        return 'DESIGN'
    if any(term in name for term in ['writing', 'marketing', 'seo', 'assistant', 'communication', 'literacy']):
        return 'DOCUMENT'
    return 'CODE'


def build_template_specs(domain):
    submission_type = _detect_submission_type(domain)
    domain_name = domain.name
    templates = []
    for complexity, preset in COMPLEXITY_PRESETS.items():
        title = {
            'BEGINNER': f'{domain_name} Starter Project',
            'INTERMEDIATE': f'{domain_name} Applied Workflow',
            'ADVANCED': f'{domain_name} Portfolio Challenge',
        }[complexity]
        templates.append(
            {
                'title': title,
                'short_description': (
                    f'Complete {preset["scope"]} in {domain_name} focused on real-world delivery and reflection.'
                ),
                'business_problem': (
                    f'A client needs help in {domain_name}. The student must deliver {preset["deliverable_hint"]} '
                    f'that solves a realistic business or portfolio scenario.'
                ),
                'complexity': complexity,
                'submission_type': submission_type,
                'estimated_hours': preset['hours'],
                'tags': [domain.code, complexity.lower(), submission_type.lower()],
                'prerequisite_skills': [domain_name, 'time management', 'communication'],
                'expected_keywords': [domain_name, 'client goal', 'deliverable', 'reflection'] + TYPE_KEYWORDS[submission_type],
                'instruction': {
                    'overview': (
                        f'Work on a {complexity.lower()}-level project in {domain_name}. '
                        'Follow the requirements, explain your approach, and show the final outcome clearly.'
                    ),
                    'steps': [
                        'Review the problem statement and identify the client goal.',
                        'Plan your approach and define the main deliverables.',
                        'Produce the submission using your chosen tools and workflow.',
                        'Write a short reflection explaining your decisions and trade-offs.',
                    ],
                    'deliverables': [
                        'Final solution or artifact',
                        'Brief implementation or process summary',
                        'Evidence of testing, review, or validation',
                        'Short reflection on improvements for the next iteration',
                    ],
                    'submission_requirements': [
                        'Submit at least one project link, artifact link, or written explanation.',
                        'Describe how your work meets the requested outcome.',
                        'Keep the submission original and avoid copied content.',
                    ],
                    'starter_resources': [
                        f'Official learning materials related to {domain_name}',
                        'Any code repository, design board, or document link used in the work',
                    ],
                    'evaluation_notes': (
                        'Score the student on correctness, originality, communication quality, and completeness.'
                    ),
                },
                'rubric': {
                    'passing_score': 70,
                    'criteria': DEFAULT_RUBRIC_CRITERIA,
                    'allow_auto_accept': True,
                    'plagiarism_threshold': 75.0,
                    'grammar_weight': 15.0,
                },
            }
        )
    return templates
