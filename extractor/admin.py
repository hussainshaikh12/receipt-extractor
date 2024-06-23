from django.contrib import admin

# Register your models here.
from .models import CustomUser, Receipt

admin.site.register(CustomUser)
admin.site.register(Receipt)