from django.contrib import admin

from .models import (
    EvaluationRubric,
    ProjectInstruction,
    ProjectSubmission,
    ProjectTemplate,
    StudentProgressSnapshot,
    StudentProjectAssignment,
    SubmissionEvaluation,
)


@admin.register(ProjectTemplate)
class ProjectTemplateAdmin(admin.ModelAdmin):
    list_display = ('title', 'domain', 'complexity', 'submission_type', 'active')
    list_filter = ('domain', 'complexity', 'submission_type', 'active')
    search_fields = ('title', 'short_description', 'domain__name', 'domain__code')


@admin.register(StudentProjectAssignment)
class StudentProjectAssignmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'project_template', 'status', 'recommendation_score', 'assigned_at')
    list_filter = ('status', 'project_template__complexity', 'project_template__domain')
    search_fields = ('student__username', 'student__email', 'project_template__title')


admin.site.register(ProjectInstruction)
admin.site.register(EvaluationRubric)
admin.site.register(ProjectSubmission)
admin.site.register(SubmissionEvaluation)
admin.site.register(StudentProgressSnapshot)
