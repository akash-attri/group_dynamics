from django.conf.urls import url, include
from .views import (
    UserCreateAPIView, UserLoginAPIView,
    assign_groups, density_api, strength_api, gender_api, groups_api
)
# from rest_framework import routers

# router = routers.DefaultRouter()
# router.register(r'register', Register, base_name='mobile_signup')

urlpatterns = [
    # url(r'^', include(router.urls)),
    url(r'^$', UserLoginAPIView.as_view(), name='login'),
    url(r'^login', UserLoginAPIView.as_view(), name='login'),
    url(r'^register', UserCreateAPIView.as_view(), name='register'),
    url(r'^groups', assign_groups, name='groups'),
    url(r'^density-api', density_api, name='density-api'),
    url(r'^gender-api', gender_api, name='gender-api'),
    url(r'^group-strength-api/(?P<uid>[0-9]+)/$', strength_api, name='group-strength-api'),
    url(r'^user-groups-api/(?P<uid>[0-9]+)/$', groups_api, name='user-groups-api')
]
