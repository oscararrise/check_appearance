from django.urls import path

from . import views

app_name = "appearance"

urlpatterns = [
    path("", views.process_selection, name="process_selection"),
    path("workspace/<str:process>/", views.workspace, name="workspace"),
    path("api/employee/lookup/", views.lookup_employee, name="lookup_employee"),
    path("api/preparation/record/", views.record_preparation, name="record_preparation"),
    path("api/check/record/", views.record_check, name="record_check"),
    path("reports/export/", views.export_report, name="export_report"),
]
