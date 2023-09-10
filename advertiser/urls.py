from django.urls import path
from . import views

urlpatterns = [
	path('', views.indexView, name = 'index'),
	path('add/', views.addGirl, name = 'add'),
	path('signup/', views.RegisterView, name = 'signup'),
	path('login/', views.loginView, name = 'login'),
	path('logout/', views.logoutView, name = 'logout'),
    path('view/<int:pk>/',views.viewView, name='view'),
    path('edit/<int:pk>/',views.editView, name='edit'),
	path('girl/<int:girl_id>/delete/', views.delete_girl, name='delete'),
    ]