from django.urls import path

from . import health, views

app_name = "core"

urlpatterns = [
    path("", views.LandingView.as_view(), name="landing"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("health/live/", health.live, name="health-live"),
    path("health/ready/", health.ready, name="health-ready"),
]
