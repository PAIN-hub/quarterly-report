"""
Utility functions for MDA Report Portal.
Includes audit logging, backup/restore, data export, and sync conflict handling.
"""

from django.utils import timezone
from django.db import transaction
from django.core.serializers import serialize
import json
import hashlib
import logging
from datetime import datetime
from .models import User, Report, AuditLog, Backup, SyncConflict, ReportVersion

logger = logging.getLogger(__name__)


def get_client_ip(request):
    """Extract client IP from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def log_audit(user, action, resource_type, resource_id, description='', 
              ip_address=None, user_agent='', changes=None):
    """
    Log an audit event for compliance and debugging.
    
    Args:
        user: User performing the action
        action: Action type (CREATE, UPDATE, DELETE, SYNC, etc.)
        resource_type: Type of resource being affected
        resource_id: ID of the resource
        description: Human-readable description
        ip_address: Client IP address
        user_agent: Client user agent string
        changes: Dict of field changes {field: {old: value, new: value}}
    """
    try:
        AuditLog.objects.create(
            user=user,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id),
            description=description,
            ip_address=ip_address,
            user_agent=user_agent,
            changes=changes or {}
        )
        logger.info(f'[AUDIT] {action} {resource_type}:{resource_id} by {user.access_id}')
    except Exception as e:
        logger.error(f'Failed to log audit: {str(e)}')


def record_conflict(report, user, local_version, local_data, server_version, server_data):
    """
    Record a sync conflict when local and server versions differ.
    """
    conflict = SyncConflict.objects.create(
        report=report,
        user=user,
        local_version=local_version,
        server_version=server_version,
        local_data=local_data,
        server_data=server_data,
        resolution='PENDING'
    )
    
    log_audit(
        user=user,
        action='CONFLICT',
        resource_type='sync_conflict',
        resource_id=str(conflict.id),
        description=f'Conflict: {report.mda_name} v{local_version} vs v{server_version}'
    )
    
    return conflict


def resolve_conflict(conflict, resolution_type, request_user=None):
    """
    Resolve a sync conflict.
    
    Args:
        conflict: SyncConflict object
        resolution_type: 'OVERWRITE' or 'KEEP_SERVER'
        request_user: User making the resolution
    """
    if resolution_type == 'OVERWRITE':
        # Overwrite server with local data
        report = conflict.report
        report.data = conflict.local_data
        report.version = conflict.server_version + 1
        report.last_modified_by = conflict.user
        report.last_modified = timezone.now()
        report.save()
        
        # Create version snapshot
        ReportVersion.objects.create(
            report=report,
            version_number=report.version,
            data=report.data,
            modified_by=conflict.user,
            change_description=f'Conflict resolution: Overwrote server v{conflict.server_version}'
        )
    
    elif resolution_type == 'KEEP_SERVER':
        # Keep server version, discard local changes
        pass
    
    conflict.resolution = resolution_type
    conflict.resolved_at = timezone.now()
    conflict.save()
    
    log_audit(
        user=request_user or conflict.user,
        action='UPDATE',
        resource_type='sync_conflict',
        resource_id=str(conflict.id),
        description=f'Resolved conflict with: {resolution_type}'
    )


def create_backup(created_by, description='', backup_type='MANUAL'):
    """
    Create a complete backup of all system data.
    
    Args:
        created_by: User creating the backup
        description: Backup description
        backup_type: MANUAL, SCHEDULED, or AUTOMATED
    
    Returns:
        Backup object
    """
    try:
        backup_data = {
            'timestamp': timezone.now().isoformat(),
            'backup_type': backup_type,
            'users': [],
            'reports': [],
            'audit_logs': [],
        }
        
        # Export users
        for user in User.objects.all():
            backup_data['users'].append({
                'id': str(user.id),
                'access_id': user.access_id,
                'name': user.name,
                'email': user.email,
                'role': user.role,
                'mda_name': user.mda_name,
                'date_joined': user.date_joined.isoformat(),
                'is_active': user.is_active,
            })
        
        # Export reports with all versions
        for report in Report.objects.all():
            report_data = {
                'id': str(report.id),
                'user_id': str(report.user.id),
                'mda_name': report.mda_name,
                'data': report.data,
                'version': report.version,
                'created_at': report.created_at.isoformat(),
                'updated_at': report.updated_at.isoformat(),
                'last_modified': report.last_modified.isoformat(),
                'is_deleted': report.is_deleted,
                'versions': []
            }
            
            for version in report.versions.all():
                report_data['versions'].append({
                    'version_number': version.version_number,
                    'data': version.data,
                    'created_at': version.created_at.isoformat(),
                    'change_description': version.change_description,
                })
            
            backup_data['reports'].append(report_data)
        
        # Export audit logs
        for log in AuditLog.objects.all():
            backup_data['audit_logs'].append({
                'id': str(log.id),
                'user_id': str(log.user.id) if log.user else None,
                'action': log.action,
                'resource_type': log.resource_type,
                'resource_id': log.resource_id,
                'description': log.description,
                'created_at': log.created_at.isoformat(),
            })
        
        # Calculate hash for integrity checking
        backup_json = json.dumps(backup_data, sort_keys=True)
        data_hash = hashlib.sha256(backup_json.encode()).hexdigest()
        
        # Create backup record
        backup = Backup.objects.create(
            backup_name=f'backup_{timezone.now().strftime("%Y%m%d_%H%M%S")}',
            description=description,
            data=backup_data,
            data_hash=data_hash,
            status='COMPLETED',
            backup_type=backup_type,
            created_by=created_by,
            size_bytes=len(backup_json.encode())
        )
        
        log_audit(
            user=created_by,
            action='BACKUP',
            resource_type='backup',
            resource_id=str(backup.id),
            description=f'Created {backup_type} backup with {len(backup_data["reports"])} reports'
        )
        
        logger.info(f'Backup created: {backup.backup_name} ({backup.size_bytes} bytes)')
        return backup
    
    except Exception as e:
        logger.error(f'Backup creation failed: {str(e)}')
        raise


@transaction.atomic
def restore_backup(backup, restore_user):
    """
    Restore system to a previous backup state.
    WARNING: This will overwrite current data!
    
    Args:
        backup: Backup object to restore
        restore_user: User performing the restore
    """
    if not backup.verify_integrity():
        raise ValueError('Backup integrity check failed. Restore aborted for safety.')
    
    try:
        data = backup.data
        
        # Clear existing data (soft delete reports, deactivate users)
        Report.objects.all().update(is_deleted=True)
        User.objects.filter(is_active=True).update(is_active=False)
        
        # Restore users (except superusers)
        user_id_map = {}  # Track old->new ID mapping
        for user_data in data.get('users', []):
            # Don't restore if superuser
            if user_data['is_active']:
                old_id = user_data['id']
                user = User.objects.create_user(
                    access_id=user_data['access_id'],
                    password='restored_placeholder',  # User must reset password
                    name=user_data['name'],
                    email=user_data.get('email'),
                    role=user_data.get('role', 'MDA_USER'),
                    mda_name=user_data.get('mda_name')
                )
                user_id_map[old_id] = user
        
        # Restore reports
        report_id_map = {}
        for report_data in data.get('reports', []):
            old_id = report_data['id']
            user_id = report_data['user_id']
            
            if user_id in user_id_map:
                user = user_id_map[user_id]
                report = Report.objects.create(
                    id=report_data['id'],
                    user=user,
                    mda_name=report_data['mda_name'],
                    data=report_data['data'],
                    version=report_data['version'],
                    created_at=datetime.fromisoformat(report_data['created_at']),
                    is_deleted=report_data['is_deleted']
                )
                report_id_map[old_id] = report
                
                # Restore report versions
                for version_data in report_data.get('versions', []):
                    ReportVersion.objects.create(
                        report=report,
                        version_number=version_data['version_number'],
                        data=version_data['data'],
                        created_at=datetime.fromisoformat(version_data['created_at']),
                        change_description=version_data.get('change_description')
                    )
        
        # Update backup record
        backup.restored_at = timezone.now()
        backup.restored_by = restore_user
        backup.save(update_fields=['restored_at', 'restored_by'])
        
        log_audit(
            user=restore_user,
            action='RESTORE',
            resource_type='backup',
            resource_id=str(backup.id),
            description=f'Restored from backup: {backup.backup_name}'
        )
        
        logger.info(f'Backup restored: {backup.backup_name}')
    
    except Exception as e:
        logger.error(f'Backup restore failed: {str(e)}')
        raise


def export_data(user, include_audit=False, include_deleted=False):
    """
    Export all accessible data as JSON.
    
    Args:
        user: User performing export (must be SYSTEM_ADMIN or REGIONAL_OFFICER)
        include_audit: Include audit logs
        include_deleted: Include soft-deleted reports
    
    Returns:
        Dict with users, reports, and optionally audit logs
    """
    export_dict = {
        'export_date': timezone.now().isoformat(),
        'exported_by': user.access_id,
        'users': [],
        'reports': [],
        'audit_logs': [] if include_audit else None,
    }
    
    # Get users based on role
    if user.role == 'SYSTEM_ADMIN':
        users = User.objects.all()
    elif user.role == 'REGIONAL_OFFICER':
        users = User.objects.filter(mda_name__isnull=False)
    else:
        users = User.objects.filter(id=user.id)
    
    # Export users
    for u in users:
        export_dict['users'].append({
            'id': str(u.id),
            'access_id': u.access_id,
            'name': u.name,
            'email': u.email,
            'role': u.role,
            'mda_name': u.mda_name,
        })
    
    # Get reports
    if user.role == 'SYSTEM_ADMIN':
        reports = Report.objects.all()
    elif user.role == 'REGIONAL_OFFICER':
        reports = Report.objects.filter(user__mda_name__isnull=False)
    else:
        reports = Report.objects.filter(user=user)
    
    if not include_deleted:
        reports = reports.filter(is_deleted=False)
    
    # Export reports
    for report in reports:
        report_dict = {
            'id': str(report.id),
            'user_id': str(report.user.id),
            'mda_name': report.mda_name,
            'data': report.data,
            'version': report.version,
            'created_at': report.created_at.isoformat(),
            'updated_at': report.updated_at.isoformat(),
            'is_deleted': report.is_deleted,
        }
        export_dict['reports'].append(report_dict)
    
    # Export audit logs if requested
    if include_audit:
        if user.role == 'SYSTEM_ADMIN':
            logs = AuditLog.objects.all()
        else:
            logs = AuditLog.objects.filter(user=user)
        
        for log in logs:
            export_dict['audit_logs'].append({
                'id': str(log.id),
                'user_id': str(log.user.id) if log.user else None,
                'action': log.action,
                'resource_type': log.resource_type,
                'resource_id': log.resource_id,
                'description': log.description,
                'created_at': log.created_at.isoformat(),
            })
    
    return export_dict


def get_performance_metrics(user=None):
    """
    Generate performance metrics for dashboard.
    """
    base_query = Report.objects.filter(is_deleted=False)
    
    if user:
        base_query = base_query.filter(user=user)
    
    metrics = {
        'total_reports': base_query.count(),
        'reports_this_month': base_query.filter(
            created_at__year=timezone.now().year,
            created_at__month=timezone.now().month
        ).count(),
        'pending_conflicts': SyncConflict.objects.filter(resolution='PENDING').count(),
    }
    
    # Calculate average performance
    excellent = fair = good = poor = 0
    for report in base_query:
        perf = report.data.get('capexPerformance')
        if perf:
            perf_num = float(perf) if isinstance(perf, (int, float)) else 0
            if perf_num >= 90:
                excellent += 1
            elif perf_num >= 70:
                good += 1
            elif perf_num >= 50:
                fair += 1
            else:
                poor += 1
    
    metrics['performance_distribution'] = {
        'excellent': excellent,
        'good': good,
        'fair': fair,
        'poor': poor
    }
    
    return metrics
