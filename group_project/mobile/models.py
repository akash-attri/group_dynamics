from django.contrib.auth.models import User
from django.db import models


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)
    gender = models.CharField(max_length=6)
    imei = models.CharField(max_length=15, blank=True)
    bt_name = models.CharField(max_length=30, blank=True)

    def __unicode__(self):
        return self.user.username


class LocationDensity(models.Model):
    location = models.CharField(max_length=12, blank=False)
    timestamp = models.DateTimeField(blank=False)
    density = models.IntegerField(default=0)


class GroupLocalization(models.Model):
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, blank=False)
    timestamp = models.DateTimeField(blank=False)
    group = models.CharField(max_length=100)


class DailyMatrix(models.Model):
    date = models.DateField(blank=False)
    group = models.TextField()


class Groups(models.Model):
    members = models.CharField(max_length=200)
    dynamic = models.CharField(max_length=6)
    type = models.CharField(max_length=7)
