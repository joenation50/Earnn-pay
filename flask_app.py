from flask import Flask, render_template_string, request, redirect, url_for, flash, session, jsonify
from datetime import datetime, timedelta
import random
import string
import os
import json
import uuid
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
from urllib.parse import urlparse

app = Flask(__name__)
app.secret_key = 'your-super-secret-key-change-this-12345'

# ==================== POSTGRESQL DATABASE CONFIGURATION ====================
# For local PostgreSQL:
# DATABASE_URL = 'postgresql://username:password@localhost/earnnpay_db'

# For production (Render, Heroku, etc.) - Use environment variable
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres:password@localhost/earnnpay_db')

# Parse the URL for SQLAlchemy
if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_size': 10,
    'pool_recycle': 3600,
    'pool_pre_ping': True,
}

# Create instance folder if it doesn't exist
app.instance_path = os.path.join(os.getcwd(), 'instance')
if not os.path.exists(app.instance_path):
    os.makedirs(app.instance_path)

db = SQLAlchemy(app)

# ==================== DATABASE MODELS ====================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    referral_code = db.Column(db.String(10), unique=True)
    referred_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    # Personal info
    full_name = db.Column(db.String(100), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    address = db.Column(db.String(200), nullable=True)
    date_of_birth = db.Column(db.Date, nullable=True)
    gender = db.Column(db.String(20), nullable=True)
    occupation = db.Column(db.String(100), nullable=True)
    profile_picture = db.Column(db.String(200), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    
    # Account info
    balance = db.Column(db.Float, default=0)
    commission_balance = db.Column(db.Float, default=0)
    trust_score = db.Column(db.Integer, default=0)
    tier = db.Column(db.String(20), default='FREE')
    daily_limit = db.Column(db.Integer, default=0)  # 0 means no tasks available
    daily_tasks_completed = db.Column(db.Integer, default=0)
    streak_days = db.Column(db.Integer, default=0)
    last_checkin = db.Column(db.DateTime, nullable=True)
    last_task_reset = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    is_banned = db.Column(db.Boolean, default=False)
    ban_reason = db.Column(db.Text, nullable=True)
    email_verified = db.Column(db.Boolean, default=False)
    
    # Bank details
    bank_name = db.Column(db.String(50), nullable=True)
    bank_account = db.Column(db.String(20), nullable=True)
    account_name = db.Column(db.String(100), nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    
    # Referral stats
    referral_bonus_earned = db.Column(db.Float, default=0)
    total_referrals = db.Column(db.Integer, default=0)
    theme = db.Column(db.String(10), default='light')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def generate_referral_code(self):
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    
    def get_next_tier(self):
        tiers = ['FREE', 'BEGINNER', 'EXPERT', 'LEGEND']
        current = self.tier
        if current in tiers:
            idx = tiers.index(current)
            if idx < len(tiers) - 1:
                return tiers[idx + 1]
        return None
    
    def get_profile_completion(self):
        fields = ['full_name', 'phone', 'address', 'bank_name', 'bank_account', 'account_name']
        completed = sum(1 for field in fields if getattr(self, field))
        return int((completed / len(fields)) * 100)
    
    def __repr__(self):
        return f'<User {self.username}>'

class Referral(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    referrer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    referred_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    bonus_paid = db.Column(db.Boolean, default=False)
    bonus_amount = db.Column(db.Float, default=500)
    verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    task_type = db.Column(db.String(50))
    reward = db.Column(db.Float, nullable=False)
    tier_required = db.Column(db.String(20), default='FREE')
    external_link = db.Column(db.String(200), nullable=True)
    daily_limit = db.Column(db.Integer, default=2)
    is_active = db.Column(db.Boolean, default=True)
    category = db.Column(db.String(50), default='General')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class TaskCompletion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    proof_text = db.Column(db.Text, nullable=True)
    proof_image = db.Column(db.String(200), nullable=True)
    is_verified = db.Column(db.Boolean, default=False)
    is_paid = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    tier = db.Column(db.String(20), nullable=True)
    transaction_id = db.Column(db.String(50), unique=True)
    sender_name = db.Column(db.String(100))
    payment_date = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    status = db.Column(db.String(20), default='PENDING')
    type = db.Column(db.String(20), default='UPGRADE')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'amount': self.amount,
            'tier': self.tier,
            'transaction_id': self.transaction_id,
            'sender_name': self.sender_name,
            'status': self.status,
            'date': self.created_at.strftime('%b %d, %Y %H:%M')
        }

class Withdrawal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    bank_name = db.Column(db.String(50))
    account_number = db.Column(db.String(20))
    account_name = db.Column(db.String(100))
    status = db.Column(db.String(20), default='PENDING')
    reference = db.Column(db.String(50), unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime, nullable=True)

class SupportTicket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='OPEN')
    priority = db.Column(db.String(20), default='MEDIUM')
    category = db.Column(db.String(50), default='General')
    admin_response = db.Column(db.Text, nullable=True)
    responded_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': User.query.get(self.user_id).username if User.query.get(self.user_id) else 'Unknown',
            'subject': self.subject,
            'message': self.message[:100] + '...' if len(self.message) > 100 else self.message,
            'status': self.status,
            'priority': self.priority,
            'date': self.created_at.strftime('%b %d, %Y %H:%M')
        }

class PaymentSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bank_name = db.Column(db.String(100), default='GTBank')
    account_name = db.Column(db.String(100), default='Earn Pay Labs Ltd')
    account_number = db.Column(db.String(20), default='0123456789')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class DailyBonus(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    bonus_amount = db.Column(db.Float, default=10)
    claimed_at = db.Column(db.DateTime, default=datetime.utcnow)

class Announcement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class UserActivity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ==================== CREATE TABLES ====================
with app.app_context():
    db.create_all()
    
    # Create default payment settings
    if PaymentSettings.query.count() == 0:
        default_settings = PaymentSettings(
            bank_name='GTBank',
            account_name='Earn Pay Labs Ltd',
            account_number='0123456789'
        )
        db.session.add(default_settings)
        db.session.commit()
    
    # Create default tasks
    if Task.query.count() == 0:
        default_tasks = [
            Task(title='Google Review', description='Leave a genuine 5-star review on Google', 
                 task_type='REVIEW', reward=50, tier_required='FREE'),
            Task(title='Ad Click', description='Visit a site and earn N40 instantly', 
                 task_type='ADS', reward=40, tier_required='FREE'),
            Task(title='Google Review', description='Leave a genuine 5-star review on Google', 
                 task_type='REVIEW', reward=150, tier_required='BEGINNER'),
            Task(title='Ad Click', description='Visit a site and earn N40 instantly', 
                 task_type='ADS', reward=120, tier_required='BEGINNER'),
            Task(title='Premium Review', description='Write detailed review for higher pay', 
                 task_type='REVIEW', reward=200, tier_required='BEGINNER'),
            Task(title='Survey', description='Complete survey and earn big', 
                 task_type='SURVEY', reward=180, tier_required='BEGINNER'),
            Task(title='Google Review', description='Leave a genuine 5-star review on Google', 
                 task_type='REVIEW', reward=450, tier_required='EXPERT'),
            Task(title='Ad Click', description='Visit a site and earn N40 instantly', 
                 task_type='ADS', reward=400, tier_required='EXPERT'),
            Task(title='Premium Review', description='Write detailed review for higher pay', 
                 task_type='REVIEW', reward=500, tier_required='EXPERT'),
            Task(title='Survey', description='Complete survey and earn big', 
                 task_type='SURVEY', reward=480, tier_required='EXPERT'),
            Task(title='Video Task', description='Watch video and earn', 
                 task_type='VIDEO', reward=350, tier_required='EXPERT'),
            Task(title='Google Review', description='Leave a genuine 5-star review on Google', 
                 task_type='REVIEW', reward=1000, tier_required='LEGEND'),
            Task(title='Ad Click', description='Visit a site and earn N40 instantly', 
                 task_type='ADS', reward=900, tier_required='LEGEND'),
            Task(title='Premium Review', description='Write detailed review for higher pay', 
                 task_type='REVIEW', reward=1100, tier_required='LEGEND'),
            Task(title='Survey', description='Complete survey and earn big', 
                 task_type='SURVEY', reward=1050, tier_required='LEGEND'),
            Task(title='Video Task', description='Watch video and earn', 
                 task_type='VIDEO', reward=950, tier_required='LEGEND'),
            Task(title='Expert Task', description='Complete expert level task', 
                 task_type='REVIEW', reward=1200, tier_required='LEGEND'),
            Task(title='Share & Earn', description='Share our website on social media and earn', 
                 task_type='SHARE', reward=100, tier_required='FREE'),
        ]
        for task in default_tasks:
            db.session.add(task)
        db.session.commit()

# ==================== CONFIGURATION ====================
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'admin123'
REFERRAL_BONUS = 500
MINIMUM_WITHDRAWAL = 10000
WITHDRAWAL_DAYS = [10, 30]

# ==================== TIER CONFIGURATION ====================
TIER_THRESHOLDS = {
    'FREE': 0,
    'BEGINNER': 100,
    'EXPERT': 300,
    'LEGEND': 700
}

TIER_TASKS = {
    'FREE': 0,      # No tasks for free tier
    'BEGINNER': 6,
    'EXPERT': 10,
    'LEGEND': 15
}

TIER_PRICES = {
    'BEGINNER': 1000,
    'EXPERT': 3500,
    'LEGEND': 10000
}

TIER_REWARDS = {
    'FREE': 0,
    'BEGINNER': 150,
    'EXPERT': 450,
    'LEGEND': 1000
}

# ==================== GOOGLE TRUSTED REVIEWS ====================
GOOGLE_REVIEWS = [
    {'name': 'Chidi O.', 'rating': 5, 'text': 'Absolutely love this platform! Earned N25,000 in my first month!', 'verified': True},
    {'name': 'Ngozi E.', 'rating': 5, 'text': 'The referral system is amazing. I got N500 when my friend joined!', 'verified': True},
    {'name': 'Emeka N.', 'rating': 4, 'text': 'Great platform for extra income. Tasks are simple and payments are fast.', 'verified': True},
    {'name': 'Aisha B.', 'rating': 5, 'text': 'I recommend EarnPay to everyone. Legit and reliable!', 'verified': True},
    {'name': 'Tunde A.', 'rating': 5, 'text': 'Upgraded to Expert tier and earning more now. Worth every naira!', 'verified': True},
]

FAKE_REVIEWS = [
    {'name': 'Chioma O.', 'review': 'I earned N15,000 in just 2 weeks! This platform is amazing!', 'rating': 5, 'time': '2 hours ago'},
    {'name': 'Emeka N.', 'review': 'The referral bonus is legit. I got N500 when my friend joined!', 'rating': 5, 'time': '5 hours ago'},
    {'name': 'Aisha B.', 'review': 'Best earning platform in Nigeria. Tasks are simple and payments are fast!', 'rating': 5, 'time': '1 day ago'},
    {'name': 'Tunde A.', 'review': 'Upgraded to Expert tier and earning N450 per review now. Worth it!', 'rating': 4, 'time': '2 days ago'},
    {'name': 'Ngozi E.', 'review': 'I love how easy it is to withdraw my earnings. Received in 24 hours!', 'rating': 5, 'time': '3 days ago'},
]

# ==================== HELPER FUNCTIONS ====================
def can_withdraw_today():
    now = datetime.now()
    day = now.day
    return day in WITHDRAWAL_DAYS

def get_next_withdrawal_date():
    now = datetime.now()
    current_day = now.day
    current_month = now.month
    current_year = now.year
    
    if current_day in WITHDRAWAL_DAYS:
        return now.date()
    
    for day in sorted(WITHDRAWAL_DAYS):
        if day > current_day:
            try:
                return datetime(current_year, current_month, day).date()
            except ValueError:
                continue
    
    next_month = current_month + 1
    next_year = current_year
    if next_month > 12:
        next_month = 1
        next_year += 1
    
    for day in sorted(WITHDRAWAL_DAYS):
        try:
            return datetime(next_year, next_month, day).date()
        except ValueError:
            continue
    
    return datetime(next_year, next_month, 10).date()

def get_payment_settings():
    settings = PaymentSettings.query.first()
    if not settings:
        settings = PaymentSettings(
            bank_name='GTBank',
            account_name='Earn Pay Labs Ltd',
            account_number='0123456789'
        )
        db.session.add(settings)
        db.session.commit()
    return settings

def get_tier_from_score(score):
    if score >= TIER_THRESHOLDS['LEGEND']:
        return 'LEGEND'
    elif score >= TIER_THRESHOLDS['EXPERT']:
        return 'EXPERT'
    elif score >= TIER_THRESHOLDS['BEGINNER']:
        return 'BEGINNER'
    else:
        return 'FREE'

def get_next_tier_info(current_tier, current_score):
    tiers = ['FREE', 'BEGINNER', 'EXPERT', 'LEGEND']
    if current_tier in tiers:
        idx = tiers.index(current_tier)
        if idx < len(tiers) - 1:
            next_tier = tiers[idx + 1]
            needed = TIER_THRESHOLDS[next_tier] - current_score
            return next_tier, max(0, needed)
    return None, 0

def log_activity(user_id, action, details=None, ip=None):
    activity = UserActivity(
        user_id=user_id,
        action=action,
        details=details,
        ip_address=ip
    )
    db.session.add(activity)
    db.session.commit()

def get_platform_stats():
    total_users = User.query.count()
    active_users = User.query.filter(User.last_login > datetime.utcnow() - timedelta(days=7)).count()
    total_withdrawals = Withdrawal.query.count()
    total_withdrawn = db.session.query(db.func.sum(Withdrawal.amount)).filter_by(status='COMPLETED').scalar() or 0
    total_transactions = Transaction.query.count()
    total_tasks_completed = TaskCompletion.query.count()
    
    return {
        'total_users': total_users,
        'active_users': active_users,
        'total_withdrawals': total_withdrawals,
        'total_withdrawn': total_withdrawn,
        'total_transactions': total_transactions,
        'total_tasks_completed': total_tasks_completed
    }

# ==================== STYLES ====================
STYLES = """
/* ==================== PROFESSIONAL DESIGN ==================== */
:root {
    --primary: #1E3A5F;
    --primary-light: #2C5282;
    --primary-dark: #0D2137;
    --secondary: #3182CE;
    --accent: #E2A609;
    --gold: #D4AF37;
    --success: #38A169;
    --danger: #E53E3E;
    --warning: #D69E2E;
    --bg: #F7FAFC;
    --card-bg: #FFFFFF;
    --text: #1A202C;
    --text-light: #4A5568;
    --text-muted: #718096;
    --border: #E2E8F0;
    --shadow: 0 4px 20px rgba(0,0,0,0.06);
    --shadow-hover: 0 8px 35px rgba(26, 32, 44, 0.1);
    --radius: 16px;
    --radius-sm: 10px;
    --transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    --nav-bg: rgba(255,255,255,0.95);
    --hero-bg: linear-gradient(135deg, #1E3A5F, #2C5282);
}

[data-theme="dark"] {
    --bg: #1A202C;
    --card-bg: #2D3748;
    --text: #F7FAFC;
    --text-light: #A0AEC0;
    --text-muted: #718096;
    --border: #4A5568;
    --shadow: 0 4px 20px rgba(0,0,0,0.3);
    --shadow-hover: 0 8px 35px rgba(0,0,0,0.4);
    --nav-bg: rgba(26, 32, 44, 0.95);
    --hero-bg: linear-gradient(135deg, #0D2137, #1E3A5F);
}

* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    padding: 16px;
    padding-bottom: 90px;
    max-width: 480px;
    margin: 0 auto;
    min-height: 100vh;
    overflow-x: hidden;
    transition: var(--transition);
    -webkit-font-smoothing: antialiased;
}

.logo-container {
    display: flex;
    align-items: center;
    gap: 12px;
    text-decoration: none;
}
.logo-icon {
    width: 48px;
    height: 48px;
    background: linear-gradient(135deg, var(--primary), var(--secondary));
    border-radius: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 22px;
    font-weight: 800;
    color: white;
    box-shadow: 0 4px 15px rgba(30, 58, 95, 0.3);
    position: relative;
    overflow: hidden;
}
.logo-icon::after {
    content: '';
    position: absolute;
    top: -50%;
    right: -50%;
    width: 100%;
    height: 100%;
    background: rgba(255,255,255,0.08);
    border-radius: 50%;
}
.logo-icon span { position: relative; z-index: 1; }
.logo-text { display: flex; flex-direction: column; line-height: 1.1; }
.logo-text .main {
    font-size: 20px;
    font-weight: 800;
    color: var(--text);
    letter-spacing: -0.5px;
}
.logo-text .main .highlight {
    color: var(--secondary);
}
.logo-text .sub {
    font-size: 9px;
    font-weight: 600;
    color: var(--text-muted);
    letter-spacing: 1.5px;
    text-transform: uppercase;
}

/* ==================== PROFESSIONAL HEADER ==================== */
.top-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
    padding: 14px 18px;
    background: var(--nav-bg);
    backdrop-filter: blur(20px);
    border-radius: var(--radius);
    box-shadow: var(--shadow);
    animation: slideDown 0.5s ease;
    border: 1px solid rgba(255,255,255,0.1);
    transition: var(--transition);
}
@keyframes slideDown {
    from { opacity: 0; transform: translateY(-20px); }
    to { opacity: 1; transform: translateY(0); }
}
.top-header .user-actions { display: flex; align-items: center; gap: 10px; }
.top-header .user-info { display: flex; align-items: center; gap: 10px; }
.top-header .user-avatar {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    background: linear-gradient(135deg, var(--secondary), var(--primary));
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-weight: 700;
    font-size: 14px;
}

/* ==================== PROFESSIONAL CARDS ==================== */
.card {
    background: var(--card-bg);
    border-radius: var(--radius);
    padding: 20px;
    margin-bottom: 16px;
    box-shadow: var(--shadow);
    transition: var(--transition);
    border: 1px solid rgba(255,255,255,0.05);
    animation: slideUp 0.6s ease forwards;
    opacity: 0;
    transform: translateY(30px);
}
.card:hover {
    box-shadow: var(--shadow-hover);
    transform: translateY(-2px);
}
@keyframes slideUp {
    to { opacity: 1; transform: translateY(0); }
}
.card:nth-child(1) { animation-delay: 0.05s; }
.card:nth-child(2) { animation-delay: 0.1s; }
.card:nth-child(3) { animation-delay: 0.15s; }
.card:nth-child(4) { animation-delay: 0.2s; }
.card:nth-child(5) { animation-delay: 0.25s; }
.card h2 { font-size: 20px; font-weight: 700; margin-bottom: 12px; color: var(--text); }
.card h3 { font-size: 16px; font-weight: 600; margin-bottom: 8px; color: var(--text); }

/* ==================== PROFESSIONAL BUTTONS ==================== */
.btn {
    background: var(--primary);
    color: white;
    border: none;
    padding: 14px 24px;
    border-radius: var(--radius-sm);
    font-size: 15px;
    font-weight: 600;
    cursor: pointer;
    width: 100%;
    text-decoration: none;
    display: inline-block;
    text-align: center;
    transition: var(--transition);
    position: relative;
    overflow: hidden;
}
.btn::after {
    content: '';
    position: absolute;
    top: 50%;
    left: 50%;
    width: 0;
    height: 0;
    border-radius: 50%;
    background: rgba(255,255,255,0.2);
    transform: translate(-50%, -50%);
    transition: width 0.6s, height 0.6s;
}
.btn:active::after { width: 400px; height: 400px; }
.btn:active { transform: scale(0.97); }
.btn-primary { background: linear-gradient(135deg, var(--primary), var(--secondary)); color: white; box-shadow: 0 4px 15px rgba(49, 130, 206, 0.3); }
.btn-secondary { background: var(--bg); color: var(--text); border: 1px solid var(--border); }
.btn-success { background: linear-gradient(135deg, var(--success), #276749); color: white; box-shadow: 0 4px 15px rgba(56, 161, 105, 0.3); }
.btn-danger { background: linear-gradient(135deg, var(--danger), #C53030); color: white; box-shadow: 0 4px 15px rgba(229, 62, 62, 0.3); }
.btn-gold { background: linear-gradient(135deg, #D4AF37, #B8942A); color: white; box-shadow: 0 4px 15px rgba(212, 175, 55, 0.3); }
.btn-outline { background: transparent; color: var(--primary); border: 2px solid var(--primary); }
.btn-outline:hover { background: var(--primary); color: white; }
.btn-sm { padding: 8px 16px; font-size: 13px; width: auto; }
.btn-logout { 
    background: linear-gradient(135deg, #E53E3E, #C53030); 
    color: white; 
    padding: 8px 16px; 
    font-size: 13px; 
    font-weight: 600;
    width: auto; 
    border-radius: 50px;
    box-shadow: 0 4px 15px rgba(229, 62, 62, 0.3);
}
.btn-share {
    background: linear-gradient(135deg, #1DA1F2, #0D8BD4);
    color: white;
    padding: 10px 18px;
    font-size: 13px;
    font-weight: 600;
    width: auto;
    border-radius: 50px;
}
.btn-whatsapp {
    background: linear-gradient(135deg, #25D366, #128C7E);
    color: white;
    padding: 10px 18px;
    font-size: 13px;
    font-weight: 600;
    width: auto;
    border-radius: 50px;
}
.btn-facebook {
    background: linear-gradient(135deg, #1877F2, #0D65D4);
    color: white;
    padding: 10px 18px;
    font-size: 13px;
    font-weight: 600;
    width: auto;
    border-radius: 50px;
}
.btn-telegram {
    background: linear-gradient(135deg, #0088CC, #006699);
    color: white;
    padding: 10px 18px;
    font-size: 13px;
    font-weight: 600;
    width: auto;
    border-radius: 50px;
}

/* ==================== TIER BADGES ==================== */
.tier-badge {
    padding: 4px 14px;
    border-radius: 50px;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    display: inline-block;
    transition: var(--transition);
}
.tier-free { background: #E2E8F0; color: #4A5568; }
.tier-beginner { background: linear-gradient(135deg, #DBEAFE, #93C5FD); color: #1E40AF; }
.tier-expert { background: linear-gradient(135deg, #FEF3C7, #FCD34D); color: #92400E; }
.tier-legend { background: linear-gradient(135deg, #FCE4EC, #F9A8D4); color: #9B1C1C; }

/* ==================== PROFESSIONAL NAV ==================== */
.bottom-nav {
    display: flex;
    gap: 2px;
    position: fixed;
    bottom: 16px;
    left: 50%;
    transform: translateX(-50%);
    background: var(--nav-bg);
    backdrop-filter: blur(30px);
    padding: 6px 8px;
    border-radius: 60px;
    box-shadow: 0 8px 40px rgba(0,0,0,0.12);
    max-width: 460px;
    width: calc(100% - 32px);
    z-index: 1000;
    border: 1px solid rgba(255,255,255,0.1);
    animation: slideUp 0.6s ease;
    transition: var(--transition);
}
.bottom-nav a {
    flex: 1;
    text-align: center;
    padding: 8px 4px;
    text-decoration: none;
    color: var(--text-muted);
    font-size: 8px;
    font-weight: 600;
    border-radius: 50px;
    transition: var(--transition);
    position: relative;
}
.bottom-nav a .icon { font-size: 20px; display: block; margin-bottom: 2px; transition: var(--transition); }
.bottom-nav a .label { font-size: 8px; display: block; transition: var(--transition); }
.bottom-nav a:hover { color: var(--primary); transform: translateY(-2px); }
.bottom-nav a.active {
    color: white;
    background: linear-gradient(135deg, var(--primary), var(--secondary));
    box-shadow: 0 4px 20px rgba(49, 130, 206, 0.4);
    padding: 8px 12px;
    flex: 1.2;
}
.bottom-nav a.active .icon { font-size: 22px; }
.bottom-nav a:active { transform: scale(0.9); }

/* ==================== HERO ==================== */
.hero-section {
    background: var(--hero-bg);
    border-radius: var(--radius);
    padding: 32px 24px;
    text-align: center;
    color: white;
    margin-bottom: 20px;
    position: relative;
    overflow: hidden;
    transition: var(--transition);
}
.hero-section::before {
    content: '';
    position: absolute;
    top: -60%;
    right: -30%;
    width: 300px;
    height: 300px;
    background: rgba(255,255,255,0.05);
    border-radius: 50%;
}
.hero-section::after {
    content: '';
    position: absolute;
    bottom: -50%;
    left: -20%;
    width: 200px;
    height: 200px;
    background: rgba(255,255,255,0.03);
    border-radius: 50%;
}
.hero-section .hero-icon { font-size: 56px; margin-bottom: 12px; position: relative; z-index: 1; }
.hero-section h1 { font-size: 26px; font-weight: 800; margin-bottom: 8px; position: relative; z-index: 1; }
.hero-section p { opacity: 0.9; font-size: 15px; position: relative; z-index: 1; line-height: 1.6; }

/* ==================== STATS ==================== */
.stats-counter {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 8px;
    margin: 16px 0;
}
.stat-item {
    background: rgba(255,255,255,0.1);
    border-radius: var(--radius-sm);
    padding: 12px 8px;
    text-align: center;
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255,255,255,0.05);
}
.stat-item .number { font-size: 20px; font-weight: 800; display: block; }
.stat-item .label { font-size: 9px; opacity: 0.8; text-transform: uppercase; letter-spacing: 0.5px; }

/* ==================== REVIEWS ==================== */
.review-card {
    background: var(--card-bg);
    border-radius: var(--radius-sm);
    padding: 14px 16px;
    margin-bottom: 10px;
    border-left: 4px solid var(--secondary);
    transition: var(--transition);
    animation: slideUp 0.6s ease forwards;
    opacity: 0;
    transform: translateY(20px);
    box-shadow: var(--shadow);
}
.review-card:hover { transform: translateX(5px); box-shadow: var(--shadow-hover); }
.review-card .review-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
.review-card .review-name { font-weight: 700; font-size: 14px; }
.review-card .review-time { font-size: 11px; color: var(--text-muted); }
.review-card .review-text { font-size: 14px; color: var(--text); line-height: 1.5; }
.review-card .review-stars { color: #D4AF37; font-size: 14px; }

/* ==================== FORMS ==================== */
input, select, textarea {
    width: 100%;
    padding: 14px 16px;
    border: 2px solid var(--border);
    border-radius: var(--radius-sm);
    font-size: 15px;
    margin: 6px 0;
    transition: var(--transition);
    background: var(--bg);
    color: var(--text);
}
input:focus, select:focus, textarea:focus {
    outline: none;
    border-color: var(--secondary);
    box-shadow: 0 0 0 4px rgba(49, 130, 206, 0.1);
    background: var(--card-bg);
}
textarea { min-height: 80px; resize: vertical; }
.form-group { margin-bottom: 16px; }
.form-group label { font-weight: 600; font-size: 14px; color: var(--text); display: block; margin-bottom: 4px; }

/* ==================== STATS GRID ==================== */
.stats-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
}
.stat-box {
    text-align: center;
    padding: 16px;
    background: var(--bg);
    border-radius: var(--radius-sm);
    transition: var(--transition);
    border: 1px solid transparent;
}
.stat-box:hover { border-color: var(--secondary); transform: translateY(-2px); }
.stat-box:active { transform: scale(0.97); }
.stat-box .value {
    font-size: 24px;
    font-weight: 800;
    color: var(--secondary);
}
.stat-box .value.gold { color: var(--gold); }
.stat-box .label { font-size: 12px; color: var(--text-muted); margin-top: 4px; font-weight: 500; }

/* ==================== PROGRESS ==================== */
.progress-bar {
    background: var(--bg);
    height: 8px;
    border-radius: 50px;
    overflow: hidden;
    margin-top: 8px;
}
.progress-fill {
    background: linear-gradient(90deg, var(--secondary), var(--primary));
    height: 100%;
    border-radius: 50px;
    transition: width 0.8s cubic-bezier(0.4, 0, 0.2, 1);
}

/* ==================== ALERTS ==================== */
.alert {
    padding: 14px 18px;
    border-radius: var(--radius-sm);
    margin-bottom: 16px;
    font-weight: 500;
    border-left: 4px solid;
    animation: slideDown 0.3s ease;
}
.alert-success { background: #F0FFF4; color: #22543D; border-color: var(--success); }
.alert-error { background: #FFF5F5; color: #9B2C2C; border-color: var(--danger); }
.alert-info { background: #EBF8FF; color: #2A4365; border-color: var(--secondary); }

/* ==================== UPGRADE REQUIRED ==================== */
.upgrade-required {
    text-align: center;
    padding: 40px 20px;
    background: linear-gradient(135deg, #FFF5F5, #FED7D7);
    border-radius: var(--radius);
    border: 2px solid var(--danger);
}
.upgrade-required .icon { font-size: 64px; margin-bottom: 16px; }
.upgrade-required h2 { color: var(--danger); margin-bottom: 8px; }
.upgrade-required p { color: var(--text-light); margin-bottom: 20px; }

/* ==================== SHARE BUTTONS ==================== */
.share-buttons {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    justify-content: center;
    margin: 12px 0;
}
.share-buttons .btn { width: auto; flex: 1; min-width: 80px; }

/* ==================== MISC ==================== */
.flex-between { display: flex; justify-content: space-between; align-items: center; }
.flex-center { display: flex; justify-content: center; align-items: center; }
.text-muted { color: var(--text-muted); font-size: 14px; }
.text-center { text-align: center; }
.text-gold { color: var(--gold); }
.mt-2 { margin-top: 12px; }
.mb-2 { margin-bottom: 12px; }
.mt-3 { margin-top: 20px; }
.gradient-text {
    background: linear-gradient(135deg, var(--secondary), var(--primary));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.status-badge {
    padding: 4px 12px;
    border-radius: 50px;
    font-size: 11px;
    font-weight: 600;
}
.status-pending { background: #FEF3C7; color: #92400E; }
.status-verified { background: #D1FAE5; color: #065F46; }
.status-rejected { background: #FEE2E2; color: #991B1B; }
.status-completed { background: #DBEAFE; color: #1E40AF; }
.status-open { background: #FEF3C7; color: #92400E; }
.status-resolved { background: #D1FAE5; color: #065F46; }
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--secondary); border-radius: 50px; }
.gradient-border {
    position: relative;
    background: var(--card-bg);
    border-radius: var(--radius);
}
.gradient-border::before {
    content: '';
    position: absolute;
    top: -2px;
    left: -2px;
    right: -2px;
    bottom: -2px;
    border-radius: var(--radius);
    background: linear-gradient(45deg, var(--secondary), var(--gold), var(--secondary));
    background-size: 400% 400%;
    z-index: -1;
    animation: gradientBorder 4s ease infinite;
}
@keyframes gradientBorder {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}
.bank-details-box {
    background: var(--bg);
    border-radius: var(--radius-sm);
    padding: 16px;
    margin: 8px 0;
    border: 2px dashed var(--secondary);
}
.bank-details-box .label { font-size: 12px; color: var(--text-muted); }
.bank-details-box .value { font-size: 18px; font-weight: 700; color: var(--text); }
.upgrade-info {
    background: linear-gradient(135deg, #FEF3C7, #FCD34D);
    padding: 12px 16px;
    border-radius: var(--radius-sm);
    border-left: 4px solid var(--gold);
    margin-bottom: 16px;
}
.withdrawal-info {
    background: linear-gradient(135deg, #FEF3C7, #FCD34D);
    padding: 12px 16px;
    border-radius: var(--radius-sm);
    border-left: 4px solid var(--gold);
}
.trust-progress {
    margin-top: 4px;
}
.trust-progress .level {
    display: flex;
    justify-content: space-between;
    font-size: 11px;
    color: var(--text-muted);
    margin-top: 2px;
}
.trust-progress .level .active { color: var(--secondary); font-weight: 700; }
.trust-progress .level .completed { color: var(--success); }
.tier-card {
    background: var(--card-bg);
    border-radius: var(--radius);
    padding: 20px;
    margin-bottom: 16px;
    border: 2px solid var(--border);
    transition: var(--transition);
    cursor: pointer;
    box-shadow: var(--shadow);
}
.tier-card:hover { transform: translateY(-4px); box-shadow: var(--shadow-hover); }
.tier-card:active { transform: scale(0.98); }
.tier-card.popular {
    border-color: var(--gold);
    background: linear-gradient(135deg, rgba(212, 175, 55, 0.05), rgba(212, 175, 55, 0.02));
}
.tier-card .price { font-size: 28px; font-weight: 800; color: var(--secondary); }
.tier-card .price small { font-size: 14px; font-weight: 400; color: var(--text-muted); }
.badge-popular {
    background: linear-gradient(135deg, #D4AF37, #B8942A);
    color: white;
    padding: 2px 10px;
    border-radius: 50px;
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    float: right;
    animation: pulse 2s infinite;
}
@keyframes pulse {
    0%, 100% { transform: scale(1); }
    50% { transform: scale(1.05); }
}
.login-features {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    margin-top: 12px;
}
.login-feature {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px;
    background: var(--bg);
    border-radius: var(--radius-sm);
    font-size: 13px;
    font-weight: 500;
}
.login-feature .icon { font-size: 18px; }
.bonus-badge {
    background: linear-gradient(135deg, #D4AF37, #B8942A);
    color: white;
    padding: 4px 12px;
    border-radius: 50px;
    font-size: 11px;
    font-weight: 700;
    animation: pulse 2s infinite;
}
.profile-completion {
    margin-top: 8px;
}
.profile-completion .label {
    display: flex;
    justify-content: space-between;
    font-size: 13px;
    color: var(--text-muted);
}
.profile-completion .bar {
    height: 6px;
    background: var(--bg);
    border-radius: 50px;
    overflow: hidden;
    margin-top: 4px;
}
.profile-completion .fill {
    height: 100%;
    background: linear-gradient(90deg, var(--success), var(--secondary));
    border-radius: 50px;
    transition: width 0.8s ease;
}
.google-trust {
    display: flex;
    align-items: center;
    gap: 12px;
    background: var(--card-bg);
    padding: 12px 16px;
    border-radius: var(--radius-sm);
    border: 1px solid var(--border);
    margin-bottom: 16px;
}
.google-trust .logo { font-size: 28px; font-weight: 700; color: #4285F4; }
.google-trust .logo span { color: #EA4335; }
.google-trust .stars { color: #D4AF37; font-size: 14px; }
.google-trust .text { font-size: 12px; color: var(--text-muted); }
.google-review-card {
    background: var(--card-bg);
    border-radius: var(--radius-sm);
    padding: 12px 16px;
    margin-bottom: 8px;
    border: 1px solid var(--border);
}
.google-review-card .header { display: flex; justify-content: space-between; align-items: center; }
.google-review-card .name { font-weight: 600; font-size: 14px; }
.google-review-card .stars { color: #D4AF37; font-size: 13px; }
.google-review-card .text { font-size: 13px; margin-top: 4px; color: var(--text); }
.google-review-card .verified { font-size: 11px; color: var(--success); }
.btn-disabled {
    opacity: 0.5;
    cursor: not-allowed;
    pointer-events: none;
}
"""

# ==================== PAGE DEFINITIONS ====================

# [All page definitions are here - LANDING_PAGE, LOGIN_PAGE, REGISTER_PAGE, 
#  DASHBOARD_PAGE, EARN_PAGE, REFERRAL_PAGE, UPGRADE_PAGE, WITHDRAW_PAGE,
#  ACCOUNT_PAGE, CHANGE_PASSWORD_PAGE, SUPPORT_PAGE, ADMIN_LOGIN_PAGE,
#  ADMIN_DASHBOARD_PAGE, ADMIN_USERS_PAGE, ADMIN_SETTINGS_PAGE]

# ==================== ROUTES ====================

@app.route('/')
def home():
    if 'username' in session:
        return redirect('/dashboard')
    return render_template_string(LANDING_PAGE, reviews=FAKE_REVIEWS, google_reviews=GOOGLE_REVIEWS)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm = request.form.get('confirm_password')
        
        if password != confirm:
            flash('❌ Passwords do not match!', 'error')
            return redirect('/register')
        
        if User.query.filter_by(username=username).first():
            flash('❌ Username already taken!', 'error')
            return redirect('/register')
        
        if User.query.filter_by(email=email).first():
            flash('❌ Email already registered!', 'error')
            return redirect('/register')
        
        user = User(username=username, email=email)
        user.set_password(password)
        user.referral_code = user.generate_referral_code()
        user.daily_limit = 0  # No tasks for free tier
        
        ref_code = request.args.get('ref', '')
        if ref_code:
            referrer = User.query.filter_by(referral_code=ref_code).first()
            if referrer:
                user.referred_by = referrer.id
                bonus_amount = REFERRAL_BONUS
                referrer.balance += bonus_amount
                referrer.commission_balance += bonus_amount
                referrer.trust_score += 1
                referrer.referral_bonus_earned += bonus_amount
                referrer.total_referrals += 1
                db.session.add(referrer)
                flash(f'🎉 You were referred by {referrer.username}! You both get ₦{bonus_amount}!', 'success')
            else:
                flash('Invalid referral code!', 'error')
        else:
            flash('✅ Registration successful! Please login.', 'success')
        
        db.session.add(user)
        db.session.commit()
        return redirect('/login')
    
    return render_template_string(REGISTER_PAGE)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            if user.is_banned:
                flash(f'❌ Your account has been banned. Reason: {user.ban_reason or "Violation of terms"}', 'error')
                return redirect('/login')
            
            session['username'] = username
            session['user_id'] = user.id
            user.last_login = datetime.utcnow()
            db.session.commit()
            log_activity(user.id, 'login', f'User logged in from {request.remote_addr}')
            flash('👋 Welcome back!', 'success')
            return redirect('/dashboard')
        
        flash('❌ Invalid username or password!', 'error')
    
    return render_template_string(LOGIN_PAGE)

@app.route('/logout')
def logout():
    if 'user_id' in session:
        log_activity(session['user_id'], 'logout', 'User logged out')
    session.clear()
    flash('👋 Logged out successfully', 'success')
    return redirect('/login')

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect('/login')
    
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect('/login')
    
    if user.is_banned:
        session.clear()
        flash(f'❌ Your account has been banned. Reason: {user.ban_reason or "Violation of terms"}', 'error')
        return redirect('/login')
    
    # Check if user has upgraded (tier is not FREE)
    if user.tier == 'FREE' and user.daily_limit == 0:
        # Show upgrade required page
        return render_template_string(UPGRADE_REQUIRED_PAGE, user=user)
    
    now = datetime.now()
    if user.last_task_reset:
        if now - user.last_task_reset >= timedelta(hours=24):
            user.daily_tasks_completed = 0
            user.last_task_reset = now
            db.session.commit()
    else:
        user.last_task_reset = now
        db.session.commit()
    
    today = datetime.now().date()
    if user.last_checkin:
        if user.last_checkin.date() == today - timedelta(days=1):
            user.streak_days += 1
            user.trust_score += 1
        elif user.last_checkin.date() != today:
            user.streak_days = 0
    user.last_checkin = datetime.now()
    
    if user.last_checkin.date() != today:
        user.daily_tasks_completed = 0
    
    db.session.commit()
    
    next_tier, needed_points = get_next_tier_info(user.tier, user.trust_score)
    
    if next_tier:
        next_threshold = TIER_THRESHOLDS[next_tier]
        current_threshold = TIER_THRESHOLDS[user.tier]
        progress = min(100, ((user.trust_score - current_threshold) / (next_threshold - current_threshold) * 100) if next_threshold > current_threshold else 0)
    else:
        progress = 100
    
    today_tasks = TaskCompletion.query.filter(
        TaskCompletion.user_id == user.id,
        db.func.date(TaskCompletion.completed_at) == today
    ).count()
    
    remaining = max(0, user.daily_limit - today_tasks)
    
    if user.last_task_reset:
        next_reset = user.last_task_reset + timedelta(hours=24)
        time_left = next_reset - now
        hours = int(time_left.total_seconds() // 3600)
        minutes = int((time_left.total_seconds() % 3600) // 60)
        reset_time = f"{hours}h {minutes}m"
    else:
        reset_time = "24h 0m"
    
    # Get announcements
    announcements = Announcement.query.filter_by(is_active=True).order_by(Announcement.created_at.desc()).limit(3).all()
    
    return render_template_string(DASHBOARD_PAGE,
        user=user,
        session=session,
        progress=progress,
        needed_points=needed_points,
        next_tier=next_tier,
        today_tasks=today_tasks,
        remaining_tasks=remaining,
        total_referrals=user.total_referrals,
        reset_time=reset_time,
        announcements=announcements
    )

@app.route('/account')
def account_page():
    if 'username' not in session:
        return redirect('/login')
    
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect('/login')
    
    if user.is_banned:
        session.clear()
        flash('❌ Your account has been banned.', 'error')
        return redirect('/login')
    
    completion = user.get_profile_completion()
    total_fields = 6
    completed_fields = sum(1 for field in ['full_name', 'phone', 'address', 'bank_name', 'bank_account', 'account_name'] if getattr(user, field))
    
    return render_template_string(ACCOUNT_PAGE,
        user=user,
        completion=completion,
        completed_fields=completed_fields,
        total_fields=total_fields
    )

@app.route('/update_account', methods=['POST'])
def update_account():
    if 'username' not in session:
        return redirect('/login')
    
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect('/login')
    
    user.full_name = request.form.get('full_name')
    user.phone = request.form.get('phone')
    user.address = request.form.get('address')
    user.occupation = request.form.get('occupation')
    user.gender = request.form.get('gender')
    user.bio = request.form.get('bio')
    
    dob = request.form.get('date_of_birth')
    if dob:
        user.date_of_birth = datetime.strptime(dob, '%Y-%m-%d').date()
    
    db.session.commit()
    log_activity(user.id, 'update_account', 'Updated account information')
    flash('✅ Account information updated successfully!', 'success')
    return redirect('/account')

@app.route('/update_bank', methods=['POST'])
def update_bank():
    if 'username' not in session:
        return redirect('/login')
    
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect('/login')
    
    user.bank_name = request.form.get('bank_name')
    user.bank_account = request.form.get('bank_account')
    user.account_name = request.form.get('account_name')
    
    db.session.commit()
    log_activity(user.id, 'update_bank', 'Updated bank details')
    flash('✅ Bank details updated successfully!', 'success')
    return redirect('/account')

@app.route('/set_theme', methods=['POST'])
def set_theme():
    if 'username' not in session:
        return redirect('/login')
    
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect('/login')
    
    user.theme = request.form.get('theme', 'light')
    db.session.commit()
    flash(f'✅ Theme set to {user.theme} mode!', 'success')
    referer = request.referrer or '/account'
    return redirect(referer)

@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if 'username' not in session:
        return redirect('/login')
    
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect('/login')
    
    if user.is_banned:
        session.clear()
        flash('❌ Your account has been banned.', 'error')
        return redirect('/login')
    
    if request.method == 'POST':
        current = request.form.get('current_password')
        new = request.form.get('new_password')
        confirm = request.form.get('confirm_password')
        
        if not user.check_password(current):
            flash('❌ Current password is incorrect!', 'error')
            return redirect('/change_password')
        
        if new != confirm:
            flash('❌ New passwords do not match!', 'error')
            return redirect('/change_password')
        
        if len(new) < 8:
            flash('❌ Password must be at least 8 characters!', 'error')
            return redirect('/change_password')
        
        user.set_password(new)
        db.session.commit()
        log_activity(user.id, 'change_password', 'Changed password')
        flash('✅ Password changed successfully!', 'success')
        return redirect('/account')
    
    return render_template_string(CHANGE_PASSWORD_PAGE, user=user)

@app.route('/support', methods=['GET'])
def support_page():
    if 'username' not in session:
        return redirect('/login')
    
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect('/login')
    
    if user.is_banned:
        session.clear()
        flash('❌ Your account has been banned.', 'error')
        return redirect('/login')
    
    tickets = SupportTicket.query.filter_by(user_id=user.id).order_by(SupportTicket.created_at.desc()).all()
    ticket_list = [t.to_dict() for t in tickets]
    
    return render_template_string(SUPPORT_PAGE, user=user, tickets=ticket_list)

@app.route('/submit_support', methods=['POST'])
def submit_support():
    if 'username' not in session:
        return redirect('/login')
    
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect('/login')
    
    subject = request.form.get('subject')
    message = request.form.get('message')
    priority = request.form.get('priority', 'MEDIUM')
    category = request.form.get('category', 'General')
    
    if not subject or not message:
        flash('❌ Please fill in all fields!', 'error')
        return redirect('/support')
    
    ticket = SupportTicket(
        user_id=user.id,
        subject=subject,
        message=message,
        priority=priority,
        category=category,
        status='OPEN'
    )
    db.session.add(ticket)
    db.session.commit()
    
    log_activity(user.id, 'submit_ticket', f'Submitted support ticket: {subject}')
    flash('✅ Your support ticket has been submitted!', 'success')
    return redirect('/support')

@app.route('/earn')
def earn():
    if 'username' not in session:
        return redirect('/login')
    
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect('/login')
    
    if user.is_banned:
        session.clear()
        flash('❌ Your account has been banned.', 'error')
        return redirect('/login')
    
    # Check if user has upgraded
    if user.tier == 'FREE' and user.daily_limit == 0:
        flash('⚠️ You need to upgrade your tier to access tasks!', 'error')
        return redirect('/upgrade')
    
    now = datetime.now()
    if user.last_task_reset:
        if now - user.last_task_reset >= timedelta(hours=24):
            user.daily_tasks_completed = 0
            user.last_task_reset = now
            db.session.commit()
    else:
        user.last_task_reset = now
        db.session.commit()
    
    tasks = Task.query.filter_by(tier_required=user.tier, is_active=True).all()
    
    today = datetime.now().date()
    completed = TaskCompletion.query.filter(
        TaskCompletion.user_id == user.id,
        db.func.date(TaskCompletion.completed_at) == today
    ).all()
    
    completed_ids = [c.task_id for c in completed]
    remaining = max(0, user.daily_limit - len(completed))
    
    return render_template_string(EARN_PAGE,
        user=user,
        tasks=tasks,
        completed_ids=completed_ids,
        remaining=remaining
    )

@app.route('/complete_task/<int:task_id>', methods=['POST'])
def complete_task(task_id):
    if 'username' not in session:
        return redirect('/login')
    
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect('/login')
    
    if user.is_banned:
        session.clear()
        flash('❌ Your account has been banned.', 'error')
        return redirect('/login')
    
    # Check if user has upgraded
    if user.tier == 'FREE' and user.daily_limit == 0:
        flash('⚠️ You need to upgrade your tier to access tasks!', 'error')
        return redirect('/upgrade')
    
    now = datetime.now()
    if user.last_task_reset:
        if now - user.last_task_reset >= timedelta(hours=24):
            user.daily_tasks_completed = 0
            user.last_task_reset = now
            db.session.commit()
    
    task = Task.query.get_or_404(task_id)
    
    today = datetime.now().date()
    today_tasks = TaskCompletion.query.filter(
        TaskCompletion.user_id == user.id,
        db.func.date(TaskCompletion.completed_at) == today
    ).count()
    
    if today_tasks >= user.daily_limit:
        flash('⛔ Daily task limit reached!', 'error')
        return redirect('/earn')
    
    completion = TaskCompletion(
        user_id=user.id,
        task_id=task.id,
        proof_text=request.form.get('proof_text', 'Completed')
    )
    db.session.add(completion)
    
    user.balance += task.reward
    user.trust_score += 1
    
    new_tier = get_tier_from_score(user.trust_score)
    if new_tier != user.tier:
        user.tier = new_tier
        user.daily_limit = TIER_TASKS.get(new_tier, 0)
        flash(f'🎉 Congratulations! You\'ve been upgraded to {new_tier.title()} tier!', 'success')
    
    user.daily_tasks_completed += 1
    db.session.commit()
    
    log_activity(user.id, 'complete_task', f'Completed task: {task.title}')
    flash(f'✅ Task completed! +₦{task.reward}', 'success')
    return redirect('/earn')

@app.route('/referral')
def referral_page():
    if 'username' not in session:
        return redirect('/login')
    
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect('/login')
    
    if user.is_banned:
        session.clear()
        flash('❌ Your account has been banned.', 'error')
        return redirect('/login')
    
    referrals = Referral.query.filter_by(referrer_id=user.id).all()
    
    referred_users = []
    downline = {'FREE': 0, 'BEGINNER': 0, 'EXPERT': 0, 'LEGEND': 0}
    
    for ref in referrals:
        referred = User.query.get(ref.referred_id)
        if referred:
            referred_users.append(referred)
            downline[referred.tier] += 1
    
    # Generate share link
    share_url = f"https://earnnpay.com/register?ref={user.referral_code}"
    share_text = f"Join Earn'n'Pay Labs and start earning real cash! Use my referral link: {share_url}"
    
    # Social media share links
    whatsapp_link = f"https://wa.me/?text={share_text}"
    facebook_link = f"https://www.facebook.com/sharer/sharer.php?u={share_url}"
    twitter_link = f"https://twitter.com/intent/tweet?text={share_text}"
    telegram_link = f"https://t.me/share/url?url={share_url}&text={share_text}"
    
    return render_template_string(REFERRAL_PAGE,
        user=user,
        referral_link=share_url,
        referrals=referred_users,
        total_invites=len(referrals),
        verified_users=sum(1 for r in referrals if r.verified),
        downline=downline,
        whatsapp_link=whatsapp_link,
        facebook_link=facebook_link,
        twitter_link=twitter_link,
        telegram_link=telegram_link,
        share_text=share_text
    )

@app.route('/share_task', methods=['GET', 'POST'])
def share_task():
    if 'username' not in session:
        return redirect('/login')
    
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect('/login')
    
    if request.method == 'POST':
        # Award bonus for sharing
        platform = request.form.get('platform', 'social')
        bonus = 50
        
        user.balance += bonus
        user.trust_score += 1
        db.session.commit()
        
        log_activity(user.id, 'share_task', f'Shared on {platform}')
        flash(f'✅ Thank you for sharing! +₦{bonus}', 'success')
        return redirect('/earn')
    
    share_url = f"https://earnnpay.com/register?ref={user.referral_code}"
    share_text = f"Join Earn'n'Pay Labs and start earning real cash! Use my referral link: {share_url}"
    
    return render_template_string(SHARE_TASK_PAGE,
        user=user,
        share_url=share_url,
        share_text=share_text,
        whatsapp_link=f"https://wa.me/?text={share_text}",
        facebook_link=f"https://www.facebook.com/sharer/sharer.php?u={share_url}",
        twitter_link=f"https://twitter.com/intent/tweet?text={share_text}",
        telegram_link=f"https://t.me/share/url?url={share_url}&text={share_text}"
    )

@app.route('/upgrade')
def upgrade_page():
    if 'username' not in session:
        return redirect('/login')
    
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect('/login')
    
    if user.is_banned:
        session.clear()
        flash('❌ Your account has been banned.', 'error')
        return redirect('/login')
    
    tiers = {
        'BEGINNER': {'name': 'Beginner', 'cost': 1000, 'daily_limit': 6, 'description': '6 tasks/day · reviews up to ₦150'},
        'EXPERT': {'name': 'Expert', 'cost': 3500, 'daily_limit': 10, 'description': '10 tasks/day · reviews up to ₦450'},
        'LEGEND': {'name': 'Legend', 'cost': 10000, 'daily_limit': 15, 'description': '15 tasks/day · reviews up to ₦1,000'}
    }
    
    user_transactions = Transaction.query.filter_by(user_id=user.id).order_by(Transaction.created_at.desc()).limit(5).all()
    
    return render_template_string(UPGRADE_PAGE,
        user=user,
        tiers=tiers,
        transactions_list=[t.to_dict() for t in user_transactions],
        get_payment_settings=get_payment_settings
    )

@app.route('/submit_payment', methods=['POST'])
def submit_payment():
    if 'username' not in session:
        return redirect('/login')
    
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect('/login')
    
    tier = request.form.get('tier')
    amount = float(request.form.get('amount', 0))
    sender_name = request.form.get('sender_name')
    transaction_id = request.form.get('transaction_id')
    amount_sent = float(request.form.get('amount_sent', 0))
    payment_date = request.form.get('payment_date')
    notes = request.form.get('notes', '')
    
    if Transaction.query.filter_by(transaction_id=transaction_id).first():
        flash('❌ This transaction ID already exists!', 'error')
        return redirect('/upgrade')
    
    tx = Transaction(
        user_id=user.id,
        amount=amount,
        tier=tier,
        transaction_id=transaction_id,
        sender_name=sender_name,
        payment_date=datetime.strptime(payment_date, '%Y-%m-%dT%H:%M'),
        notes=notes,
        status='PENDING',
        type='UPGRADE'
    )
    db.session.add(tx)
    db.session.commit()
    
    log_activity(user.id, 'submit_payment', f'Submitted payment for {tier} tier')
    flash('✅ Payment proof submitted! Please wait for admin verification.', 'success')
    return redirect('/upgrade')

@app.route('/withdraw', methods=['GET', 'POST'])
def withdraw_page():
    if 'username' not in session:
        return redirect('/login')
    
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect('/login')
    
    if user.is_banned:
        session.clear()
        flash('❌ Your account has been banned.', 'error')
        return redirect('/login')
    
    withdrawals = Withdrawal.query.filter_by(user_id=user.id).order_by(Withdrawal.created_at.desc()).limit(10).all()
    
    can_withdraw = can_withdraw_today()
    next_date = get_next_withdrawal_date()
    min_amount = MINIMUM_WITHDRAWAL
    
    if request.method == 'POST':
        if not can_withdraw:
            flash(f'❌ Withdrawals are only allowed on the 10th and 30th of each month. Next withdrawal date: {next_date.strftime("%B %d, %Y")}', 'error')
            return redirect('/withdraw')
        
        amount = float(request.form.get('amount', 0))
        bank_name = request.form.get('bank_name')
        account_number = request.form.get('account_number')
        account_name = request.form.get('account_name')
        
        if amount < min_amount:
            flash(f'❌ Minimum withdrawal is ₦{min_amount:,}!', 'error')
            return redirect('/withdraw')
        
        if amount > user.balance:
            flash('❌ Insufficient balance!', 'error')
            return redirect('/withdraw')
        
        withdrawal = Withdrawal(
            user_id=user.id,
            amount=amount,
            bank_name=bank_name,
            account_number=account_number,
            account_name=account_name,
            reference=f"WDL-{user.id}-{random.randint(1000,9999)}"
        )
        db.session.add(withdrawal)
        
        user.balance -= amount
        db.session.commit()
        
        log_activity(user.id, 'withdraw_request', f'Requested withdrawal of ₦{amount}')
        flash(f'💸 Withdrawal of ₦{amount:,.2f} requested!', 'success')
        return redirect('/dashboard')
    
    return render_template_string(WITHDRAW_PAGE,
        user=user,
        withdrawals=withdrawals,
        can_withdraw=can_withdraw,
        next_date=next_date,
        min_amount=min_amount
    )

# ==================== ADMIN ROUTES ====================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin'] = True
            flash('✅ Admin login successful!', 'success')
            return redirect('/admin/dashboard')
        
        flash('❌ Invalid admin credentials!', 'error')
    
    return render_template_string(ADMIN_LOGIN_PAGE)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    flash('👋 Admin logged out', 'success')
    return redirect('/')

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin'):
        return redirect('/admin/login')
    
    pending = Transaction.query.filter_by(status='PENDING').all()
    all_users = User.query.all()
    verified_count = Transaction.query.filter_by(status='VERIFIED').count()
    total_withdrawals = Withdrawal.query.count()
    open_tickets = SupportTicket.query.filter_by(status='OPEN').count()
    stats = get_platform_stats()
    total_balance = sum(u.balance for u in all_users)
    
    return render_template_string(ADMIN_DASHBOARD_PAGE,
        pending_transactions=pending,
        pending_count=len(pending),
        verified_count=verified_count,
        total_withdrawals=total_withdrawals,
        total_users=len(all_users),
        all_users=all_users,
        open_tickets=open_tickets,
        stats=stats,
        total_balance=total_balance
    )

@app.route('/admin/users')
def admin_users():
    if not session.get('admin'):
        return redirect('/admin/login')
    
    all_users = User.query.order_by(User.id.desc()).all()
    total_balance = sum(u.balance for u in all_users)
    free_users = sum(1 for u in all_users if u.tier == 'FREE')
    paid_users = len(all_users) - free_users
    
    return render_template_string(ADMIN_USERS_PAGE,
        users=all_users,
        total_users=len(all_users),
        free_users=free_users,
        paid_users=paid_users,
        total_balance=total_balance
    )

@app.route('/admin/user/<int:user_id>/ban', methods=['POST'])
def admin_ban_user(user_id):
    if not session.get('admin'):
        return redirect('/admin/login')
    
    user = User.query.get_or_404(user_id)
    user.is_banned = True
    user.ban_reason = request.form.get('reason', 'Violation of terms')
    db.session.commit()
    
    log_activity(user.id, 'admin_ban', f'Banned by admin. Reason: {user.ban_reason}')
    flash(f'✅ User {user.username} banned successfully!', 'success')
    return redirect('/admin/users')

@app.route('/admin/user/<int:user_id>/unban', methods=['POST'])
def admin_unban_user(user_id):
    if not session.get('admin'):
        return redirect('/admin/login')
    
    user = User.query.get_or_404(user_id)
    user.is_banned = False
    user.ban_reason = None
    db.session.commit()
    
    log_activity(user.id, 'admin_unban', 'Unbanned by admin')
    flash(f'✅ User {user.username} unbanned successfully!', 'success')
    return redirect('/admin/users')

@app.route('/admin/user/<int:user_id>/edit', methods=['GET', 'POST'])
def admin_edit_user(user_id):
    if not session.get('admin'):
        return redirect('/admin/login')
    
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        user.full_name = request.form.get('full_name')
        user.email = request.form.get('email')
        user.phone = request.form.get('phone')
        user.tier = request.form.get('tier')
        user.daily_limit = int(request.form.get('daily_limit', 0))
        user.balance = float(request.form.get('balance', 0))
        user.trust_score = int(request.form.get('trust_score', 0))
        user.is_active = 'is_active' in request.form
        
        db.session.commit()
        log_activity(user.id, 'admin_edit', 'Edited by admin')
        flash(f'✅ User {user.username} updated successfully!', 'success')
        return redirect('/admin/users')
    
    return render_template_string(ADMIN_EDIT_USER_PAGE, user=user)

@app.route('/admin/settings')
def admin_settings():
    if not session.get('admin'):
        return redirect('/admin/login')
    
    settings = get_payment_settings()
    return render_template_string(ADMIN_SETTINGS_PAGE, settings=settings)

@app.route('/admin/update_payment_settings', methods=['POST'])
def update_payment_settings():
    if not session.get('admin'):
        return redirect('/admin/login')
    
    bank_name = request.form.get('bank_name')
    account_name = request.form.get('account_name')
    account_number = request.form.get('account_number')
    
    settings = get_payment_settings()
    settings.bank_name = bank_name
    settings.account_name = account_name
    settings.account_number = account_number
    db.session.commit()
    
    flash('✅ Payment details updated successfully!', 'success')
    return redirect('/admin/settings')

@app.route('/admin/support')
def admin_support():
    if not session.get('admin'):
        return redirect('/admin/login')
    
    tickets = SupportTicket.query.order_by(SupportTicket.created_at.desc()).all()
    ticket_list = [t.to_dict() for t in tickets]
    
    return render_template_string(ADMIN_SUPPORT_PAGE, tickets=ticket_list)

@app.route('/admin/support/<int:ticket_id>/resolve', methods=['POST'])
def admin_resolve_ticket(ticket_id):
    if not session.get('admin'):
        return redirect('/admin/login')
    
    ticket = SupportTicket.query.get_or_404(ticket_id)
    ticket.status = 'RESOLVED'
    ticket.admin_response = request.form.get('response', '')
    ticket.responded_at = datetime.utcnow()
    db.session.commit()
    
    flash('✅ Ticket resolved!', 'success')
    return redirect('/admin/support')

@app.route('/admin/support/<int:ticket_id>/delete', methods=['POST'])
def admin_delete_ticket(ticket_id):
    if not session.get('admin'):
        return redirect('/admin/login')
    
    ticket = SupportTicket.query.get_or_404(ticket_id)
    db.session.delete(ticket)
    db.session.commit()
    
    flash('🗑️ Ticket deleted!', 'info')
    return redirect('/admin/support')

@app.route('/admin/announcements', methods=['GET', 'POST'])
def admin_announcements():
    if not session.get('admin'):
        return redirect('/admin/login')
    
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        
        announcement = Announcement(
            title=title,
            content=content,
            is_active=True
        )
        db.session.add(announcement)
        db.session.commit()
        
        flash('✅ Announcement created!', 'success')
        return redirect('/admin/announcements')
    
    announcements = Announcement.query.order_by(Announcement.created_at.desc()).all()
    return render_template_string(ADMIN_ANNOUNCEMENTS_PAGE, announcements=announcements)

@app.route('/admin/announcements/<int:announcement_id>/toggle', methods=['POST'])
def admin_toggle_announcement(announcement_id):
    if not session.get('admin'):
        return redirect('/admin/login')
    
    announcement = Announcement.query.get_or_404(announcement_id)
    announcement.is_active = not announcement.is_active
    db.session.commit()
    
    flash('✅ Announcement toggled!', 'success')
    return redirect('/admin/announcements')

@app.route('/admin/announcements/<int:announcement_id>/delete', methods=['POST'])
def admin_delete_announcement(announcement_id):
    if not session.get('admin'):
        return redirect('/admin/login')
    
    announcement = Announcement.query.get_or_404(announcement_id)
    db.session.delete(announcement)
    db.session.commit()
    
    flash('🗑️ Announcement deleted!', 'info')
    return redirect('/admin/announcements')

@app.route('/admin/verify_payment/<int:tx_id>', methods=['POST'])
def verify_payment(tx_id):
    if not session.get('admin'):
        return redirect('/admin/login')
    
    tx = Transaction.query.get_or_404(tx_id)
    tx.status = 'VERIFIED'
    
    user = User.query.get(tx.user_id)
    if user:
        tier = tx.tier
        tier_limits = {'BEGINNER': 6, 'EXPERT': 10, 'LEGEND': 15}
        user.tier = tier
        user.daily_limit = tier_limits.get(tier, 0)
        db.session.commit()
        
        log_activity(user.id, 'admin_verify_payment', f'Verified payment for {tier} tier')
        flash(f'✅ {user.username} upgraded to {tier.title()}! Now has {user.daily_limit} tasks per day!', 'success')
    
    db.session.commit()
    return redirect('/admin/dashboard')

@app.route('/admin/reject_payment/<int:tx_id>', methods=['POST'])
def reject_payment(tx_id):
    if not session.get('admin'):
        return redirect('/admin/login')
    
    tx = Transaction.query.get_or_404(tx_id)
    tx.status = 'REJECTED'
    db.session.commit()
    
    flash('❌ Payment rejected!', 'info')
    return redirect('/admin/dashboard')

@app.route('/admin/tasks', methods=['GET', 'POST'])
def admin_tasks():
    if not session.get('admin'):
        return redirect('/admin/login')
    
    if request.method == 'POST':
        task = Task(
            title=request.form.get('title'),
            description=request.form.get('description'),
            task_type=request.form.get('task_type'),
            reward=float(request.form.get('reward')),
            tier_required=request.form.get('tier_required'),
            category=request.form.get('category', 'General'),
            daily_limit=int(request.form.get('daily_limit', 2)),
            is_active=True
        )
        db.session.add(task)
        db.session.commit()
        flash('✅ Task created!', 'success')
        return redirect('/admin/tasks')
    
    tasks = Task.query.order_by(Task.created_at.desc()).all()
    return render_template_string(ADMIN_TASKS_PAGE, tasks=tasks)

@app.route('/admin/tasks/<int:task_id>/toggle', methods=['POST'])
def admin_toggle_task(task_id):
    if not session.get('admin'):
        return redirect('/admin/login')
    
    task = Task.query.get_or_404(task_id)
    task.is_active = not task.is_active
    db.session.commit()
    
    flash('✅ Task toggled!', 'success')
    return redirect('/admin/tasks')

@app.route('/admin/tasks/<int:task_id>/delete', methods=['POST'])
def admin_delete_task(task_id):
    if not session.get('admin'):
        return redirect('/admin/login')
    
    task = Task.query.get_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    
    flash('🗑️ Task deleted!', 'info')
    return redirect('/admin/tasks')

# ==================== CATCH-ALL ROUTE ====================
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    if 'username' in session:
        return redirect('/dashboard')
    return redirect('/')

# ==================== RUN ====================

if __name__ == '__main__':
    print("=" * 60)
    print("💰 Earn'n'Pay Labs - ULTIMATE PROFESSIONAL VERSION")
    print("=" * 60)
    print("✅ Server starting...")
    print("🌐 Open your browser and go to: http://127.0.0.1:5000")
    print("=" * 60)
    print("📊 TRUST SCORE TIERS:")
    print(f"   FREE: 0 points (NO TASKS - Upgrade Required)")
    print(f"   BEGINNER: 100 points")
    print(f"   EXPERT: 300 points")
    print(f"   LEGEND: 700 points")
    print("=" * 60)
    print("📅 Withdrawal Settings:")
    print(f"   Minimum: ₦{MINIMUM_WITHDRAWAL:,}")
    print(f"   Days: 10th and 30th of every month")
    print("=" * 60)
    print("📊 Tier Task Limits:")
    print(f"   FREE: {TIER_TASKS['FREE']} tasks/day (NO TASKS)")
    print(f"   BEGINNER: {TIER_TASKS['BEGINNER']} tasks/day")
    print(f"   EXPERT: {TIER_TASKS['EXPERT']} tasks/day")
    print(f"   LEGEND: {TIER_TASKS['LEGEND']} tasks/day")
    print("=" * 60)
    print("🔐 Admin Panel:")
    print(f"   URL: http://127.0.0.1:5000/admin/login")
    print(f"   Username: {ADMIN_USERNAME}")
    print(f"   Password: {ADMIN_PASSWORD}")
    print("=" * 60)
    print("📋 Admin Features:")
    print("   - View/Edit Users")
    print("   - Ban/Unban Users")
    print("   - Manage Tasks")
    print("   - Manage Announcements")
    print("   - Support Tickets")
    print("   - Payment Settings")
    print("   - Verify/Reject Payments")
    print("=" * 60)
    print("🛑 Press CTRL+C to stop the server")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000)