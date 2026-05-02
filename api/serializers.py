"""
Django REST Framework serializers for MDA Report Portal.
Handles data validation and transformation for all API endpoints.
"""

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import User, Report, ReportVersion, AuditLog, Backup, SyncConflict
from django.utils import timezone
from django.contrib.auth.hashers import make_password
import hashlib
import json


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Customized JWT token serializer for Access ID authentication.
    """
    username_field = 'access_id'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Change the username field label
        if 'username' in self.fields:
         del self.fields['username']
         
        self.fields[self.username_field] = serializers.CharField()
    
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        
        # Add custom claims
        token['access_id'] = user.access_id
        token['name'] = user.name
        token['role'] = user.role
        token['mda_name'] = user.mda_name
        
        return token


class UserSerializer(serializers.ModelSerializer):
    """User serializer with password hashing."""
    
    class Meta:
        model = User
        fields = ['id', 'access_id', 'name', 'email', 'role', 'mda_name', 'is_active', 'date_joined', 'last_login']
        read_only_fields = ['id', 'date_joined', 'last_login']


class UserCreateSerializer(serializers.ModelSerializer):
    """User creation serializer with password handling."""
    password = serializers.CharField(write_only=True, required=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True, required=True)
    
    class Meta:
        model = User
        fields = ['access_id', 'name', 'email', 'password', 'password_confirm', 'role', 'mda_name']
    
    def validate(self, data):
        if data['password'] != data.pop('password_confirm'):
            raise serializers.ValidationError({'password': 'Passwords do not match.'})
        
        # Validate Access ID format (e.g., KTS-MDA-001)
        access_id = data.get('access_id', '').upper()
        parts = access_id.split('-')
        if len(parts) != 3 or not all(len(p) > 0 for p in parts):
            raise serializers.ValidationError({
                'access_id': 'Access ID must be in format: STATE-MDA-NUMBER (e.g., KTS-MDA-001)'
            })
        
        return data
    
    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user


class ReportVersionSerializer(serializers.ModelSerializer):
    """Serializer for report version history."""
    modified_by_name = serializers.CharField(source='modified_by.name', read_only=True)
    
    class Meta:
        model = ReportVersion
        fields = ['id', 'version_number', 'data', 'modified_by', 'modified_by_name', 'created_at', 'change_description']
        read_only_fields = ['id', 'created_at']


class ReportSerializer(serializers.ModelSerializer):
    """Report serializer with version and sync tracking."""
    user_name = serializers.CharField(source='user.name', read_only=True)
    last_modified_by_name = serializers.CharField(source='last_modified_by.name', read_only=True)
    versions = ReportVersionSerializer(many=True, read_only=True)
    performance_status = serializers.SerializerMethodField()
    
    class Meta:
        model = Report
        fields = [
            'id', 'user', 'user_name', 'mda_name', 'data', 'version', 
            'created_at', 'updated_at', 'last_modified', 'last_modified_by', 'last_modified_by_name',
            'synced_at', 'is_deleted', 'versions', 'performance_status'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'last_modified', 'synced_at', 'versions']
    
    def get_performance_status(self, obj):
        """Calculate performance status from capexPerformance data."""
        perf = obj.data.get('capexPerformance')
        if not perf:
            return None
        
        perf_num = float(perf) if isinstance(perf, (int, float)) else 0
        if perf_num >= 90:
            return 'EXCELLENT'
        elif perf_num >= 70:
            return 'GOOD'
        elif perf_num >= 50:
            return 'FAIR'
        else:
            return 'POOR'
    
    def create(self, validated_data):
        """Create report and initial version."""
        user = self.context['request'].user
        report = Report.objects.create(user=user, last_modified_by=user, **validated_data)
        
        # Create initial version
        ReportVersion.objects.create(
            report=report,
            version_number=1,
            data=validated_data['data'],
            modified_by=user,
            change_description='Initial submission'
        )
        
        return report
    
    def update(self, instance, validated_data):
        """Update report with version tracking."""
        user = self.context['request'].user
        
        # Check for version conflicts
        new_version = instance.version + 1
        old_data = instance.data.copy() if instance.data else {}
        
        instance.data = validated_data.get('data', instance.data)
        instance.last_modified_by = user
        instance.version = new_version
        instance.save()
        
        # Create version snapshot
        ReportVersion.objects.create(
            report=instance,
            version_number=new_version,
            data=instance.data,
            modified_by=user,
            change_description='Updated'
        )
        
        return instance


class SyncConflictSerializer(serializers.ModelSerializer):
    """Serializer for sync conflicts."""
    report_name = serializers.CharField(source='report.mda_name', read_only=True)
    user_name = serializers.CharField(source='user.name', read_only=True)
    
    class Meta:
        model = SyncConflict
        fields = [
            'id', 'report', 'report_name', 'user', 'user_name', 
            'local_version', 'server_version', 'local_data', 'server_data',
            'resolution', 'created_at', 'resolved_at'
        ]
        read_only_fields = ['id', 'created_at', 'resolved_at']


class AuditLogSerializer(serializers.ModelSerializer):
    """Serializer for audit logs."""
    user_name = serializers.CharField(source='user.name', read_only=True)
    
    class Meta:
        model = AuditLog
        fields = [
            'id', 'user', 'user_name', 'action', 'resource_type', 'resource_id',
            'changes', 'description', 'ip_address', 'user_agent', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class BackupSerializer(serializers.ModelSerializer):
    """Serializer for backup management."""
    created_by_name = serializers.CharField(source='created_by.name', read_only=True)
    restored_by_name = serializers.CharField(source='restored_by.name', read_only=True)
    
    class Meta:
        model = Backup
        fields = [
            'id', 'backup_name', 'description', 'status', 'backup_type',
            'created_by', 'created_by_name', 'created_at', 'size_bytes',
            'restored_at', 'restored_by', 'restored_by_name'
        ]
        read_only_fields = ['id', 'created_at', 'size_bytes', 'restored_at', 'restored_by']


class DataExportSerializer(serializers.Serializer):
    """Serializer for data export functionality."""
    users = UserSerializer(many=True)
    reports = ReportSerializer(many=True)
    audit_logs = AuditLogSerializer(many=True)
    metadata = serializers.SerializerMethodField()
    
    def get_metadata(self, obj):
        return {
            'export_date': timezone.now().isoformat(),
            'total_users': obj.get('users', []) | len(),
            'total_reports': obj.get('reports', []) | len(),
            'total_audit_entries': obj.get('audit_logs', []) | len(),
            'backup_hash': hashlib.sha256(
                json.dumps(obj, default=str, sort_keys=True).encode()
            ).hexdigest()
        }


class SyncActionSerializer(serializers.Serializer):
    """Serializer for sync actions from offline clients."""
    action_type = serializers.ChoiceField(choices=['CREATE_REPORT', 'UPDATE_REPORT', 'DELETE_REPORT'])
    report_id = serializers.UUIDField(required=False, allow_null=True)
    data = serializers.JSONField()
    version = serializers.IntegerField(required=False)
    timestamp = serializers.DateTimeField(required=False)


class BulkSyncSerializer(serializers.Serializer):
    """Serializer for bulk sync operations from offline clients."""
    actions = SyncActionSerializer(many=True)
    device_id = serializers.CharField(max_length=255)
    last_sync = serializers.DateTimeField()
