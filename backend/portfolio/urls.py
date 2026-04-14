from django.urls import path

from .views import PublicPortfolioView

urlpatterns = [
    path('<str:username>/', PublicPortfolioView.as_view(), name='public-portfolio'),
]
