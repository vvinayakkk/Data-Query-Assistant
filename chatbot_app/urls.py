from django.urls import path
from . import views

urlpatterns = [
    path('', views.chatbot_home, name='chatbot_home'),
    path('get_response/', views.get_response, name='get_response'),
    path('add_data_source/', views.add_data_source, name='add_data_source'),
]
