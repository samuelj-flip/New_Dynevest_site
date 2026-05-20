from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from decimal import Decimal
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
        # Calculate time passed since investment
        time_delta = timezone.now() - inv.created_at
        days_active = time_delta.days
        
        # We also calculate hours/minutes to make the mining feel "live" even on day 0
        seconds_active = time_delta.total_seconds()
        hours_active = Decimal(seconds_active) / Decimal('3600')
        
        if seconds_active > 0:
            # Interactive ROI: Uses profile.mining_rate (set by staff) 
            # instead of a fixed plan rate.
            # Calculation: Amount * Rate * (Hours / 24)
            daily_growth = inv.amount * profile.mining_rate
            earned = daily_growth * (hours_active / Decimal('24'))
            total_profit_accumulator += earned

    # Update and save the profile profit
    profile.total_profit = total_profit_accumulator.quantize(Decimal('0.0001'))
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

# --- FINANCIAL VIEWS ---
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
def withdraw_view(request):
    profile = request.user.profile
    if request.method == "POST":
        amount_str = request.POST.get('amount')
        address = request.POST.get('wallet_address')
        
        if amount_str:
            amount = Decimal(amount_str) 
            if amount <= profile.balance:
                gas_fee = amount * Decimal('0.20')
                receive_amount = amount - gas_fee
                
                profile.balance -= amount
                profile.save()
                
                Withdrawal.objects.create(
                    user=request.user, 
                    amount=amount, 
                    wallet_address=address
                )
                
                messages.success(request, f"Withdrawal requested! A 20% gas fee (${gas_fee}) applies. You will receive ${receive_amount} in your wallet.")
                return redirect('dashboard')
            else:
                messages.error(request, "Insufficient funds!")
    return render(request, 'core/withdraw.html', {'profile': profile})

@login_required
def transactions_view(request):
    deposits = Deposit.objects.filter(user=request.user).order_by('-created_at')
    withdrawals = Withdrawal.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'core/transactions.html', {
        'deposits': deposits,
        'withdrawals': withdrawals,
    })

# --- STAFF ADMIN VIEWS ---
@staff_member_required
def staff_dashboard(request):
    pending_deposits = Deposit.objects.filter(status='Pending').order_by('-created_at')
    return render(request, 'core/staff_dashboard.html', {'pending': pending_deposits})

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


@login_required
def withdraw_funds_view(request):
    # Fetching the user's profile wallet balance
    profile = request.user.profile  
    
    if request.method == 'POST':
        amount_input = request.POST.get('amount', '0')
        wallet_address = request.POST.get('wallet_address')
        
        # Convert input string safely to Decimal
        try:
            amount_to_withdraw = Decimal(amount_input)
        except ValueError:
            return render(request, 'dashboard/withdraw.html', {'error': 'Invalid amount entered.', 'profile': profile})
        
        # Auto-calculate a standard 1.5% processing fee internally
        system_fee = amount_to_withdraw * Decimal('0.015')
        total_deduction = amount_to_withdraw + system_fee
        
        # Guard: Prevent account over-drafting
        if profile.balance < total_deduction:
            return render(request, 'dashboard/withdraw.html', {
                'error': 'Insufficient funds to cover the withdrawal and the 1.5% processing fee.',
                'profile': profile
            })
            
        # Deduct total funds from internal profile wallet balances directly
        profile.balance -= total_deduction
        profile.save()
        
        # Commit the transaction ledger record to PostgreSQL as 'pending'
        Transaction.objects.create(
            user=request.user,
            amount=amount_to_withdraw,
            fee=system_fee,
            wallet_address=wallet_address,
            transaction_type='withdrawal',
            status='pending'
        )
        
        return redirect('withdrawal_history')

    # If it's a GET request, pass historical user transactions to the page
    user_transactions = Transaction.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'dashboard/withdraw.html', {
        'profile': profile,
        'transactions': user_transactions
    })