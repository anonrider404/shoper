from django.db import models
from django.contrib.auth.models import User
# Create your models here.
class Girl(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    username = models.CharField(max_length=20, unique=True)
    photo = models.ImageField(upload_to='girls/', null=True)
    title = models.CharField(max_length=100)
    description = models.TextField(max_length=700, null=True)
    phone = models.CharField(max_length=15)
    date = models.DateField(auto_now_add=True)

    def __str__(self) -> str:
        return self.username