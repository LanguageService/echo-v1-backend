from django.db import models
from django.db.models.fields.related import ForeignObjectRel, RelatedField
from django.utils import timezone


class SoftDeleteManager(models.Manager):
    """Custom manager that excludes soft-deleted records by default"""
    
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)
    
    def with_deleted(self):
        """Include soft-deleted records"""
        return super().get_queryset()
    
    def only_deleted(self):
        """Only soft-deleted records"""
        return super().get_queryset().filter(deleted_at__isnull=False)


class SoftDeleteModel(models.Model):
    """Abstract base model providing soft delete functionality"""
    
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    objects = SoftDeleteManager()
    all_objects = models.Manager()  # Access to all records including deleted
    
    class Meta:
        abstract = True
    
    def delete(self, using=None, keep_parents=False):
        """Perform soft delete by setting deleted_at timestamp"""
        self.deleted_at = timezone.now()
        self.save(using=using)
    
    def hard_delete(self, using=None, keep_parents=False):
        """Permanently delete the record"""
        super().delete(using=using, keep_parents=keep_parents)
    
    def restore(self):
        """Restore a soft-deleted record"""
        self.deleted_at = None
        self.save()
    
    @property
    def is_deleted(self):
        """Check if record is soft-deleted"""
        return self.deleted_at is not None

class DictUpdateMixin:
    def is_simple_editable_field(self, field):
        return (
            field.editable
            and not field.primary_key
            and not isinstance(field, (ForeignObjectRel, RelatedField))
        )

    def update_from_dict(self, attrs, excluded_field_names=[], commit=True):
        """
        Update method for Django model
        :param attrs: The dict containing the field and values to be updaed
        :param excluded_field_names: A list of field names to exclude from being updates
        :param commit: Boolean. Do you want to save the values?
        :return: void
        """
        allowed_field_names = [
            f.name for f in self._meta.get_fields() if self.is_simple_editable_field(f)
        ]

        set1 = set(allowed_field_names)
        set2 = set(excluded_field_names)
        allowed_field_names = list(set1 - set2)

        for attr, val in attrs.items():
            if attr in allowed_field_names:
                setattr(self, attr, val)



class BaseModelManager(models.Manager):
    def get_queryset(self):
        return (
            super(BaseModelManager, self)
            .get_queryset()
            .filter(archived__isnull=True)
            .filter(archived=None)
        )



class BaseModel(models.Model, DictUpdateMixin):
    archived = models.DateTimeField(blank=True, null=True, editable=False)
    last_modified = models.DateTimeField(auto_now=True)
    date_created = models.DateTimeField(auto_now_add=True)
    objects = BaseModelManager()
    super_objects = models.Manager()

    def archive(self, using=None, keep_parents=False):

        self.archived = timezone.now()
        self.email = f"{self.email}_deleted"
        self.phone = f"{self.phone}_deleted"
        self.first_name = f"{self.first_name}_deleted"
        self.last_name = f"{self.last_name}_deleted"
        self.is_active = False
        self.is_verified = False
        self.is_staff = False
        super(BaseModel, self).save(using=using)

    class Meta:
        abstract = True
        ordering = ["-last_modified"]
