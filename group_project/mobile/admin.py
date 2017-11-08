# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib import admin
from .models import UserProfile, LocationDensity, GroupLocalization, DailyMatrix, Groups

admin.site.register(UserProfile)
admin.site.register(LocationDensity)
admin.site.register(GroupLocalization)
admin.site.register(DailyMatrix)
admin.site.register(Groups)
