from django.urls import path

from . import views

app_name = "appearance"

urlpatterns = [
    path("", views.process_selection, name="process_selection"),
    path("settings/schedule/", views.schedule_settings, name="schedule_settings"),
    path("workspace/<str:process>/", views.workspace, name="workspace"),
    path("api/employee/lookup/", views.lookup_employee, name="lookup_employee"),
    path("api/studio-assignment/retry/", views.retry_studio_assignment, name="retry_studio_assignment"),
    path("api/preparation/record/", views.record_preparation, name="record_preparation"),
    path("api/check/record/", views.record_check, name="record_check"),
    path("api/schedule/<str:process>/", views.update_schedule, name="update_schedule"),
    path("reports/export/", views.export_report, name="export_report"),
    path("health/live/", views.health_live, name="health_live"),
    path("health/ready/", views.health_ready, name="health_ready"),
]
