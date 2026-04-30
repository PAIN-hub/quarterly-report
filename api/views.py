"""
Django REST Framework views for MDA Report Portal.
Implements all API endpoints with proper authentication, permissions, and audit logging.
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.core.files.base import ContentFile
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

from .models import User, Report, ReportVersion, AuditLog, Backup, SyncConflict
from .serializers import (
    CustomTokenObtainPairSerializer, UserSerializer, UserCreateSerializer,
    ReportSerializer, ReportVersionSerializer, SyncConflictSerializer,
    AuditLogSerializer, BackupSerializer, DataExportSerializer, BulkSyncSerializer
)
from .utils import (
    log_audit, get_client_ip, record_conflict, resolve_conflict,
    create_backup, restore_backup, export_data
)

import json
import logging

logger = logging.getLogger(__name__)


# ============================================
# AUTHENTICATION ENDPOINTS
# ============================================

class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Custom JWT token endpoint using Access ID instead of username.
    POST /api/v1/auth/login/
    """
    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = [AllowAny]
    
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        
        if response.status_code == 200:
            user = User.objects.get(access_id=request.data.get('access_id'))
            user.last_login = timezone.now()
            user.save(update_fields=['last_login'])
            
            # Log login
            log_audit(
                user=user,
                action='LOGIN',
                resource_type='user',
                resource_id=str(user.id),
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
            )
        
        return response


class TokenRefreshView(viewsets.ViewSet):
    """Refresh JWT tokens."""
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def refresh(self, request):
        """POST /api/v1/auth/token/refresh/"""
        try:
            refresh = RefreshToken(request.data['refresh'])
            return Response({'access': str(refresh.access_token)})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ============================================
# USER MANAGEMENT ENDPOINTS
# ============================================

class UserViewSet(viewsets.ModelViewSet):
    """
    User management with role-based access control.
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['access_id', 'name', 'mda_name']
    ordering_fields = ['date_joined', 'last_login']
    ordering = ['-date_joined']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        return UserSerializer
    
    def get_queryset(self):
        """Filter users based on role."""
        user = self.request.user
        
        # Only SYSTEM_ADMIN and REGIONAL_OFFICER can view all users
        if user.role in ['SYSTEM_ADMIN', 'REGIONAL_OFFICER']:
            return User.objects.filter(is_active=True)
        
        # MDA_ADMIN can only see users in their MDA
        if user.role == 'MDA_ADMIN':
            return User.objects.filter(mda_name=user.mda_name, is_active=True)
        
        # Regular users can only see themselves
        return User.objects.filter(id=user.id)
    
    def create(self, request, *args, **kwargs):
        """Create new user (SYSTEM_ADMIN only)."""
        if request.user.role != 'SYSTEM_ADMIN':
            return Response(
                {'error': 'Only system administrators can create users'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        log_audit(
            user=request.user,
            action='CREATE',
            resource_type='user',
            resource_id=str(user.id),
            description=f'Created user: {user.access_id}',
            ip_address=get_client_ip(request),
        )
        
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current user profile. GET /api/v1/users/me/"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)
    
    @action(detail=True, methods=['patch'])
    def change_password(self, request, pk=None):
        """Change user password. PATCH /api/v1/users/{id}/change_password/"""
        user = self.get_object()
        
        if request.user.id != user.id and request.user.role != 'SYSTEM_ADMIN':
            return Response(
                {'error': 'Cannot change another user\'s password'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')
        
        if not user.check_password(old_password):
            return Response(
                {'error': 'Current password is incorrect'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user.set_password(new_password)
        user.save()
        
        log_audit(
            user=request.user,
            action='UPDATE',
            resource_type='user',
            resource_id=str(user.id),
            description=f'Changed password for user: {user.access_id}',
        )
        
        return Response({'message': 'Password changed successfully'})


# ============================================
# REPORT MANAGEMENT ENDPOINTS
# ============================================

class ReportViewSet(viewsets.ModelViewSet):
    """
    Report management with offline sync and conflict detection.
    """
    queryset = Report.objects.filter(is_deleted=False)
    serializer_class = ReportSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['mda_name', 'user__name']
    ordering_fields = ['last_modified', 'created_at']
    ordering = ['-last_modified']
    
    def get_queryset(self):
        """Filter reports based on user role."""
        user = self.request.user
        
        if user.role in ['SYSTEM_ADMIN', 'REGIONAL_OFFICER']:
            return Report.objects.filter(is_deleted=False)
        
        if user.role == 'MDA_ADMIN':
            return Report.objects.filter(mda_name=user.mda_name, is_deleted=False)
        
        # Regular MDA_USER can only see their own reports
        return Report.objects.filter(user=user, is_deleted=False)
    
    def create(self, request, *args, **kwargs):
        """Create new report."""
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        report = serializer.save()
        
        log_audit(
            user=request.user,
            action='CREATE',
            resource_type='report',
            resource_id=str(report.id),
            description=f'Created report: {report.mda_name}',
            ip_address=get_client_ip(request),
        )
        
        return Response(ReportSerializer(report).data, status=status.HTTP_201_CREATED)
    
    def update(self, request, *args, **kwargs):
        """Update report with conflict checking."""
        report = self.get_object()
        local_version = request.data.get('version', report.version)
        
        # Check for version conflict
        if local_version < report.version:
            # Conflict detected
            conflict = record_conflict(
                report=report,
                user=request.user,
                local_version=local_version,
                local_data=request.data.get('data', {}),
                server_version=report.version,
                server_data=report.data
            )
            
            log_audit(
                user=request.user,
                action='CONFLICT',
                resource_type='report',
                resource_id=str(report.id),
                description=f'Version conflict detected: local v{local_version} vs server v{report.version}',
            )
            
            return Response({
                'error': 'Version conflict detected',
                'conflict_id': str(conflict.id),
                'server_version': report.version,
                'server_data': report.data,
                'options': ['OVERWRITE', 'KEEP_SERVER']
            }, status=status.HTTP_409_CONFLICT)
        
        # No conflict, proceed with update
        serializer = self.get_serializer(report, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        report = serializer.save()
        
        log_audit(
            user=request.user,
            action='UPDATE',
            resource_type='report',
            resource_id=str(report.id),
            description=f'Updated report: {report.mda_name}',
        )
        
        return Response(ReportSerializer(report).data)
    
    def destroy(self, request, *args, **kwargs):
        """Soft delete report."""
        report = self.get_object()
        report.is_deleted = True
        report.save()
        
        log_audit(
            user=request.user,
            action='DELETE',
            resource_type='report',
            resource_id=str(report.id),
            description=f'Deleted report: {report.mda_name}',
        )
        
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=True, methods=['get'])
    def versions(self, request, pk=None):
        """Get all versions of a report. GET /api/v1/reports/{id}/versions/"""
        report = self.get_object()
        versions = report.versions.all()
        serializer = ReportVersionSerializer(versions, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def revert(self, request, pk=None):
        """Revert to a specific version. POST /api/v1/reports/{id}/revert/"""
        report = self.get_object()
        version_number = request.data.get('version_number')
        
        try:
            version = report.versions.get(version_number=version_number)
        except ReportVersion.DoesNotExist:
            return Response(
                {'error': 'Version not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        report.data = version.data
        report.version = report.version + 1
        report.last_modified_by = request.user
        report.save()
        
        # Create new version for revert
        ReportVersion.objects.create(
            report=report,
            version_number=report.version,
            data=report.data,
            modified_by=request.user,
            change_description=f'Reverted to version {version_number}'
        )
        
        log_audit(
            user=request.user,
            action='UPDATE',
            resource_type='report',
            resource_id=str(report.id),
            description=f'Reverted to version {version_number}',
        )
        
        return Response(ReportSerializer(report).data)


# ============================================
# SYNC & CONFLICT RESOLUTION
# ============================================

class SyncViewSet(viewsets.ViewSet):
    """
    Handle offline sync and conflict resolution.
    """
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def bulk_sync(self, request):
        """
        Bulk sync multiple offline changes.
        POST /api/v1/sync/bulk_sync/
        """
        serializer = BulkSyncSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        actions = serializer.data['actions']
        results = []
        conflicts = []
        
        for action_data in actions:
            action_type = action_data['action_type']
            report_id = action_data.get('report_id')
            data = action_data.get('data', {})
            version = action_data.get('version')
            
            try:
                if action_type == 'CREATE_REPORT':
                    report = Report.objects.create(
                        user=request.user,
                        mda_name=data.get('mdaName'),
                        data=data,
                        last_modified_by=request.user
                    )
                    ReportVersion.objects.create(
                        report=report,
                        version_number=1,
                        data=data,
                        modified_by=request.user,
                        change_description='Synced from offline'
                    )
                    results.append({
                        'action': action_type,
                        'status': 'success',
                        'report_id': str(report.id),
                        'version': 1
                    })
                
                elif action_type == 'UPDATE_REPORT':
                    report = Report.objects.get(id=report_id)
                    
                    # Check conflict
                    if version and version < report.version:
                        conflict = record_conflict(
                            report=report,
                            user=request.user,
                            local_version=version,
                            local_data=data,
                            server_version=report.version,
                            server_data=report.data
                        )
                        conflicts.append({
                            'conflict_id': str(conflict.id),
                            'report_id': str(report.id),
                            'local_version': version,
                            'server_version': report.version
                        })
                    else:
                        report.data = data
                        report.version = (report.version or 0) + 1
                        report.last_modified = timezone.now()
                        report.last_modified_by = request.user
                        report.synced_at = timezone.now()
                        report.save()
                        
                        ReportVersion.objects.create(
                            report=report,
                            version_number=report.version,
                            data=data,
                            modified_by=request.user,
                            change_description='Synced from offline'
                        )
                        
                        results.append({
                            'action': action_type,
                            'status': 'success',
                            'report_id': str(report.id),
                            'version': report.version
                        })
                
                elif action_type == 'DELETE_REPORT':
                    report = Report.objects.get(id=report_id)
                    report.is_deleted = True
                    report.save()
                    results.append({
                        'action': action_type,
                        'status': 'success',
                        'report_id': str(report.id)
                    })
            
            except Report.DoesNotExist:
                results.append({
                    'action': action_type,
                    'status': 'error',
                    'error': 'Report not found'
                })
        
        # Update user's last_sync
        request.user.last_sync = timezone.now()
        request.user.save(update_fields=['last_sync'])
        
        log_audit(
            user=request.user,
            action='SYNC',
            resource_type='sync',
            resource_id='bulk',
            description=f'Synced {len(actions)} actions, {len(conflicts)} conflicts',
        )
        
        return Response({
            'results': results,
            'conflicts': conflicts,
            'synced_at': timezone.now()
        })
    
    @action(detail=False, methods=['get'])
    def changes_since(self, request):
        """Get all changes since last sync. GET /api/v1/sync/changes_since/?timestamp=..."""
        timestamp_str = request.query_params.get('timestamp')
        
        if not timestamp_str:
            return Response(
                {'error': 'timestamp parameter required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from dateutil import parser
            timestamp = parser.isoparse(timestamp_str)
        except:
            return Response(
                {'error': 'Invalid timestamp format'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reports = Report.objects.filter(
            last_modified__gte=timestamp,
            is_deleted=False
        ).select_related('user', 'last_modified_by')
        
        deleted_reports = Report.objects.filter(
            last_modified__gte=timestamp,
            is_deleted=True
        ).values_list('id', flat=True)
        
        serializer = ReportSerializer(reports, many=True)
        
        return Response({
            'updated_reports': serializer.data,
            'deleted_report_ids': list(deleted_reports),
            'server_timestamp': timezone.now()
        })


# ============================================
# AUDIT & BACKUP
# ============================================

class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Audit log management (read-only for non-admins).
    """
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['user__name', 'action', 'resource_type']
    ordering_fields = ['created_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        user = self.request.user
        
        if user.role in ['SYSTEM_ADMIN', 'REGIONAL_OFFICER']:
            return AuditLog.objects.all()
        
        # Regular users can only see their own audit logs
        return AuditLog.objects.filter(user=user)


class BackupViewSet(viewsets.ModelViewSet):
    """
    Backup management (SYSTEM_ADMIN only).
    """
    queryset = Backup.objects.all()
    serializer_class = BackupSerializer
    permission_classes = [IsAuthenticated]
    ordering = ['-created_at']
    
    def get_queryset(self):
        if self.request.user.role != 'SYSTEM_ADMIN':
            return Backup.objects.none()
        return Backup.objects.all()
    
    def create(self, request, *args, **kwargs):
        """Create manual backup."""
        if request.user.role != 'SYSTEM_ADMIN':
            return Response(
                {'error': 'Only system administrators can create backups'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        backup = create_backup(
            created_by=request.user,
            description=request.data.get('description', ''),
            backup_type='MANUAL'
        )
        
        log_audit(
            user=request.user,
            action='BACKUP',
            resource_type='backup',
            resource_id=str(backup.id),
            description=f'Created backup: {backup.backup_name}',
        )
        
        return Response(BackupSerializer(backup).data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        """Restore from backup. POST /api/v1/backups/{id}/restore/"""
        if request.user.role != 'SYSTEM_ADMIN':
            return Response(
                {'error': 'Only system administrators can restore backups'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        backup = self.get_object()
        
        try:
            restore_backup(backup, request.user)
            
            log_audit(
                user=request.user,
                action='RESTORE',
                resource_type='backup',
                resource_id=str(backup.id),
                description=f'Restored from backup: {backup.backup_name}',
            )
            
            return Response({'message': 'Backup restored successfully'})
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'])
    def verify(self, request, pk=None):
        """Verify backup integrity. GET /api/v1/backups/{id}/verify/"""
        backup = self.get_object()
        is_valid = backup.verify_integrity()
        
        return Response({
            'backup_id': str(backup.id),
            'integrity_valid': is_valid,
            'data_hash': backup.data_hash
        })


# ============================================
# DATA EXPORT
# ============================================

class DataExportViewSet(viewsets.ViewSet):
    """
    Data export functionality (JSON download).
    """
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def export_json(self, request):
        """
        Export all accessible data as JSON.
        GET /api/v1/export/export_json/?include_audit=true
        """
        if request.user.role not in ['SYSTEM_ADMIN', 'REGIONAL_OFFICER']:
            return Response(
                {'error': 'Insufficient permissions for data export'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        include_audit = request.query_params.get('include_audit', 'false').lower() == 'true'
        
        try:
            export_data_dict = export_data(
                user=request.user,
                include_audit=include_audit,
                include_deleted=request.query_params.get('include_deleted', 'false').lower() == 'true'
            )
            
            response = HttpResponse(
                json.dumps(export_data_dict, indent=2, default=str),
                content_type='application/json'
            )
            response['Content-Disposition'] = f'attachment; filename="mda_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.json"'
            
            log_audit(
                user=request.user,
                action='EXPORT',
                resource_type='data',
                resource_id='all',
                description=f'Exported data (audit: {include_audit})',
            )
            
            return response
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


# ============================================
# HEALTH & STATUS
# ============================================

@require_http_methods(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    """Health check endpoint. GET /api/v1/health/"""
    return JsonResponse({
        'status': 'healthy',
        'timestamp': timezone.now().isoformat()
    })


@require_http_methods(["GET"])
def api_info(request):
    """API information endpoint. GET /api/v1/info/"""
    return JsonResponse({
        'name': 'MDA Report Portal API',
        'version': '1.0.0',
        'documentation': '/api/v1/docs/',
    })
