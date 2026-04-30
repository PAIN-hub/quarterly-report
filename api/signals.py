"""
Django signals for MDA Report Portal.
Automatic audit logging and data validation.
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from .models import User, Report
from .utils import log_audit
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def user_post_save(sender, instance, created, **kwargs):
    """Log user creation."""
    if created:
        try:
            log_audit(
                user=instance,
                action='CREATE',
                resource_type='user',
                resource_id=str(instance.id),
                description=f'User created: {instance.access_id}'
            )
        except Exception as e:
            logger.error(f'Failed to log user creation: {e}')


@receiver(post_save, sender=Report)
def report_post_save(sender, instance, created, **kwargs):
    """Log report changes and update sync timestamp."""
    try:
        if hasattr(instance, '_skip_audit'):
            return
        
        # Update last_sync on changes
        if not created:
            instance.synced_at = timezone.now()
            instance.save(update_fields=['synced_at'])
    
    except Exception as e:
        logger.error(f'Failed to process report save signal: {e}')
