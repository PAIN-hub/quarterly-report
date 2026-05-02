"""
Django admin configuration for MDA Report Portal.
Provides admin interface for managing users, reports, and audit logs.
"""

from django import forms
from django.contrib import admin
from django.utils.html import format_html
from .models import User, Report, ReportVersion, AuditLog, Backup, SyncConflict

class UserAdminForm(forms.ModelForm):
    """
    Custom form to securely render the password field in the Django admin.
    """
    password = forms.CharField(
        widget=forms.PasswordInput(render_value=True),
        required=False,
        help_text="Leave blank to keep the current password, or enter a new one to change it."
    )

    class Meta:
        model = User
        fields = '__all__'


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    form = UserAdminForm
    list_display = ['access_id', 'name', 'role', 'mda_name', 'is_active', 'date_joined']
    list_filter = ['role', 'is_active', 'date_joined']
    search_fields = ['access_id', 'name', 'email', 'mda_name']
    readonly_fields = ['id', 'date_joined', 'last_login', 'last_sync']
    
    fieldsets = (
        ('Account Information', {
            'fields': ('id', 'access_id', 'name', 'email', 'password')
        }),
        ('Organization', {
            'fields': ('mda_name', 'role')
        }),
        ('Status', {
            'fields': ('is_active', 'is_staff', 'is_superuser')
        }),
        ('Timestamps', {
            'fields': ('date_joined', 'last_login', 'last_sync'),
            'classes': ('collapse',)
        }),
    )

    def save_model(self, request, obj, form, change):
        """
        Hash the password when creating or updating the user object.
        """
        if 'password' in form.cleaned_data and form.cleaned_data['password']:
            obj.set_password(form.cleaned_data['password'])
        super().save_model(request, obj, form, change)


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ['mda_name', 'user', 'version', 'status_badge', 'last_modified']
    list_filter = ['is_deleted', 'version', 'created_at', 'last_modified']
    search_fields = ['mda_name', 'user__name']
    readonly_fields = ['id', 'created_at', 'updated_at', 'last_modified']
    
    fieldsets = (
        ('Report Information', {
            'fields': ('id', 'user', 'mda_name')
        }),
        ('Content', {
            'fields': ('data',),
            'classes': ('collapse',)
        }),
        ('Versioning', {
            'fields': ('version', 'last_modified_by')
        }),
        ('Status', {
            'fields': ('is_deleted', 'synced_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'last_modified'),
            'classes': ('collapse',)
        }),
    )
    
    def status_badge(self, obj):
        if obj.is_deleted:
            return format_html(
                '<span style="color: red;">&#x2717; Deleted</span>'
            )
        return format_html(
            '<span style="color: green;">&#x2713; Active</span>'
        )
    status_badge.short_description = 'Status'


@admin.register(ReportVersion)
class ReportVersionAdmin(admin.ModelAdmin):
    list_display = ['report', 'version_number', 'modified_by', 'created_at']
    list_filter = ['created_at']
    search_fields = ['report__mda_name', 'modified_by__name']
    readonly_fields = ['id', 'created_at']


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['action', 'resource_type', 'user', 'created_at']
    list_filter = ['action', 'resource_type', 'created_at']
    search_fields = ['user__name', 'resource_id', 'description']
    readonly_fields = ['id', 'created_at']
    date_hierarchy = 'created_at'


@admin.register(Backup)
class BackupAdmin(admin.ModelAdmin):
    list_display = ['backup_name', 'status', 'backup_type', 'created_by', 'created_at']
    list_filter = ['status', 'backup_type', 'created_at']
    search_fields = ['backup_name', 'description']
    readonly_fields = ['id', 'data_hash', 'created_at', 'restored_at'] # Added to keep original functionality
    
    fieldsets = (
        ('Backup Information', {
            'fields': ('id', 'backup_name', 'description')
        }),
        ('Status', {
            'fields': ('status', 'backup_type')
        }),
        ('Data Integrity', {
            'fields': ('data_hash', 'size_bytes'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'restored_by', 'restored_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(SyncConflict)
class SyncConflictAdmin(admin.ModelAdmin):
    list_display = ['report', 'user', 'resolution', 'local_version', 'server_version', 'created_at']
    list_filter = ['resolution', 'created_at']
    search_fields = ['report__mda_name', 'user__name']
    readonly_fields = ['id', 'created_at']
    
    fieldsets = (
        ('Conflict Information', {
            'fields': ('id', 'report', 'user')
        }),
        ('Versions', {
            'fields': ('local_version', 'server_version')
        }),
        ('Data', {
            'fields': ('local_data', 'server_data'),
            'classes': ('collapse',)
        }),
        ('Resolution', {
            'fields': ('resolution', 'created_at', 'resolved_at')
        }),
    )
