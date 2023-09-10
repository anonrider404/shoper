from django.contrib import admin
from .models import Girl
# Register your models here.
models = [Girl]

for model in models:
    admin.site.register(model)