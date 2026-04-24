from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification
from .serializers import NotificationSerializer


class NotificationListView(generics.ListAPIView):
    """GET /api/notifications/ — latest 20 for the current user."""

    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user).order_by('-created_at')[:20]


class NotificationMarkReadView(APIView):
    """POST /api/notifications/<id>/read/"""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        updated = Notification.objects.filter(pk=pk, recipient=request.user, is_read=False).update(
            is_read=True
        )
        if not updated:
            return Response({'detail': 'Not found or already read.'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'detail': 'Marked read.'}, status=status.HTTP_200_OK)


class NotificationReadAllView(APIView):
    """POST /api/notifications/read-all/"""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
        return Response({'detail': 'All marked read.'}, status=status.HTTP_200_OK)
