from django.db import models
from django.core.validators import MinValueValidator

from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone



class CustomUserManager(BaseUserManager):
    def create_user(self, phone_number, password=None, **extra_fields):
        if not phone_number:
            raise ValueError('Users must have a phone number')
        user = self.model(phone_number=phone_number, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if password is None:
            raise ValueError('Superusers must have a password')

        user = self.create_user(phone_number, password, **extra_fields)
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)
        return user

class CustomUser(AbstractBaseUser, PermissionsMixin):  # Add PermissionsMixin here
    name = models.CharField(max_length=255, blank=True)
    phone_number = models.CharField(unique=True, max_length=15)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    email = models.EmailField(blank=True)
    

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = []

    objects = CustomUserManager()  # Link your CustomUserManager

    def __str__(self):
        return self.phone_number


class Receipt(models.Model):
    file = models.FileField(upload_to='receipts/')
    date = models.DateField(blank=True, null=True)
    vendor = models.CharField(max_length=255, blank=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, validators=[MinValueValidator(0)])
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)  # Link receipt to user

    def __str__(self):
        return f"Receipt: {self.vendor} - {self.date} (by {self.user.phone_number})"
