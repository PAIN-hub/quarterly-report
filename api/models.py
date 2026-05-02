"""
Database models for MDA Report Portal.
Includes User, Report, AuditLog, Backup models with full audit trail support.
"""

from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
from django.db.models import JSONField
import uuid
import hashlib


class UserManager(BaseUserManager):
    """Custom user manager for Access ID authentication."""
    
    def create_user(self, access_id, password, **extra_fields):
        """Create and save a regular user."""
        if not access_id:
            raise ValueError('The Access ID must be set')
        
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_active', True)
        
        user = self.model(access_id=access_id, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, access_id, password, **extra_fields):
        """Create and save a superuser."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'SYSTEM_ADMIN')
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(access_id, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom user model with Access ID authentication and role-based access control.
    """
    ROLE_CHOICES = (
        ('MDA_USER', 'MDA User'),
        ('MDA_ADMIN', 'MDA Administrator'),
        ('REGIONAL_OFFICER', 'Regional Officer'),
        ('SYSTEM_ADMIN', 'System Administrator'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    access_id = models.CharField(max_length=20, unique=True, db_index=True)  # e.g., KTS-MDA-001
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True, null=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='MDA_USER')
    mda_name = models.CharField(max_length=255, blank=True, null=True)  # MDA they belong to
    
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    
    date_joined = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(null=True, blank=True)
    last_sync = models.DateTimeField(null=True, blank=True)  # For offline tracking
    
    objects = UserManager()
    
    USERNAME_FIELD = 'access_id'
    REQUIRED_FIELDS = ['name']
    
    class Meta:
        db_table = 'users'
        ordering = ['-date_joined']
        indexes = [
            models.Index(fields=['access_id']),
            models.Index(fields=['is_active']),
            models.Index(fields=['role']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.access_id})"
    
    def get_full_name(self):
        return self.name
    
    def get_short_name(self):
        return self.access_id


class Report(models.Model):
    """
    Report model with version tracking and conflict resolution support.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reports')
    mda_name = models.CharField(max_length=255, db_index=True)
    
    # Content fields - JSON for flexibility
    data = JSONField(default=dict)
    
    # Versioning and timestamps
    version = models.IntegerField(default=1, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_modified = models.DateTimeField(auto_now=True, db_index=True)
    last_modified_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='modified_reports'
    )
    
    # Sync tracking
    synced_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)  # Soft delete for audit trail
    
    class Meta:
        db_table = 'reports'
        ordering = ['-last_modified']
        indexes = [
            models.Index(fields=['user', 'is_deleted']),
            models.Index(fields=['mda_name', 'is_deleted']),
            models.Index(fields=['last_modified']),
            models.Index(fields=['version']),
        ]
    
    def __str__(self):
        return f"{self.mda_name} - v{self.version} ({self.user.name})"


class ReportVersion(models.Model):
    """
    Complete history of report versions for conflict resolution and audit.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report = models.ForeignKey(Report, on_delete=models.CASCADE, related_name='versions')
    version_number = models.IntegerField(db_index=True)
    data = JSONField()  # Complete snapshot
    modified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    change_description = models.CharField(max_length=255, blank=True)
    
    class Meta:
        db_table = 'report_versions'
        unique_together = ('report', 'version_number')
        ordering = ['-version_number']
        indexes = [
            models.Index(fields=['report', 'version_number']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.report.mda_name} - Version {self.version_number}"


class AuditLog(models.Model):
    """
    Complete audit trail of all system changes for compliance and debugging.
    """
    ACTION_CHOICES = (
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
        ('SYNC', 'Sync'),
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
        ('CONFLICT', 'Conflict Detected'),
        ('EXPORT', 'Data Export'),
        ('BACKUP', 'Backup Created'),
        ('RESTORE', 'Data Restored'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, db_index=True)
    resource_type = models.CharField(max_length=50)  # 'report', 'user', 'backup', etc.
    resource_id = models.CharField(max_length=255, db_index=True)
    
    # What changed
    changes = JSONField(default=dict)  # {field: {old: value, new: value}}
    description = models.TextField(blank=True)
    
    # Metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        db_table = 'audit_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['action', 'created_at']),
            models.Index(fields=['resource_type', 'resource_id']),
        ]
    
    def __str__(self):
        return f"{self.action} - {self.resource_type}:{self.resource_id}"


class Backup(models.Model):
    """
    Backup snapshots for data recovery and historical audits.
    """
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('RESTORED', 'Restored'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    backup_name = models.CharField(max_length=255, unique=True, db_index=True)
    description = models.TextField(blank=True)
    
    # Backup data
    data = JSONField()  # {users, reports, audit_logs}
    data_hash = models.CharField(max_length=64, unique=True)  # SHA-256 for integrity
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    backup_type = models.CharField(max_length=20, default='MANUAL')  # MANUAL, SCHEDULED, AUTOMATED
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    size_bytes = models.BigIntegerField()  # For monitoring
    
    # Restoration tracking
    restored_at = models.DateTimeField(null=True, blank=True)
    restored_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='restored_backups'
    )
    
    class Meta:
        db_table = 'backups'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['data_hash']),
        ]
    
    def __str__(self):
        return f"Backup {self.backup_name} - {self.status}"
    
    def verify_integrity(self):
        """Verify backup integrity using hash."""
        import json
        backup_json = json.dumps(self.data, sort_keys=True)
        computed_hash = hashlib.sha256(backup_json.encode()).hexdigest()
        return computed_hash == self.data_hash


class SyncConflict(models.Model):
    """
    Track sync conflicts between offline clients and server for resolution.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report = models.ForeignKey(Report, on_delete=models.CASCADE, related_name='sync_conflicts')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # Conflict details
    local_version = models.IntegerField()
    server_version = models.IntegerField()
    local_data = JSONField()
    server_data = JSONField()
    resolution = models.CharField(
        max_length=20,
        choices=[('OVERWRITE', 'Overwrite'), ('KEEP_SERVER', 'Keep Server'), ('PENDING', 'Pending')],
        default='PENDING'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'sync_conflicts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['report', 'resolved_at']),
            models.Index(fields=['user', 'created_at']),
        ]
    
    def __str__(self):
        return f"Conflict - {self.report.mda_name} (v{self.local_version} vs v{self.server_version})"
