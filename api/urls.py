"""
URL routing for MDA Report Portal API.
Configures all REST endpoints and viewsets.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    CustomTokenObtainPairView,
    UserViewSet,
    ReportViewSet,
    SyncViewSet,
    AuditLogViewSet,
    BackupViewSet,
    DataExportViewSet,
    health_check,
    api_info,
)

# Create router for viewsets
router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'reports', ReportViewSet, basename='report')
router.register(r'sync', SyncViewSet, basename='sync')
router.register(r'audit-logs', AuditLogViewSet, basename='audit-log')
router.register(r'backups', BackupViewSet, basename='backup')
router.register(r'export', DataExportViewSet, basename='export')

app_name = 'api'

urlpatterns = [
    # Authentication endpoints
    path('auth/login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Health & Info
    path('health/', health_check, name='health_check'),
    path('info/', api_info, name='api_info'),
    
    # Router URLs
    path('', include(router.urls)),
]
