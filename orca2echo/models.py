from django.db import models

# Create your models here.

# class Movie(models.Model):
#     id = models.IntegerField(primary_key=True)
#     title = models.CharField(max_length=200, null=False, blank=False)
#     overview = models.TextField(null=True, blank=True)
#     genres = models.CharField(max_length=200, null=True, blank=True)
#     cast = models.TextField(null=True, blank=True)
#     director = models.CharField(max_length=200, null=True, blank=True)
#     release_date = models.DateField(null=True, blank=True)
#     languages = models.CharField(max_length=200, null=True, blank=True)
    
class Otp(models.Model):
    otp = models.IntegerField(null=True)  # Store OTP, typically a 6-digit integer
    email = models.EmailField(null=True, blank=True)  # Store the email address
    
