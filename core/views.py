from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from decimal import Decimal
from django.contrib.auth.models import User
from .models import Profile, Plan, Deposit, Investment, Withdrawal, Transaction
from django.core.mail import send_mail

# --- PUBLIC VIEWS ---
def home_view(request):
    return render(request, 'core/home.html')

def register_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        email_from_html = request.POST.get('email')
        
        if form.is_valid():
            user = form.save(commit=False)
            if email_from_html:
                user.email = email_from_html
            user.save()
            
            Profile.objects.get_or_create(user=user)

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
            # Calculation: Amount * Rate * (Hours / 24)
            daily_growth = inv.amount * profile.mining_rate
            earned = daily_growth * (hours_active / Decimal('24'))
            total_profit_accumulator += earned

    # CLIENT REQUIREMENT CRITICAL FIX: 
    # Calculate the newly generated profit delta and award it directly to the withdrawable mining pool
    new_profit = total_profit_accumulator.quantize(Decimal('0.0001'))
    profit_difference = new_profit - profile.total_profit

    if profit_difference > 0:
        profile.mining_balance += profit_difference

    # Update historical tracking stats
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
        return redirect('dashboard')
    return render(request, 'core/deposit.html')


@login_required
def withdraw_funds_view(request):
    profile = request.user.profile  
    
    if request.method == 'POST':
        amount_input = request.POST.get('amount', '0')
        wallet_address = request.POST.get('wallet_address')
        
        try:
            amount_to_withdraw = Decimal(amount_input)
        except (ValueError, TypeError):
            return render(request, 'core/withdraw.html', {
                'error': 'Invalid amount format entered.', 
                'profile': profile,
                'transactions': Withdrawal.objects.filter(user=request.user).order_by('-created_at')
            })
        
        # 🛠️ CLIENT REQUIREMENT: Intercept Withdrawal with External Deposit Restriction
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
                'transactions': Withdrawal.objects.filter(user=request.user).order_by('-created_at')
            })

        system_fee = amount_to_withdraw * Decimal('0.015')
        total_deduction = amount_to_withdraw + system_fee
        
        if profile.mining_balance < total_deduction:
            return render(request, 'core/withdraw.html', {
                'error': f'Insufficient mining earnings. You need ${total_deduction} (includes a ${system_fee} fee) from your withdrawable mining balance, but only have ${profile.mining_balance}.',
                'profile': profile,
                'transactions': Withdrawal.objects.filter(user=request.user).order_by('-created_at')
            })
            
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

    user_withdrawals = Withdrawal.objects.filter(user=request.user).order_by('-created_at')
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
    
    # Force profile generation for any trailing user accounts across the system
    all_users = User.objects.all()
    for user in all_users:
        Profile.objects.get_or_create(user=user)
        
    user_profiles = Profile.objects.select_related('user').order_by('user__username')
    
    return render(request, 'core/staff_dashboard.html', {
        'pending_deposits': pending_deposits,
        'pending_withdrawals': pending_withdrawals,
        'user_profiles': user_profiles
    })


@staff_member_required
def manipulate_user(request, profile_id):
    """
    Unified Portal Control Endpoint: Allows modifying all central user profile fields
    directly from the main dashboard screen interface.
    """
    if request.method == "POST":
        profile = get_object_or_404(Profile, id=profile_id)
        user = profile.user
        
        balance_input = request.POST.get('balance')
        mining_balance_input = request.POST.get('mining_balance')
        mining_rate_input = request.POST.get('mining_rate')
        
        # New account metadata inputs
        email_input = request.POST.get('email')
        is_active_input = request.POST.get('is_active')
        
        # 🛠️ New Client Requirement Controls
        require_deposit_input = request.POST.get('require_external_deposit')
        deposit_percentage_input = request.POST.get('required_deposit_percentage')

        try:
            if balance_input is not None:
                profile.balance = Decimal(balance_input)
            if mining_balance_input is not None:
                profile.mining_balance = Decimal(mining_balance_input)
            if mining_rate_input is not None:
                profile.mining_rate = Decimal(mining_rate_input)
            
            # Update Client Requirement Flags
            if require_deposit_input is not None:
                profile.require_external_deposit = (require_deposit_input == "True")
            if deposit_percentage_input is not None:
                profile.required_deposit_percentage = int(deposit_percentage_input)
            
            # Save User model details directly from the single portal view
            if email_input is not None:
                user.email = email_input
            
            # Toggle user login permissions (Suspended vs Active)
            user.is_active = True if is_active_input == "True" else False
                
            user.save()
            profile.save()
            messages.success(request, f"Successfully updated all details for user: {user.username}!")
        except (ValueError, TypeError):
            messages.error(request, "Failed to update user parameters. Verify your numeric entries.")
            
    return redirect('staff_dashboard')


@staff_member_required
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