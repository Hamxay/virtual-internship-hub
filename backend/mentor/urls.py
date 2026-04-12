from django.urls import path

from .views import MentorQueueView, MentorReviewActionView

urlpatterns = [
    path('queue/', MentorQueueView.as_view(), name='mentor-queue'),
    path('reviews/', MentorReviewActionView.as_view(), name='mentor-review-action'),
]
