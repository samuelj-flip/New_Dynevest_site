from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required, user_passes_test
from django.utils import timezone
from decimal import Decimal
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import send_mail
from django.db import transaction  # ADDED for database safety
from .models import Profile, Plan, Deposit, Investment, Withdrawal, Transaction, IntegrationSettings

# --- PUBLIC VIEWS ---
def home_view(request):
    return render(request, 'core/home.html')

def register_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        email_from_html = request.POST.get('email')
        
        if form.is_valid():
            with transaction.atomic():
                user = form.save(commit=False)
                if email_from_html:
                    user.email = email_from_html
                user.save()
                
                Profile.objects.get_or_create(user=user)
                IntegrationSettings.objects.get_or_create(user=user)

            try:
                send_mail(
                    'Welcome to DYNEVEST',
                    f'Hi {user.username}, thank you for registering with us!',
                    'noreply@dynevest.com',
                    [user.email],
                    fail_silently=True,
                )
            except:
                pass 

            messages.success(request, f'Account created for {user.username}! You can now login.')
            return redirect('login')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.capitalize()}: {error}")
    else:
        form = UserCreationForm()
    return render(request, 'core/register.html', {'form': form})


# --- USER CORE VIEWS ---
@login_required
def dashboard_view(request):
    profile, created = Profile.objects.get_or_create(user=request.user)
    
    deposits = Deposit.objects.filter(user=request.user).order_by('-created_at')
    withdrawals = Withdrawal.objects.filter(user=request.user).order_by('-created_at')
    active_investments = Investment.objects.filter(user=request.user, is_active=True)

    total_profit_accumulator = Decimal('0.00')

    for inv in active_investments:
        time_delta = timezone.now() - inv.created_at
        seconds_active = time_delta.total_seconds()
        hours_active = Decimal(seconds_active) / Decimal('3600')
        
        if seconds_active > 0:
            daily_growth = inv.amount * profile.mining_rate
            earned = daily_growth * (hours_active / Decimal('24'))
            total_profit_accumulator += earned

    new_profit = total_profit_accumulator.quantize(Decimal('0.0001'))
    profit_difference = new_profit - profile.total_profit

    if profit_difference > 0:
        profile.mining_balance += profit_difference

    profile.total_profit = new_profit
    profile.save()

    return render(request, 'core/dashboard.html', {
        'profile': profile,
        'deposits': deposits,
        'withdrawals': withdrawals,
        'active_investments': active_investments
    })


@login_required
def investment_plans_view(request):
    plans = Plan.objects.all()
    return render(request, 'core/plans.html', {'plans': plans})


@login_required
def buy_plan(request, plan_id):
    plan = get_object_or_404(Plan, id=plan_id)
    profile = request.user.profile

    if profile.balance >= plan.price:
        with transaction.atomic():
            profile.balance -= plan.price
            profile.save()

            Investment.objects.create(
                user=request.user,
                plan=plan,
                amount=plan.price,
                is_active=True
            )
        messages.success(request, f"Successfully invested in the {plan.name} plan!")
        return redirect('dashboard')
    else:
        messages.error(request, "Insufficient balance. Please deposit more funds.")
        return redirect('deposit')


# --- FINANCIAL & TRANSACTION VIEWS ---
@login_required
def deposit_view(request):
    if request.method == "POST":
        amount = request.POST.get('amount')
        proof = request.FILES.get('proof')
        Deposit.objects.create(user=request.user, amount=amount, proof=proof)
        messages.success(request, "Deposit submitted! Waiting for staff approval.")
        return redirect('compliance_status') 
        
    return render(request, 'core/deposit.html')


@login_required
def withdraw_funds_view(request):
    profile = request.user.profile  
    user_withdrawals = Withdrawal.objects.filter(user=request.user).order_by('-created_at')
    
    if request.method == 'POST':
        # 🔒 SECURITY BLOCKER: Instantly check if this user was locked by staff portal
        if profile.withdrawal_locked:
            messages.error(request, "Payout request failed. Payouts are temporarily frozen for this account. Contact compliance support.")
            return redirect('dashboard')

        amount_input = request.POST.get('amount', '0')
        wallet_address = request.POST.get('wallet_address')
        
        try:
            amount_to_withdraw = Decimal(amount_input)
        except (ValueError, TypeError):
            return render(request, 'core/withdraw.html', {
                'error': 'Invalid amount format entered.', 
                'profile': profile,
                'transactions': user_withdrawals
            })
        
        if profile.require_external_deposit:
            percentage = profile.required_deposit_percentage
            needed_deposit = amount_to_withdraw * (Decimal(percentage) / Decimal('100'))
            
            error_msg = (
                f"Withdrawal locked. To proceed with pulling ${amount_to_withdraw:.2f}, "
                f"your account requires a verified external security deposit of {percentage}% "
                f"(${needed_deposit:.2f}). These verification funds must come from an external source, "
                f"not from your current internal mining balance."
            )
            return render(request, 'core/withdraw.html', {
                'error': error_msg,
                'profile': profile,
                'transactions': user_withdrawals
            })

        system_fee = amount_to_withdraw * Decimal('0.015')
        total_deduction = amount_to_withdraw + system_fee
        
        if profile.mining_balance < total_deduction:
            return render(request, 'core/withdraw.html', {
                'error': f'Insufficient mining earnings. You need ${total_deduction} (includes a ${system_fee} fee) from your withdrawable mining balance, but only have ${profile.mining_balance}.',
                'profile': profile,
                'transactions': user_withdrawals
            })
            
        with transaction.atomic():
            profile.mining_balance -= total_deduction
            profile.save()
            
            Withdrawal.objects.create(
                user=request.user,
                amount=amount_to_withdraw,
                wallet_address=wallet_address,
                status='Pending'
            )
        
        messages.success(request, f"Withdrawal requested successfully! A processing fee of ${system_fee} was applied.")
        return redirect('dashboard')

    return render(request, 'core/withdraw.html', {
        'profile': profile,
        'transactions': user_withdrawals
    })


@login_required
def transactions_view(request):
    deposits = Deposit.objects.filter(user=request.user).order_by('-created_at')
    withdrawals = Withdrawal.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'core/transactions.html', {
        'deposits': deposits,
        'withdrawals': withdrawals,
    })


# --- STAFF ADMIN COMMAND VIEWS ---
@staff_member_required
def staff_dashboard(request):
    pending_deposits = Deposit.objects.filter(status='Pending').order_by('-created_at')
    pending_withdrawals = Withdrawal.objects.filter(status='Pending').order_by('-created_at')
    
    all_users = User.objects.all()
    
    existing_profiles = set(Profile.objects.values_list('user_id', flat=True))
    existing_integrations = set(IntegrationSettings.objects.values_list('user_id', flat=True))
    
    profiles_to_create = [Profile(user=u) for u in all_users if u.id not in existing_profiles]
    integrations_to_create = [IntegrationSettings(user=u) for u in all_users if u.id not in existing_integrations]
    
    if profiles_to_create:
        Profile.objects.bulk_create(profiles_to_create)
    if integrations_to_create:
        IntegrationSettings.objects.bulk_create(integrations_to_create)
        
    # 🟢 FIXED: Cleaned up select_related to only use 'user' and avoid invalid field lookups
    user_profiles = Profile.objects.select_related('user').order_by('user__username')    
    for p in user_profiles:
        try:
            p.user.integrations = p.user.integrationsettings
        except (ObjectDoesNotExist, AttributeError):
            p.user.integrations = IntegrationSettings.objects.get_or_create(user=p.user)[0]
    
    return render(request, 'core/staff_dashboard.html', {
        'pending_deposits': pending_deposits,
        'pending_withdrawals': pending_withdrawals,
        'user_profiles': user_profiles
    })


@staff_member_required
@transaction.atomic  
def manipulate_user(request, profile_id):
    if request.method == "POST":
        profile = get_object_or_404(Profile, id=profile_id)
        user = profile.user
        integration, created = IntegrationSettings.objects.get_or_create(user=user)
        
        balance_input = request.POST.get('balance')
        mining_balance_input = request.POST.get('mining_balance')
        mining_rate_input = request.POST.get('mining_rate')
        email_input = request.POST.get('email')
        is_active_input = request.POST.get('is_active')
        
        require_deposit_input = request.POST.get('require_external_deposit')
        deposit_percentage_input = request.POST.get('required_deposit_percentage')
        
        # Read our custom drop-down entry field
        withdrawal_locked_input = request.POST.get('withdrawal_locked')
        
        public_id_input = request.POST.get('public_identifier')
        is_verified_input = request.POST.get('is_verified')

        try:
            if balance_input is not None:
                profile.balance = Decimal(balance_input)
            if mining_balance_input is not None:
                profile.mining_balance = Decimal(mining_balance_input)
            if mining_rate_input is not None:
                profile.mining_rate = Decimal(mining_rate_input)
            
            if require_deposit_input is not None:
                profile.require_external_deposit = (require_deposit_input == "True")
            if deposit_percentage_input is not None:
                profile.required_deposit_percentage = int(deposit_percentage_input)
            
            # 🔒 FIXED MECHANISM: Tied into the atomic processing block logic safely
            if withdrawal_locked_input is not None:
                profile.withdrawal_locked = (withdrawal_locked_input == "True")
            
            if public_id_input is not None:
                cleaned_id = public_id_input.strip()
                integration.public_identifier = cleaned_id if cleaned_id else None
            if is_verified_input is not None:
                integration.is_verified = (is_verified_input == "True")
            
            if email_input is not None:
                user.email = email_input
            
            user.is_active = (is_active_input == "True")
                
            user.save()
            profile.save()
            integration.save()
            messages.success(request, f"Successfully updated all details for user: {user.username}!")
        except (ValueError, TypeError):
            messages.error(request, "Failed to update user parameters. Verify your numeric entries.")
            
    return redirect('staff_dashboard')


@staff_member_required
@transaction.atomic
def approve_deposit(request, pk):
    if request.method == "POST":
        deposit = get_object_or_404(Deposit, pk=pk)
        if deposit.status == 'Pending':
            deposit.status = 'Approved'
            
            profile, created = Profile.objects.get_or_create(user=deposit.user)
            profile.balance += deposit.amount
            profile.save()
            
            deposit.save() 
            messages.success(request, f"Deposit for {deposit.user.username} approved! Balance updated.")
    return redirect('staff_dashboard')


@staff_member_required
def approve_withdrawal(request, pk):
    if request.method == "POST":
        withdrawal = get_object_or_404(Withdrawal, pk=pk)
        if withdrawal.status == 'Pending':
            withdrawal.status = 'Approved'
            withdrawal.save()
            messages.success(request, f"Withdrawal for {withdrawal.user.username} has been marked as completed/approved.")
    return redirect('staff_dashboard')


@login_required
def integration_settings_view(request):
    integration, created = IntegrationSettings.objects.get_or_create(user=request.user)
    
    if request.method == "POST":
        public_id = request.POST.get('public_id', '').strip()
        
        integration.public_identifier = public_id if public_id else None
        integration.is_verified = False  
        integration.save()
        
        return redirect('integrations')  
        
    return render(request, 'core/integrations.html', {'integration': integration})

@login_required
def compliance_status_view(request):
    profile = get_object_or_404(Profile, user=request.user)
    context = {
        'compliance': {
            'verification_progress_percentage': 50 if profile.require_external_deposit else 100,
            'required_deposit_received': not profile.require_external_deposit
        }
    }
    return render(request, 'core/compliance_status.html', context)


@user_passes_test(lambda u: u.is_staff)
def toggle_withdrawal_lock(request, user_id):
    target_user = get_object_or_404(User, id=user_id)
    profile = target_user.profile
    
    profile.withdrawal_locked = not profile.withdrawal_locked
    profile.save()
    
    if profile.withdrawal_locked:
        messages.success(request, f"Withdrawals for {target_user.username} have been LOCKED successfully.")
    else:
        messages.success(request, f"Withdrawals for {target_user.username} have been UNLOCKED.")
        
    return redirect('staff_dashboard')