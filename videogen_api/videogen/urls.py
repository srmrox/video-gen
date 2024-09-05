from django.urls import path
from .views import ProcessVideoView

urlpatterns = [
    path('process-video/', ProcessVideoView.as_view(), name='process-video'),
]
