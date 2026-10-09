from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('upload/', views.upload_view, name='upload'),
    path('meeting/<uuid:meeting_id>/', views.meeting_detail_view, name='meeting_detail'),
    path('meeting/<uuid:meeting_id>/status/', views.meeting_status_api, name='meeting_status_api'),
    path('meeting/<uuid:meeting_id>/chat/', views.meeting_chat_api, name='meeting_chat_api'),
    path('meeting/<uuid:meeting_id>/reprocess/', views.reprocess_meeting_view, name='reprocess_meeting'),
    path('meeting/<uuid:meeting_id>/export/md/', views.export_meeting_markdown, name='export_markdown'),
    path('meeting/<uuid:meeting_id>/export/pdf/', views.export_meeting_pdf, name='export_pdf'),
    path('meeting/<uuid:meeting_id>/delete/', views.delete_meeting_view, name='delete_meeting'),
    path('compare/', views.compare_meetings_view, name='compare_meetings'),
    path('search/', views.search_view, name='search'),
]
