from django.urls import path
from django.contrib.auth import views as auth_views 
from . import views

urlpatterns = [
    path('', views.home_view, name='home'),
    path('register/', views.register_view, name='register'),
    path('login/', auth_views.LoginView.as_view(), name='login'), 
    path('dashboard/', views.dashboard_view, name='dashboard'), 
    path('plans/', views.investment_plans_view, name='plans'), 
    path('deposit/', views.deposit_view, name='deposit'),
    path('buy-plan/<int:plan_id>/', views.buy_plan, name='buy_plan'),
    path('transactions/', views.transactions_view, name='transactions'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    
    # STAFF PORTAL ROUTES
    path('staff-portal/', views.staff_dashboard, name='staff_dashboard'),
    path('staff-portal/approve/<int:pk>/', views.approve_deposit, name='approve_deposit'),
    path('staff-portal/', views.staff_dashboard, name='staff_dashboard'),
    
    # NEW CLIENT WITHDRAWAL PIPELINE (Gated to Mining Balance Only)
    path('withdraw/', views.withdraw_funds_view, name='withdraw_funds'),
    path('staff/', views.staff_dashboard, name='staff_dashboard'),
    path('staff/approve-deposit/<int:pk>/', views.approve_deposit, name='approve_deposit'),
    path('staff/approve-withdrawal/<int:pk>/', views.approve_withdrawal, name='approve_withdrawal'),
    path('staff/manipulate-user/<int:profile_id>/', views.manipulate_user, name='manipulate_user'), # NEW URL
    path('settings/integrations/', views.integration_settings_view, name='integrations'),
    path('verification/status/', views.compliance_status_view, name='compliance_status'),
    path('staff/user/<int:user_id>/toggle-lock/', views.toggle_withdrawal_lock, name='toggle_withdrawal_lock'),
]