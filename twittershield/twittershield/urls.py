"""twittershield URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.conf.urls import url
from website.views import index, toxicity_score, poll_status, get_following, toxicity_score_higher_threshold, poll_with_higher_threshold


urlpatterns = [
    path('admin/', admin.site.urls),
    url(r'^$', index),
    url(r'^toxicityscore', toxicity_score),
    url(r'^toxicity_score_higher_threshold', toxicity_score_higher_threshold),
    url(r'^poll_with_higher_threshold', poll_with_higher_threshold),
    url(r'^poll_status', poll_status),
    url(r'^get_following', get_following)
]

