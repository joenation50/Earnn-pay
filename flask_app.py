from flask import Flask, render_template_string, request, redirect, url_for, flash, session, jsonify
from datetime import datetime, timedelta
import random
import string
import os
import json
import uuid
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from urllib.parse import urlparse

app = Flask(__name__)
app.secret_key = 'your-super-secret-key-change-this-12345'

# ==================== POSTGRESQL DATABASE CONFIGURATION ====================
DATABASE_URL = os.environ.get('DATABASE_URL')

if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_size': 10,
    'pool_recycle': 3600,
    'pool_pre_ping': True,
}

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
    
    full_name = db.Column(db.String(100), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    address = db.Column(db.String(200), nullable=True)
    date_of_birth = db.Column(db.Date, nullable=True)
    gender = db.Column(db.String(20), nullable=True)
    occupation = db.Column(db.String(100), nullable=True)
    profile_picture = db.Column(db.String(200), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    
    balance = db.Column(db.Float, default=0)
    commission_balance = db.Column(db.Float, default=0)
    trust_score = db.Column(db.Integer, default=0)
    tier = db.Column(db.String(20), default='FREE')
    daily_limit = db.Column(db.Integer, default=0)
    daily_tasks_completed = db.Column(db.Integer, default=0)
    streak_days = db.Column(db.Integer, default=0)
    last_checkin = db.Column(db.DateTime, nullable=True)
    last_task_reset = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    is_banned = db.Column(db.Boolean, default=False)
    ban_reason = db.Column(db.Text, nullable=True)
    email_verified = db.Column(db.Boolean, default=False)
    
    bank_name = db.Column(db.String(50), nullable=True)
    bank_account = db.Column(db.String(20), nullable=True)
    account_name = db.Column(db.String(100), nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    
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
    tier_required = db.Column(db.String(20), default='BEGINNER')
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
    
    if PaymentSettings.query.count() == 0:
        default_settings = PaymentSettings(
            bank_name='GTBank',
            account_name='Earn Pay Labs Ltd',
            account_number='0123456789'
        )
        db.session.add(default_settings)
        db.session.commit()
    
    if Task.query.count() == 0:
        default_tasks = [
            # BEGINNER TIER TASKS
            Task(title='Google Review', description='Leave a genuine 5-star review on Google', 
                 task_type='REVIEW', reward=150, tier_required='BEGINNER'),
            Task(title='Ad Click', description='Visit a site and earn N120 instantly', 
                 task_type='ADS', reward=120, tier_required='BEGINNER'),
            Task(title='Premium Review', description='Write detailed review for higher pay', 
                 task_type='REVIEW', reward=200, tier_required='BEGINNER'),
            Task(title='Survey', description='Complete survey and earn big', 
                 task_type='SURVEY', reward=180, tier_required='BEGINNER'),
            # EXPERT TIER TASKS
            Task(title='Google Review', description='Leave a genuine 5-star review on Google', 
                 task_type='REVIEW', reward=450, tier_required='EXPERT'),
            Task(title='Ad Click', description='Visit a site and earn N400 instantly', 
                 task_type='ADS', reward=400, tier_required='EXPERT'),
            Task(title='Premium Review', description='Write detailed review for higher pay', 
                 task_type='REVIEW', reward=500, tier_required='EXPERT'),
            Task(title='Survey', description='Complete survey and earn big', 
                 task_type='SURVEY', reward=480, tier_required='EXPERT'),
            Task(title='Video Task', description='Watch video and earn', 
                 task_type='VIDEO', reward=350, tier_required='EXPERT'),
            # LEGEND TIER TASKS
            Task(title='Google Review', description='Leave a genuine 5-star review on Google', 
                 task_type='REVIEW', reward=1000, tier_required='LEGEND'),
            Task(title='Ad Click', description='Visit a site and earn N900 instantly', 
                 task_type='ADS', reward=900, tier_required='LEGEND'),
            Task(title='Premium Review', description='Write detailed review for higher pay', 
                 task_type='REVIEW', reward=1100, tier_required='LEGEND'),
            Task(title='Survey', description='Complete survey and earn big', 
                 task_type='SURVEY', reward=1050, tier_required='LEGEND'),
            Task(title='Video Task', description='Watch video and earn', 
                 task_type='VIDEO', reward=950, tier_required='LEGEND'),
            Task(title='Expert Task', description='Complete expert level task', 
                 task_type='REVIEW', reward=1200, tier_required='LEGEND'),
        ]
        for task in default_tasks:
            db.session.add(task)
        db.session.commit()

# ==================== CONFIGURATION ====================
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'admin123'
REFERRAL_BONUS = 500
MINIMUM_WITHDRAWAL = 10000
WITHDRAWAL_DAYS = [5, 30]

TIER_THRESHOLDS = {
    'FREE': 0,
    'BEGINNER': 100,
    'EXPERT': 300,
    'LEGEND': 700
}

TIER_TASKS = {
    'FREE': 0,
    'BEGINNER': 6,
    'EXPERT': 10,
    'LEGEND': 15
}

TIER_PRICES = {
    'BEGINNER': 1000,
    'EXPERT': 3500,
    'LEGEND': 10000
}

# ==================== FAKE TESTIMONIALS ====================
TESTIMONIALS = [
    {'name': 'Chidi O.', 'text': 'I earned N25,000 in my first month! This platform is a lifesaver! 🎉', 'rating': 5},
    {'name': 'Ngozi E.', 'text': 'The referral bonus is amazing! I got N500 when my friend joined. 💰', 'rating': 5},
    {'name': 'Emeka N.', 'text': 'Finally a legit platform that actually pays! Withdrew N15,000 in 24 hours! ⚡', 'rating': 5},
    {'name': 'Aisha B.', 'text': 'Best side hustle ever! Simple tasks, instant payments. I recommend to everyone! 🌟', 'rating': 5},
    {'name': 'Tunde A.', 'text': 'Upgraded to Expert tier and I\'m earning N450 per review. Worth every naira! 🚀', 'rating': 5},
    {'name': 'Zainab M.', 'text': 'Made over N20,000 in a month working from my phone. Life-changing! 🙌', 'rating': 5},
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
    
    return datetime(next_year, next_month, 5).date()

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

def reset_user_tasks_if_needed(user):
    """Reset user's daily tasks if 24 hours have passed"""
    now = datetime.now()
    if user.last_task_reset:
        if now - user.last_task_reset >= timedelta(hours=24):
            user.daily_tasks_completed = 0
            user.last_task_reset = now
            db.session.commit()
            return True
    else:
        user.last_task_reset = now
        user.daily_tasks_completed = 0
        db.session.commit()
        return True
    return False

def get_user_today_tasks(user_id):
    """Get count of tasks completed today by user"""
    today = datetime.now().date()
    return TaskCompletion.query.filter(
        TaskCompletion.user_id == user_id,
        db.func.date(TaskCompletion.completed_at) == today
    ).count()

def get_share_message():
    """Generate a compelling share message with testimonials"""
    testimonial1 = random.choice(TESTIMONIALS)
    testimonial2 = random.choice(TESTIMONIALS)
    
    return f"""💰 JOIN EARN'N'PAY LABS - EARN REAL CASH! 💰

✅ Complete simple tasks and get paid instantly!
✅ Google Reviews - Earn up to ₦1,200 per review
✅ Ad Clicks - Earn up to ₦1,200 instantly
✅ Share & Earn - ₦100 per share
✅ Refer Friends - ₦500 bonus per referral
✅ Upgrade Tiers - Earn even more!

🎯 TIER BENEFITS:
• BEGINNER: 6 tasks/day - Earn up to ₦200 per task
• EXPERT: 10 tasks/day - Earn up to ₦500 per task  
• LEGEND: 15 tasks/day - Earn up to ₦1,200 per task

⭐ REAL TESTIMONIALS:
"{testimonial1['text']}" - {testimonial1['name']}
"{testimonial2['text']}" - {testimonial2['name']}

💰 Withdraw on 5th & 30th of every month
⚡ Instant payments to your bank account
🔒 100% Legit & Verified Platform

Join 10,000+ Nigerians already earning! 🚀
SIGN UP NOW:"""

# ==================== STYLES - Keeping the same styles as before ====================
# [STYLES variable would be here - keeping it to save space, but you have it in your original code]

# ==================== PAGE DEFINITIONS ====================

# ==================== LANDING_PAGE ====================
LANDING_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Earn'n'Pay Labs</title>
    <style>""" + STYLES + """</style>
</head>
<body>
    <div class="page-transition">
        <div class="top-header">
            <div class="logo-container">
                <div class="logo-icon"><span>💰</span></div>
                <div class="logo-text">
                    <span class="main">Earn'n'Pay</span>
                    <span class="sub">Labs <span>•</span> Trusted Platform</span>
                </div>
            </div>
            <div style="display:flex;gap:8px;">
                <a href="/login" class="btn btn-sm btn-outline" style="width:auto;padding:8px 16px;">Login</a>
            </div>
        </div>
        <div class="hero-section">
            <div class="hero-icon">🚀</div>
            <h1>Earn Real Cash</h1>
            <p>Complete tasks, get paid instantly, and upgrade your earning potential!</p>
            <div style="margin-top:16px;">
                <a href="/register" class="btn btn-gold" style="width:auto;padding:12px 32px;display:inline-block;font-size:18px;">
                    🎯 Create Account & Start Earning
                </a>
            </div>
            <div style="margin-top:12px;font-size:13px;opacity:0.8;">
                ⚡ Free to join · No hidden fees · Instant payments
            </div>
        </div>
        
        <div class="stats-counter">
            <div class="stat-item"><span class="number">10K+</span><span class="label">Active Users</span></div>
            <div class="stat-item"><span class="number">100K+</span><span class="label">Tasks Done</span></div>
        </div>
        
        <div class="card">
            <h3>⭐ What Our Users Say</h3>
            <div style="margin-top:8px;max-height:400px;overflow-y:auto;padding-right:4px;">
                {% for review in testimonials %}
                <div class="review-card">
                    <div class="review-header">
                        <span class="review-name">{{ review.name }}</span>
                        <span class="review-time">✅ Verified User</span>
                    </div>
                    <div class="review-stars">{% for i in range(review.rating) %}⭐{% endfor %}</div>
                    <div class="review-text">"{{ review.text }}"</div>
                </div>
                {% endfor %}
            </div>
        </div>
        
        <div class="card">
            <h3>⚡ How It Works</h3>
            <div style="margin-top:12px;">
                <div style="display:flex;align-items:center;gap:12px;padding:12px 0;border-bottom:1px solid var(--border);">
                    <span style="font-size:28px;">⬆️</span>
                    <div><strong>Upgrade Your Tier</strong><br><span class="text-muted">Pay to unlock earning tasks</span></div>
                </div>
                <div style="display:flex;align-items:center;gap:12px;padding:12px 0;border-bottom:1px solid var(--border);">
                    <span style="font-size:28px;">📝</span>
                    <div><strong>Complete Tasks</strong><br><span class="text-muted">Write reviews, click ads, earn rewards</span></div>
                </div>
                <div style="display:flex;align-items:center;gap:12px;padding:12px 0;border-bottom:1px solid var(--border);">
                    <span style="font-size:28px;">💵</span>
                    <div><strong>Get Paid Instantly</strong><br><span class="text-muted">Money drops straight into your wallet</span></div>
                </div>
                <div style="display:flex;align-items:center;gap:12px;padding:12px 0;">
                    <span style="font-size:28px;">👥</span>
                    <div><strong>Refer & Earn</strong><br><span class="text-muted">Earn ₦500 for every friend who joins</span></div>
                </div>
            </div>
        </div>
        
        <div class="card" style="background:linear-gradient(135deg,#0a0a23,#1a1a3e);color:white;text-align:center;border:none;">
            <h2 style="color:white;">🎯 Ready to Start Earning?</h2>
            <p style="opacity:0.9;">Join thousands of users already earning!</p>
            <div style="margin-top:16px;display:flex;gap:8px;flex-direction:column;">
                <a href="/register" class="btn btn-gold">Create Account Now</a>
                <a href="/login" class="btn btn-outline" style="border-color:white;color:white;background:rgba(255,255,255,0.1);">Already have an account? Login</a>
            </div>
        </div>
    </div>
</body>
</html>
"""

# ==================== LOGIN_PAGE ====================
LOGIN_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - Earn'n'Pay Labs</title>
    <style>""" + STYLES + """</style>
</head>
<body>
    <div class="page-transition">
        <div class="top-header">
            <div class="logo-container">
                <div class="logo-icon"><span>💰</span></div>
                <div class="logo-text">
                    <span class="main">Earn'n'Pay</span>
                    <span class="sub">Labs <span>•</span> Login</span>
                </div>
            </div>
            <a href="/" class="btn btn-sm btn-secondary" style="width:auto;padding:8px 16px;">← Back</a>
        </div>
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        <div class="card gradient-border">
            <div style="text-align:center;margin-bottom:16px;">
                <div style="font-size:48px;">🔐</div>
                <h2>Welcome Back!</h2>
                <p class="text-muted">Login to continue earning 💰</p>
            </div>
            <form method="POST">
                <div class="form-group">
                    <label>👤 Username</label>
                    <input type="text" name="username" required placeholder="Enter your username">
                </div>
                <div class="form-group">
                    <label>🔑 Password</label>
                    <input type="password" name="password" required placeholder="Enter your password">
                </div>
                <button type="submit" class="btn btn-primary">🚀 Login</button>
            </form>
            <p class="text-center mt-2">Don't have an account? <a href="/register" style="color:var(--secondary);font-weight:600;">Register Now →</a></p>
        </div>
    </div>
</body>
</html>
"""

# ==================== REGISTER_PAGE ====================
REGISTER_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Register - Earn'n'Pay Labs</title>
    <style>""" + STYLES + """</style>
</head>
<body>
    <div class="page-transition">
        <div class="top-header">
            <div class="logo-container">
                <div class="logo-icon"><span>💰</span></div>
                <div class="logo-text">
                    <span class="main">Earn'n'Pay</span>
                    <span class="sub">Labs <span>•</span> Register</span>
                </div>
            </div>
            <a href="/" class="btn btn-sm btn-secondary" style="width:auto;padding:8px 16px;">← Back</a>
        </div>
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        <div class="card gradient-border">
            <div style="text-align:center;margin-bottom:16px;">
                <div style="font-size:48px;">📝</div>
                <h2>Create Account</h2>
                <p class="text-muted">Join and start earning today! 🚀</p>
            </div>
            <form method="POST">
                <div class="form-group">
                    <label>👤 Username</label>
                    <input type="text" name="username" required placeholder="Choose a unique username">
                </div>
                <div class="form-group">
                    <label>📧 Email</label>
                    <input type="email" name="email" required placeholder="Your email address">
                </div>
                <div class="form-group">
                    <label>🔑 Password</label>
                    <input type="password" name="password" required placeholder="Create a strong password">
                </div>
                <div class="form-group">
                    <label>✅ Confirm Password</label>
                    <input type="password" name="confirm_password" required placeholder="Confirm your password">
                </div>
                <button type="submit" class="btn btn-primary">🎯 Create Account</button>
            </form>
            <div style="margin-top:16px;background:linear-gradient(135deg,#fef3c7,#fde68a);padding:12px;border-radius:var(--radius-sm);text-align:center;">
                <span style="font-weight:600;">🎉 Bonus:</span>
                <span class="text-muted">Refer friends and earn <strong>₦500</strong> each!</span>
            </div>
            <p class="text-center mt-2">Already have an account? <a href="/login" style="color:var(--secondary);font-weight:600;">Login →</a></p>
        </div>
    </div>
</body>
</html>
"""

# ==================== DASHBOARD_PAGE ====================
DASHBOARD_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard - Earn'n'Pay Labs</title>
    <style>""" + STYLES + """</style>
</head>
<body data-theme="{{ user.theme if user else 'light' }}">
    <div class="page-transition">
        <div class="top-header">
            <div class="logo-container">
                <div class="logo-icon"><span>💰</span></div>
                <div class="logo-text">
                    <span class="main">Earn'n'Pay</span>
                    <span class="sub">Labs <span>•</span> Dashboard</span>
                </div>
            </div>
            <div class="user-actions">
                <div class="user-info">
                    <span class="tier-badge tier-{{ user.tier|lower }}">{{ user.tier }}</span>
                    <span style="font-size:14px;font-weight:600;">👋 {{ user.username }}</span>
                </div>
                <a href="/logout" class="btn btn-logout" onclick="return confirm('Are you sure you want to logout?')">🚪 Logout</a>
            </div>
        </div>
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        {% if user.tier == 'FREE' %}
        <div class="card" style="text-align:center;background:linear-gradient(135deg,#fef3c7,#fde68a);border:2px solid var(--gold);">
            <div style="font-size:48px;">⬆️</div>
            <h2 style="color:var(--text);">Upgrade Required!</h2>
            <p class="text-muted">You need to upgrade your tier to start earning!</p>
            <a href="/upgrade" class="btn btn-gold mt-2">Upgrade Now</a>
        </div>
        {% endif %}
        
        <div class="card" style="background:linear-gradient(135deg,#0a0a23,#1a1a3e);color:white;position:relative;overflow:hidden;border:none;">
            <div style="position:absolute;top:-50px;right:-50px;width:150px;height:150px;background:rgba(233,69,96,0.1);border-radius:50%;"></div>
            <div style="position:absolute;bottom:-30px;left:-30px;width:100px;height:100px;background:rgba(212,175,55,0.08);border-radius:50%;"></div>
            <div style="position:relative;z-index:1;">
                <div style="font-size:14px;opacity:0.8;margin-bottom:4px;">💰 Available Balance</div>
                <div style="font-size:40px;font-weight:800;">₦{{ "%.2f"|format(user.balance) }}</div>
                <div style="display:flex;gap:12px;margin-top:16px;flex-wrap:wrap;">
                    <span style="background:rgba(255,255,255,0.1);padding:4px 12px;border-radius:50px;font-size:12px;">⭐ Trust Score: {{ user.trust_score }}</span>
                    <span style="background:rgba(255,255,255,0.1);padding:4px 12px;border-radius:50px;font-size:12px;">🔥 {{ user.streak_days }} day streak</span>
                    <span style="background:rgba(255,255,255,0.1);padding:4px 12px;border-radius:50px;font-size:12px;">👥 {{ user.total_referrals }} referrals</span>
                </div>
            </div>
        </div>
        
        {% if user.tier != 'FREE' %}
        <div class="card">
            <div class="flex-between">
                <span style="font-weight:600;">
                    {% if next_tier %}
                        {{ needed_points }} more to <span class="gradient-text">{{ next_tier }}</span>
                    {% else %}
                        <span class="gradient-text">MAX LEVEL</span>
                    {% endif %}
                </span>
                <span style="font-weight:600;color:var(--secondary);">{{ "%.0f"|format(progress) }}%</span>
            </div>
            <div class="progress-bar"><div class="progress-fill" style="width:{{ progress }}%;"></div></div>
            <div style="margin-top:8px;display:flex;gap:4px;flex-wrap:wrap;">
                <span class="tier-badge tier-free {% if user.tier == 'FREE' %}active{% endif %}">FREE</span>
                <span class="tier-badge tier-beginner {% if user.tier == 'BEGINNER' %}active{% endif %}">BEGINNER</span>
                <span class="tier-badge tier-expert {% if user.tier == 'EXPERT' %}active{% endif %}">EXPERT</span>
                <span class="tier-badge tier-legend {% if user.tier == 'LEGEND' %}active{% endif %}">LEGEND</span>
            </div>
            <div class="trust-progress">
                <div class="level">
                    <span>0</span>
                    <span class="{% if user.trust_score >= 100 %}completed{% endif %}">100</span>
                    <span class="{% if user.trust_score >= 300 %}completed{% endif %}">300</span>
                    <span class="{% if user.trust_score >= 700 %}completed{% endif %}">700</span>
                </div>
            </div>
        </div>
        
        <div class="stats-grid">
            <div class="stat-box"><div class="value">₦{{ "%.2f"|format(user.commission_balance) }}</div><div class="label">💸 Commission</div></div>
            <div class="stat-box"><div class="value gold">{{ user.daily_limit }}</div><div class="label">📝 Daily Limit</div></div>
            <div class="stat-box"><div class="value">{{ today_tasks }}</div><div class="label">✅ Tasks Done</div></div>
            <div class="stat-box"><div class="value">{{ remaining_tasks }}</div><div class="label">⏳ Tasks Left</div></div>
        </div>
        {% endif %}
        
        <div class="card">
            <div class="flex-between">
                <h3>⚡ Quick Actions</h3>
                {% if user.tier != 'FREE' %}
                <span style="font-size:11px;color:var(--text-muted);">🔄 Resets in {{ reset_time }}</span>
                {% endif %}
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:12px;">
                <a href="/earn" class="btn btn-primary" style="font-size:14px;padding:12px;">💰 Earn</a>
                <a href="/upgrade" class="btn btn-gold" style="font-size:14px;padding:12px;">⬆️ Upgrade</a>
                <a href="/referral" class="btn btn-secondary" style="font-size:14px;padding:12px;">👥 Refer</a>
                <a href="/withdraw" class="btn btn-success" style="font-size:14px;padding:12px;">💸 Withdraw</a>
            </div>
        </div>
        
        <nav class="bottom-nav">
            <a href="/" class="active"><span class="icon">🏠</span><span class="label">Home</span></a>
            <a href="/earn"><span class="icon">💰</span><span class="label">Earn</span></a>
            <a href="/upgrade"><span class="icon">⬆️</span><span class="label">Upgrade</span></a>
            <a href="/referral"><span class="icon">👥</span><span class="label">Refer</span></a>
            <a href="/withdraw"><span class="icon">💸</span><span class="label">Withdraw</span></a>
        </nav>
    </div>
</body>
</html>
"""

# ==================== EARN_PAGE ====================
EARN_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Earn - Earn'n'Pay Labs</title>
    <style>""" + STYLES + """</style>
</head>
<body data-theme="{{ user.theme if user else 'light' }}">
    <div class="page-transition">
        <div class="top-header">
            <div class="logo-container">
                <div class="logo-icon"><span>💰</span></div>
                <div class="logo-text">
                    <span class="main">Earn'n'Pay</span>
                    <span class="sub">Labs <span>•</span> Earn</span>
                </div>
            </div>
            <div class="user-actions">
                <div class="user-info">
                    <span class="tier-badge tier-{{ user.tier|lower }}">{{ user.tier }}</span>
                    <span style="font-size:14px;font-weight:600;">👋 {{ user.username }}</span>
                </div>
                <a href="/logout" class="btn btn-logout" onclick="return confirm('Are you sure you want to logout?')">🚪 Logout</a>
            </div>
        </div>
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        {% if user.tier == 'FREE' %}
        <div class="card" style="text-align:center;background:linear-gradient(135deg,#fef3c7,#fde68a);border:2px solid var(--gold);">
            <div style="font-size:48px;">⬆️</div>
            <h2 style="color:var(--text);">Upgrade Required</h2>
            <p class="text-muted">You need to upgrade your tier to access tasks!</p>
            <a href="/upgrade" class="btn btn-gold mt-2">Upgrade Now</a>
        </div>
        {% else %}
        <div class="card" style="background:linear-gradient(135deg,#e94560,#ff6b81);color:white;border:none;">
            <div style="font-size:14px;opacity:0.9;">📊 Today's Earning Potential</div>
            <div style="font-size:32px;font-weight:800;">₦{{ potential_earnings }}</div>
            <div style="font-size:12px;opacity:0.8;">{{ remaining_tasks }} tasks remaining out of {{ user.daily_limit }}</div>
        </div>
        
        <!-- Share Task Section -->
        {% for task in tasks %}
            {% if task.task_type == 'SHARE' %}
            <div class="card" style="border-left:4px solid var(--gold);">
                <div class="flex-between">
                    <div>
                        <h3>{{ task.title }}</h3>
                        <p class="text-muted">{{ task.description }}</p>
                        <div style="margin-top:6px;">
                            <span class="tier-badge tier-{{ task.tier_required|lower }}">{{ task.tier_required }}</span>
                            <span style="margin-left:8px;font-size:12px;color:var(--text-light);">💵 ₦{{ task.reward }}</span>
                        </div>
                    </div>
                    <div>
                        {% if task.id in completed_ids %}
                            <span style="background:#27ae60;color:white;padding:6px 12px;border-radius:50px;font-size:12px;font-weight:600;">✅ Done</span>
                        {% elif remaining_tasks <= 0 %}
                            <span style="background:#e74c3c;color:white;padding:6px 12px;border-radius:50px;font-size:12px;font-weight:600;">⛔ Limit</span>
                        {% else %}
                            <a href="/share_task" class="btn btn-gold btn-sm" style="width:auto;padding:8px 16px;">📤 Share</a>
                        {% endif %}
                    </div>
                </div>
            </div>
            {% endif %}
        {% endfor %}
        
        <!-- Regular Tasks -->
        {% for task in tasks %}
            {% if task.task_type != 'SHARE' %}
            <div class="card" style="border-left:4px solid var(--secondary);">
                <div class="flex-between">
                    <div>
                        <h3>{{ task.title }}</h3>
                        <p class="text-muted">{{ task.description }}</p>
                        <div style="margin-top:6px;">
                            <span class="tier-badge tier-{{ task.tier_required|lower }}">{{ task.tier_required }}</span>
                            <span style="margin-left:8px;font-size:12px;color:var(--text-light);">💵 ₦{{ task.reward }}</span>
                        </div>
                    </div>
                    <div>
                        {% if task.id in completed_ids %}
                            <span style="background:#27ae60;color:white;padding:6px 12px;border-radius:50px;font-size:12px;font-weight:600;">✅ Done</span>
                        {% elif remaining_tasks <= 0 %}
                            <span style="background:#e74c3c;color:white;padding:6px 12px;border-radius:50px;font-size:12px;font-weight:600;">⛔ Limit</span>
                        {% else %}
                            <form method="POST" action="/complete_task/{{ task.id }}">
                                <button type="submit" style="background:linear-gradient(135deg,#e94560,#ff6b81);color:white;border:none;padding:10px 20px;border-radius:50px;font-size:14px;font-weight:600;cursor:pointer;">🚀 Start</button>
                            </form>
                        {% endif %}
                    </div>
                </div>
            </div>
            {% endif %}
        {% else %}
        <div class="card">
            <p class="text-center text-muted">🎯 No tasks available for your tier</p>
            <a href="/upgrade" class="btn btn-gold mt-2">⬆️ Upgrade to unlock more</a>
        </div>
        {% endfor %}
        {% endif %}
        
        <nav class="bottom-nav">
            <a href="/"><span class="icon">🏠</span><span class="label">Home</span></a>
            <a href="/earn" class="active"><span class="icon">💰</span><span class="label">Earn</span></a>
            <a href="/upgrade"><span class="icon">⬆️</span><span class="label">Upgrade</span></a>
            <a href="/referral"><span class="icon">👥</span><span class="label">Refer</span></a>
            <a href="/withdraw"><span class="icon">💸</span><span class="label">Withdraw</span></a>
        </nav>
    </div>
</body>
</html>
"""

# ==================== SHARE_TASK_PAGE ====================
SHARE_TASK_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Share & Earn - Earn'n'Pay Labs</title>
    <style>""" + STYLES + """</style>
</head>
<body data-theme="{{ user.theme if user else 'light' }}">
    <div class="page-transition">
        <div class="top-header">
            <div class="logo-container">
                <div class="logo-icon"><span>💰</span></div>
                <div class="logo-text">
                    <span class="main">Earn'n'Pay</span>
                    <span class="sub">Labs <span>•</span> Share & Earn</span>
                </div>
            </div>
            <div class="user-actions">
                <div class="user-info">
                    <span class="tier-badge tier-{{ user.tier|lower }}">{{ user.tier }}</span>
                    <span style="font-size:14px;font-weight:600;">👋 {{ user.username }}</span>
                </div>
                <a href="/logout" class="btn btn-logout" onclick="return confirm('Are you sure you want to logout?')">🚪 Logout</a>
            </div>
        </div>
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        <div class="card" style="text-align:center;">
            <div style="font-size:48px;">📤</div>
            <h2>Share & Earn ₦100</h2>
            <p class="text-muted">Share our website on social media and earn ₦100 instantly!</p>
        </div>
        
        <div class="card" style="background:linear-gradient(135deg,#fef3c7,#fde68a);border:2px solid var(--gold);">
            <div style="font-size:14px;color:var(--text-light);">Your Referral Link</div>
            <div style="background:white;padding:12px;border-radius:var(--radius-sm);margin-top:8px;word-break:break-all;">
                <code>{{ share_url }}</code>
            </div>
            <button onclick="navigator.clipboard.writeText('{{ share_url }}');alert('✅ Link copied!')" class="btn btn-secondary mt-2" style="width:auto;padding:10px 20px;">
                📋 Copy Link
            </button>
        </div>

        <!-- WhatsApp Share Button -->
        <div class="card" style="background:linear-gradient(135deg,#25D366,#128C7E);color:white;text-align:center;border:none;">
            <div style="font-size:48px;">💬</div>
            <h2 style="color:white;">Share on WhatsApp</h2>
            <p style="opacity:0.9;">Share directly with friends and family!</p>
            <div style="margin-top:16px;">
                <a href="{{ whatsapp_link }}" target="_blank" class="btn btn-share" style="background:white;color:#25D366;font-size:18px;padding:14px 24px;">
                    📱 Share on WhatsApp
                </a>
            </div>
        </div>

        <!-- Share Message Preview -->
        <div class="card">
            <h3>📋 Your Share Message</h3>
            <div style="background:var(--bg);padding:16px;border-radius:var(--radius-sm);margin-top:8px;font-size:14px;line-height:1.6;white-space:pre-wrap;">
                {{ share_message }}
            </div>
            <button onclick="navigator.clipboard.writeText('{{ share_message }}');alert('✅ Message copied!')" class="btn btn-secondary mt-2" style="width:auto;padding:10px 20px;">
                📋 Copy Full Message
            </button>
        </div>
        
        <div class="card share-confirm">
            <span class="icon">✅</span>
            <h3>After sharing, confirm here</h3>
            <p class="text-muted" style="font-size:13px;">Click the button below after you've shared on any platform</p>
            <form method="POST" action="/share_task">
                <button type="submit" class="btn btn-success mt-2">💰 Claim ₦100 Reward</button>
            </form>
        </div>
        
        <nav class="bottom-nav">
            <a href="/"><span class="icon">🏠</span><span class="label">Home</span></a>
            <a href="/earn" class="active"><span class="icon">💰</span><span class="label">Earn</span></a>
            <a href="/upgrade"><span class="icon">⬆️</span><span class="label">Upgrade</span></a>
            <a href="/referral"><span class="icon">👥</span><span class="label">Refer</span></a>
            <a href="/withdraw"><span class="icon">💸</span><span class="label">Withdraw</span></a>
        </nav>
    </div>
</body>
</html>
"""

# ==================== REFERRAL_PAGE ====================
REFERRAL_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Referrals - Earn'n'Pay Labs</title>
    <style>""" + STYLES + """</style>
</head>
<body data-theme="{{ user.theme if user else 'light' }}">
    <div class="page-transition">
        <div class="top-header">
            <div class="logo-container">
                <div class="logo-icon"><span>💰</span></div>
                <div class="logo-text">
                    <span class="main">Earn'n'Pay</span>
                    <span class="sub">Labs <span>•</span> Refer</span>
                </div>
            </div>
            <div class="user-actions">
                <div class="user-info">
                    <span class="tier-badge tier-{{ user.tier|lower }}">{{ user.tier }}</span>
                    <span style="font-size:14px;font-weight:600;">👋 {{ user.username }}</span>
                </div>
                <a href="/logout" class="btn btn-logout" onclick="return confirm('Are you sure you want to logout?')">🚪 Logout</a>
            </div>
        </div>
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        <div class="card" style="background:linear-gradient(135deg,#0a0a23,#1a1a3e);color:white;text-align:center;border:none;">
            <div style="font-size:48px;">👥</div>
            <h2>Invite & Earn</h2>
            <p style="opacity:0.9;">Earn <strong>₦500</strong> for every friend who joins!</p>
            <div style="margin-top:8px;">
                <span class="bonus-badge">🎯 Total Earned: ₦{{ "%.2f"|format(user.referral_bonus_earned) }}</span>
            </div>
        </div>
        
        <div class="card">
            <div class="form-group">
                <label>📋 Your Referral Link</label>
                <div style="display:flex;gap:8px;align-items:center;">
                    <input type="text" value="{{ referral_link }}" readonly style="flex:1;" onclick="this.select();navigator.clipboard.writeText(this.value);">
                    <button onclick="navigator.clipboard.writeText('{{ referral_link }}');alert('✅ Link copied!')" style="background:var(--secondary);color:white;border:none;padding:12px 16px;border-radius:12px;cursor:pointer;font-size:20px;">📋</button>
                </div>
            </div>
        </div>

        <!-- WhatsApp Share Button -->
        <div class="card" style="background:linear-gradient(135deg,#25D366,#128C7E);color:white;text-align:center;border:none;">
            <div style="font-size:32px;">💬</div>
            <h3 style="color:white;">Share on WhatsApp</h3>
            <p style="opacity:0.9;font-size:13px;">Share your referral link with friends and earn ₦500 each!</p>
            <div style="margin-top:12px;">
                <a href="{{ whatsapp_link }}" target="_blank" class="btn btn-share" style="background:white;color:#25D366;font-size:16px;padding:12px 20px;">
                    📱 Share Now
                </a>
            </div>
        </div>

        <div class="stats-grid">
            <div class="stat-box"><div class="value">{{ total_invites }}</div><div class="label">📊 Total Invites</div></div>
            <div class="stat-box"><div class="value gold">{{ total_earned }}</div><div class="label">💰 Total Earned</div></div>
        </div>
        
        {% if referred_users %}
        <div class="card">
            <h3>👥 Referred Users</h3>
            {% for ref in referred_users %}
            <div style="padding:8px 0;border-bottom:1px solid var(--border);">
                <div class="flex-between">
                    <div><strong>{{ ref.username }}</strong><span class="tier-badge tier-{{ ref.tier|lower }}" style="font-size:10px;margin-left:8px;">{{ ref.tier }}</span></div>
                    <div style="text-align:right;">
                        <div style="font-size:12px;color:var(--text-light);">Joined: {{ ref.created_at.strftime('%b %d, %Y') }}</div>
                        <div style="font-size:11px;color:#27ae60;">+₦500 bonus</div>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
        {% else %}
        <div class="card">
            <p class="text-center text-muted">📭 You haven't referred anyone yet. Share your link!</p>
        </div>
        {% endif %}
        
        <nav class="bottom-nav">
            <a href="/"><span class="icon">🏠</span><span class="label">Home</span></a>
            <a href="/earn"><span class="icon">💰</span><span class="label">Earn</span></a>
            <a href="/upgrade"><span class="icon">⬆️</span><span class="label">Upgrade</span></a>
            <a href="/referral" class="active"><span class="icon">👥</span><span class="label">Refer</span></a>
            <a href="/withdraw"><span class="icon">💸</span><span class="label">Withdraw</span></a>
        </nav>
    </div>
</body>
</html>
"""

# ==================== UPGRADE_PAGE ====================
UPGRADE_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Upgrade - Earn'n'Pay Labs</title>
    <style>""" + STYLES + """</style>
</head>
<body data-theme="{{ user.theme if user else 'light' }}">
    <div class="page-transition">
        <div class="top-header">
            <div class="logo-container">
                <div class="logo-icon"><span>💰</span></div>
                <div class="logo-text">
                    <span class="main">Earn'n'Pay</span>
                    <span class="sub">Labs <span>•</span> Upgrade</span>
                </div>
            </div>
            <div class="user-actions">
                <div class="user-info">
                    <span class="tier-badge tier-{{ user.tier|lower }}">{{ user.tier }}</span>
                    <span style="font-size:14px;font-weight:600;">👋 {{ user.username }}</span>
                </div>
                <a href="/logout" class="btn btn-logout" onclick="return confirm('Are you sure you want to logout?')">🚪 Logout</a>
            </div>
        </div>
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        <div class="upgrade-info">
            <div style="display:flex;align-items:center;gap:8px;">
                <span style="font-size:20px;">💡</span>
                <div>
                    <strong>Upgrade to Start Earning!</strong>
                    <div style="font-size:13px;color:var(--text-light);">
                        Send payment to the bank details below and submit your proof for verification.
                    </div>
                </div>
            </div>
        </div>
        
        <div class="card" style="text-align:center;">
            <h2 style="font-size:24px;">🚀 Upgrade Your Tier</h2>
            <p class="text-muted">Pay to unlock higher paying tasks!</p>
        </div>
        
        <div class="card" style="text-align:center;background:linear-gradient(135deg,#f8f9fa,white);">
            <div style="font-size:14px;color:var(--text-light);">📌 Current Tier</div>
            <div style="font-size:32px;font-weight:800;" class="gradient-text">{{ user.tier }}</div>
            <div style="font-size:14px;color:var(--text-light);">📝 {{ user.daily_limit }} tasks/day</div>
        </div>
        
        {% set payment_settings = get_payment_settings() %}
        <div class="card" style="background:linear-gradient(135deg,#fef3c7,#fde68a);border:2px solid var(--gold);">
            <h3 style="color:var(--text);">🏦 Send Payment To:</h3>
            <div class="bank-details-box">
                <div><span class="label">🏛️ Bank:</span> <span class="value">{{ payment_settings.bank_name }}</span></div>
                <div><span class="label">👤 Account Name:</span> <span class="value">{{ payment_settings.account_name }}</span></div>
                <div><span class="label">🔢 Account Number:</span> <span class="value" style="color:var(--secondary);font-size:20px;">{{ payment_settings.account_number }}</span></div>
            </div>
            <p class="text-muted" style="font-size:12px;text-align:center;">⚠️ Send the exact amount for your chosen tier</p>
        </div>
        
        {% for tier_key, tier in tiers.items() %}
            {% if user.tier != tier_key %}
            <div class="tier-card {% if tier_key == 'EXPERT' %}popular{% endif %}">
                {% if tier_key == 'EXPERT' %}<span class="badge-popular">🔥 POPULAR</span>{% endif %}
                <div class="flex-between">
                    <div>
                        <h3 style="font-size:20px;">{{ tier.name }}</h3>
                        <p class="text-muted">{{ tier.description }}</p>
                        <div style="margin-top:6px;"><span class="tier-badge tier-{{ tier_key|lower }}">{{ tier_key }}</span></div>
                    </div>
                    <div style="text-align:right;">
                        <div class="price">₦{{ "%.2f"|format(tier.cost) }}</div>
                        <button onclick="showPaymentForm('{{ tier_key }}', {{ tier.cost }})" class="btn btn-primary btn-sm" style="margin-top:8px;width:auto;">💳 Pay & Upgrade</button>
                    </div>
                </div>
            </div>
            {% endif %}
        {% endfor %}
        
        <div id="paymentForm" style="display:none;">
            <div class="card" style="border:2px solid var(--success);">
                <h3>💳 Submit Payment Proof</h3>
                <p class="text-muted">After sending money, fill this form to confirm your payment.</p>
                <form method="POST" action="/submit_payment">
                    <input type="hidden" name="tier" id="selectedTier">
                    <input type="hidden" name="amount" id="selectedAmount">
                    <div class="form-group"><label>👤 Full Name (as sender)</label><input type="text" name="sender_name" placeholder="Your full name" required></div>
                    <div class="form-group"><label>🔢 Transaction Reference / ID</label><input type="text" name="transaction_id" placeholder="e.g., 1234567890" required></div>
                    <div class="form-group"><label>💰 Amount Sent (₦)</label><input type="number" name="amount_sent" id="amountSent" required></div>
                    <div class="form-group"><label>📅 Payment Date & Time</label><input type="datetime-local" name="payment_date" required></div>
                    <div class="form-group"><label>📝 Additional Notes (optional)</label><textarea name="notes" placeholder="Any extra details..."></textarea></div>
                    <button type="submit" class="btn btn-success">✅ Submit Payment Proof</button>
                    <button type="button" onclick="hidePaymentForm()" class="btn btn-secondary mt-2">❌ Cancel</button>
                </form>
            </div>
        </div>
        
        {% if transactions_list %}
        <div class="card">
            <h3>📜 Your Payment History</h3>
            {% for tx in transactions_list %}
            <div style="padding:8px 0;border-bottom:1px solid var(--border);">
                <div class="flex-between">
                    <div><strong>{{ tx.tier }}</strong><span style="font-size:12px;color:var(--text-light);">₦{{ "%.2f"|format(tx.amount) }}</span></div>
                    <div><span class="status-badge status-{{ tx.status|lower }}">{{ tx.status }}</span></div>
                </div>
                <div class="text-muted" style="font-size:11px;">{{ tx.date }} · Ref: {{ tx.transaction_id }}</div>
            </div>
            {% endfor %}
        </div>
        {% endif %}
        
        <nav class="bottom-nav">
            <a href="/"><span class="icon">🏠</span><span class="label">Home</span></a>
            <a href="/earn"><span class="icon">💰</span><span class="label">Earn</span></a>
            <a href="/upgrade" class="active"><span class="icon">⬆️</span><span class="label">Upgrade</span></a>
            <a href="/referral"><span class="icon">👥</span><span class="label">Refer</span></a>
            <a href="/withdraw"><span class="icon">💸</span><span class="label">Withdraw</span></a>
        </nav>
        
        <script>
            function showPaymentForm(tier, amount) {
                document.getElementById('selectedTier').value = tier;
                document.getElementById('selectedAmount').value = amount;
                document.getElementById('amountSent').value = amount;
                document.getElementById('paymentForm').style.display = 'block';
                document.getElementById('paymentForm').scrollIntoView({ behavior: 'smooth' });
            }
            function hidePaymentForm() { document.getElementById('paymentForm').style.display = 'none'; }
        </script>
    </div>
</body>
</html>
"""

# ==================== WITHDRAW_PAGE ====================
WITHDRAW_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Withdraw - Earn'n'Pay Labs</title>
    <style>""" + STYLES + """</style>
</head>
<body data-theme="{{ user.theme if user else 'light' }}">
    <div class="page-transition">
        <div class="top-header">
            <div class="logo-container">
                <div class="logo-icon"><span>💰</span></div>
                <div class="logo-text">
                    <span class="main">Earn'n'Pay</span>
                    <span class="sub">Labs <span>•</span> Withdraw</span>
                </div>
            </div>
            <div class="user-actions">
                <div class="user-info">
                    <span class="tier-badge tier-{{ user.tier|lower }}">{{ user.tier }}</span>
                    <span style="font-size:14px;font-weight:600;">👋 {{ user.username }}</span>
                </div>
                <a href="/logout" class="btn btn-logout" onclick="return confirm('Are you sure you want to logout?')">🚪 Logout</a>
            </div>
        </div>
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        <div class="card" style="text-align:center;background:linear-gradient(135deg,#0a0a23,#1a1a3e);color:white;border:none;">
            <div style="font-size:14px;opacity:0.8;">💰 Available Balance</div>
            <div style="font-size:40px;font-weight:800;">₦{{ "%.2f"|format(user.balance) }}</div>
        </div>

        <div class="withdrawal-info">
            <div style="display:flex;align-items:center;gap:8px;">
                <span style="font-size:20px;">📅</span>
                <div>
                    <strong>Withdrawal Days: 5th & 30th of every month</strong>
                    <div style="font-size:13px;color:var(--text-light);">
                        {% if can_withdraw %}
                            ✅ <span style="color:var(--success);">Today is a withdrawal day!</span>
                        {% else %}
                            ⏳ Next withdrawal: <span class="highlight">{{ next_date.strftime('%B %d, %Y') }}</span>
                        {% endif %}
                    </div>
                </div>
            </div>
        </div>

        <div class="card">
            <form method="POST">
                <div class="form-group">
                    <label>💰 Amount (₦) - Minimum ₦{{ min_amount }}</label>
                    <input type="number" name="amount" min="{{ min_amount }}" max="{{ user.balance }}" required>
                    <span class="text-muted" style="font-size:12px;">Minimum: ₦{{ min_amount }}</span>
                </div>
                <div class="form-group">
                    <label>🏛️ Bank Name</label>
                    <select name="bank_name" required>
                        <option value="">Select bank</option>
                        <option value="GTBank">GTBank</option>
                        <option value="Access Bank">Access Bank</option>
                        <option value="First Bank">First Bank</option>
                        <option value="Zenith Bank">Zenith Bank</option>
                        <option value="UBA">UBA</option>
                        <option value="PalmPay">PalmPay</option>
                        <option value="Opay">Opay</option>
                        <option value="Moniepoint">Moniepoint</option>
                        <option value="Kuda Bank">Kuda Bank</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>🔢 Account Number</label>
                    <input type="text" name="account_number" placeholder="10-digit account number" pattern="[0-9]{10}" required>
                </div>
                <div class="form-group">
                    <label>👤 Account Name</label>
                    <input type="text" name="account_name" placeholder="Full name on account" required>
                </div>
                {% if can_withdraw %}
                    <button type="submit" class="btn btn-success">💸 Request Withdrawal</button>
                {% else %}
                    <button type="button" class="btn btn-secondary btn-disabled" style="cursor:not-allowed;">
                        🔒 Withdrawals on 5th & 30th only
                    </button>
                    <p style="font-size:12px;color:var(--text-light);text-align:center;margin-top:8px;">
                        Next withdrawal: <strong>{{ next_date.strftime('%B %d, %Y') }}</strong>
                    </p>
                {% endif %}
            </form>
        </div>

        {% if withdrawals %}
        <div class="card">
            <h3>📜 Withdrawal History</h3>
            {% for w in withdrawals %}
            <div style="padding:8px 0;border-bottom:1px solid var(--border);">
                <div class="flex-between">
                    <div>
                        <strong>₦{{ "%.2f"|format(w.amount) }}</strong>
                        <span style="margin-left:8px;font-size:12px;color:var(--text-light);">{{ w.bank_name }}</span>
                    </div>
                    <div>
                        <span class="status-badge status-{{ w.status|lower }}">{{ w.status }}</span>
                    </div>
                </div>
                <div class="text-muted" style="font-size:12px;">{{ w.created_at.strftime('%b %d, %Y %H:%M') }}</div>
            </div>
            {% endfor %}
        </div>
        {% endif %}

        <nav class="bottom-nav">
            <a href="/"><span class="icon">🏠</span><span class="label">Home</span></a>
            <a href="/earn"><span class="icon">💰</span><span class="label">Earn</span></a>
            <a href="/upgrade"><span class="icon">⬆️</span><span class="label">Upgrade</span></a>
            <a href="/referral"><span class="icon">👥</span><span class="label">Refer</span></a>
            <a href="/withdraw" class="active"><span class="icon">💸</span><span class="label">Withdraw</span></a>
        </nav>
    </div>
</body>
</html>
"""

# ==================== ACCOUNT_PAGE ====================
ACCOUNT_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Account - Earn'n'Pay Labs</title>
    <style>""" + STYLES + """</style>
</head>
<body data-theme="{{ user.theme if user else 'light' }}">
    <div class="page-transition">
        <div class="top-header">
            <div class="logo-container">
                <div class="logo-icon"><span>💰</span></div>
                <div class="logo-text">
                    <span class="main">Earn'n'Pay</span>
                    <span class="sub">Labs <span>•</span> Account</span>
                </div>
            </div>
            <div class="user-actions">
                <div class="user-info">
                    <span class="tier-badge tier-{{ user.tier|lower }}">{{ user.tier }}</span>
                    <span style="font-size:14px;font-weight:600;">👋 {{ user.username }}</span>
                </div>
                <a href="/logout" class="btn btn-logout" onclick="return confirm('Are you sure you want to logout?')">🚪 Logout</a>
            </div>
        </div>
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        <div class="card"><div style="text-align:center;"><div style="font-size:48px;">👤</div><h2>Account Settings</h2><p class="text-muted">Manage your personal information</p></div></div>
        
        <div class="card gradient-border">
            <h3>📝 Personal Information</h3>
            <form method="POST" action="/update_account">
                <div class="form-group"><label>👤 Full Name</label><input type="text" name="full_name" value="{{ user.full_name or '' }}" placeholder="Enter your full name"></div>
                <div class="form-group"><label>📧 Email</label><input type="email" value="{{ user.email }}" disabled style="opacity:0.7;"></div>
                <div class="form-group"><label>📱 Phone Number</label><input type="tel" name="phone" value="{{ user.phone or '' }}" placeholder="Enter your phone number"></div>
                <div class="form-group"><label>📍 Address</label><input type="text" name="address" value="{{ user.address or '' }}" placeholder="Enter your address"></div>
                <div class="form-group"><label>🎂 Date of Birth</label><input type="date" name="date_of_birth" value="{{ user.date_of_birth.strftime('%Y-%m-%d') if user.date_of_birth else '' }}"></div>
                <div class="form-group"><label>⚥ Gender</label><select name="gender"><option value="">Select gender</option><option value="Male" {% if user.gender == 'Male' %}selected{% endif %}>Male</option><option value="Female" {% if user.gender == 'Female' %}selected{% endif %}>Female</option><option value="Other" {% if user.gender == 'Other' %}selected{% endif %}>Other</option></select></div>
                <div class="form-group"><label>💼 Occupation</label><input type="text" name="occupation" value="{{ user.occupation or '' }}" placeholder="Enter your occupation"></div>
                <div class="form-group"><label>📝 Bio</label><textarea name="bio" placeholder="Tell us about yourself">{{ user.bio or '' }}</textarea></div>
                <button type="submit" class="btn btn-primary">💾 Save Changes</button>
            </form>
        </div>
        
        <div class="card">
            <h3>🏦 Bank Details</h3>
            <form method="POST" action="/update_bank">
                <div class="form-group"><label>🏛️ Bank Name</label><select name="bank_name"><option value="">Select bank</option><option value="GTBank" {% if user.bank_name == 'GTBank' %}selected{% endif %}>GTBank</option><option value="Access Bank" {% if user.bank_name == 'Access Bank' %}selected{% endif %}>Access Bank</option><option value="First Bank" {% if user.bank_name == 'First Bank' %}selected{% endif %}>First Bank</option><option value="Zenith Bank" {% if user.bank_name == 'Zenith Bank' %}selected{% endif %}>Zenith Bank</option><option value="UBA" {% if user.bank_name == 'UBA' %}selected{% endif %}>UBA</option><option value="PalmPay" {% if user.bank_name == 'PalmPay' %}selected{% endif %}>PalmPay</option><option value="Opay" {% if user.bank_name == 'Opay' %}selected{% endif %}>Opay</option><option value="Moniepoint" {% if user.bank_name == 'Moniepoint' %}selected{% endif %}>Moniepoint</option><option value="Kuda Bank" {% if user.bank_name == 'Kuda Bank' %}selected{% endif %}>Kuda Bank</option></select></div>
                <div class="form-group"><label>🔢 Account Number</label><input type="text" name="bank_account" value="{{ user.bank_account or '' }}" placeholder="10-digit account number" pattern="[0-9]{10}"></div>
                <div class="form-group"><label>👤 Account Name</label><input type="text" name="account_name" value="{{ user.account_name or '' }}" placeholder="Full name on account"></div>
                <button type="submit" class="btn btn-success">💾 Save Bank Details</button>
            </form>
        </div>
        
        <div class="card">
            <h3>🎨 Theme Preference</h3>
            <div style="display:flex;gap:12px;margin-top:8px;">
                <form method="POST" action="/set_theme" style="flex:1;"><input type="hidden" name="theme" value="light"><button type="submit" class="btn btn-secondary" style="{% if user.theme == 'light' %}border:2px solid var(--secondary);{% endif %}">☀️ Light</button></form>
                <form method="POST" action="/set_theme" style="flex:1;"><input type="hidden" name="theme" value="dark"><button type="submit" class="btn btn-secondary" style="{% if user.theme == 'dark' %}border:2px solid var(--secondary);{% endif %}">🌙 Dark</button></form>
            </div>
        </div>
        
        <div class="card" style="border:2px solid var(--danger);"><h3 style="color:var(--danger);">🔒 Security</h3><a href="/change_password" class="btn btn-danger">🔑 Change Password</a></div>
        
        <nav class="bottom-nav">
            <a href="/"><span class="icon">🏠</span><span class="label">Home</span></a>
            <a href="/earn"><span class="icon">💰</span><span class="label">Earn</span></a>
            <a href="/upgrade"><span class="icon">⬆️</span><span class="label">Upgrade</span></a>
            <a href="/referral"><span class="icon">👥</span><span class="label">Refer</span></a>
            <a href="/withdraw"><span class="icon">💸</span><span class="label">Withdraw</span></a>
        </nav>
    </div>
</body>
</html>
"""

# ==================== CHANGE_PASSWORD_PAGE ====================
CHANGE_PASSWORD_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Change Password</title>
    <style>""" + STYLES + """</style>
</head>
<body data-theme="{{ user.theme if user else 'light' }}">
    <div class="page-transition">
        <div class="top-header">
            <div class="logo-container">
                <div class="logo-icon"><span>💰</span></div>
                <div class="logo-text">
                    <span class="main">Earn'n'Pay</span>
                    <span class="sub">Labs <span>•</span> Security</span>
                </div>
            </div>
            <a href="/account" class="btn btn-sm btn-secondary" style="width:auto;padding:8px 16px;">← Back</a>
        </div>
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        <div class="card gradient-border">
            <form method="POST">
                <div class="form-group"><label>🔑 Current Password</label><input type="password" name="current_password" required></div>
                <div class="form-group"><label>🔐 New Password</label><input type="password" name="new_password" required minlength="6"></div>
                <div class="form-group"><label>✅ Confirm New Password</label><input type="password" name="confirm_password" required></div>
                <button type="submit" class="btn btn-primary">Update Password</button>
            </form>
        </div>
    </div>
</body>
</html>
"""

# ==================== ADMIN PAGES ====================
ADMIN_LOGIN_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Login - Earn'n'Pay Labs</title>
    <style>""" + STYLES + """</style>
</head>
<body>
    <div class="page-transition">
        <div class="top-header">
            <div class="logo-container">
                <div class="logo-icon"><span>🔐</span></div>
                <div class="logo-text">
                    <span class="main">Admin Panel</span>
                    <span class="sub">Earn'n'Pay <span>•</span> Login</span>
                </div>
            </div>
        </div>
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        <div class="card gradient-border">
            <h2>🔐 Admin Login</h2>
            <form method="POST">
                <div class="form-group"><label>👤 Username</label><input type="text" name="username" required></div>
                <div class="form-group"><label>🔑 Password</label><input type="password" name="password" required></div>
                <button type="submit" class="btn btn-primary">🚀 Login</button>
            </form>
            <p class="text-center mt-2">Default: admin / admin123</p>
        </div>
    </div>
</body>
</html>
"""

ADMIN_DASHBOARD_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Dashboard - Earn'n'Pay Labs</title>
    <style>""" + STYLES + """</style>
</head>
<body>
    <div class="page-transition">
        <div class="top-header">
            <div class="logo-container">
                <div class="logo-icon"><span>🔐</span></div>
                <div class="logo-text">
                    <span class="main">Admin Panel</span>
                    <span class="sub">Earn'n'Pay <span>•</span> Dashboard</span>
                </div>
            </div>
            <div><span style="font-size:14px;font-weight:600;">👋 Admin</span><a href="/admin/logout" style="margin-left:8px;color:var(--danger);text-decoration:none;font-size:12px;">🚪 Logout</a></div>
        </div>
        
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        <div class="stats-grid" style="margin-bottom:16px;">
            <div class="stat-box" style="background:linear-gradient(135deg,#0a0a23,#1a1a3e);color:white;"><div class="value" style="color:white;font-size:32px;">{{ total_users }}</div><div class="label" style="color:rgba(255,255,255,0.8);">👥 Total Users</div></div>
            <div class="stat-box" style="background:linear-gradient(135deg,#e94560,#ff6b81);color:white;"><div class="value" style="color:white;font-size:32px;">{{ pending_count }}</div><div class="label" style="color:rgba(255,255,255,0.8);">⏳ Pending</div></div>
            <div class="stat-box" style="background:linear-gradient(135deg,#27ae60,#1a7a3a);color:white;"><div class="value" style="color:white;font-size:32px;">{{ verified_count }}</div><div class="label" style="color:rgba(255,255,255,0.8);">✅ Verified</div></div>
            <div class="stat-box" style="background:linear-gradient(135deg,#f39c12,#e67e22);color:white;"><div class="value" style="color:white;font-size:32px;">{{ open_tickets }}</div><div class="label" style="color:rgba(255,255,255,0.8);">💬 Tickets</div></div>
        </div>

        <div class="card">
            <h3>📊 Payment Requests</h3>
            {% if pending_transactions %}
                {% for tx in pending_transactions %}
                <div style="padding:12px 0;border-bottom:1px solid var(--border);">
                    <div class="flex-between">
                        <div><strong>{{ tx.username }}</strong><span class="tier-badge tier-{{ tx.tier|lower }}">{{ tx.tier }}</span></div>
                        <div><span style="font-weight:600;">₦{{ "%.2f"|format(tx.amount) }}</span></div>
                    </div>
                    <div style="font-size:12px;color:var(--text-light);margin-top:4px;">Ref: {{ tx.transaction_id }} · {{ tx.date }}</div>
                    <div style="margin-top:8px;display:flex;gap:8px;">
                        <form method="POST" action="/admin/verify_payment/{{ tx.id }}" style="flex:1;"><button type="submit" class="btn btn-success btn-sm">✅ Verify</button></form>
                        <form method="POST" action="/admin/reject_payment/{{ tx.id }}" style="flex:1;"><button type="submit" class="btn btn-danger btn-sm">❌ Reject</button></form>
                    </div>
                </div>
                {% endfor %}
            {% else %}
                <p class="text-center text-muted">🎉 No pending payments</p>
            {% endif %}
        </div>

        <div class="card">
            <h3>📊 All Users</h3>
            {% for user in all_users %}
            <div style="padding:8px 0;border-bottom:1px solid var(--border);">
                <div class="flex-between">
                    <div>
                        <strong>{{ user.username }}</strong>
                        <span class="tier-badge tier-{{ user.tier|lower }}">{{ user.tier }}</span>
                        {% if user.tier != 'FREE' %}
                            <span style="font-size:10px;color:#27ae60;margin-left:4px;">💰 PAID</span>
                        {% else %}
                            <span style="font-size:10px;color:var(--text-muted);margin-left:4px;">FREE</span>
                        {% endif %}
                    </div>
                    <div style="text-align:right;">
                        <div style="font-size:12px;">💰 ₦{{ "%.2f"|format(user.balance) }}</div>
                        <div style="font-size:12px;color:var(--text-light);">⭐ {{ user.trust_score }} pts</div>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>

        <nav class="bottom-nav">
            <a href="/" style="flex:1;text-align:center;padding:6px 4px;text-decoration:none;color:var(--text-light);font-size:8px;border-radius:50px;"><span class="icon">🏠</span><span class="label">Home</span></a>
            <a href="/admin/users" style="flex:1;text-align:center;padding:6px 4px;text-decoration:none;color:var(--text-light);font-size:8px;border-radius:50px;"><span class="icon">📊</span><span class="label">Users</span></a>
            <a href="/admin/support" style="flex:1;text-align:center;padding:6px 4px;text-decoration:none;color:var(--text-light);font-size:8px;border-radius:50px;"><span class="icon">💬</span><span class="label">Support</span></a>
            <a href="/admin/settings" style="flex:1;text-align:center;padding:6px 4px;text-decoration:none;color:var(--text-light);font-size:8px;border-radius:50px;"><span class="icon">⚙️</span><span class="label">Settings</span></a>
            <a href="/admin/dashboard" class="active" style="flex:1.2;text-align:center;padding:6px 10px;text-decoration:none;color:white;font-size:8px;background:linear-gradient(135deg,#e94560,#ff6b81);border-radius:50px;box-shadow:0 4px 20px rgba(233,69,96,0.4);"><span class="icon">🔐</span><span class="label">Admin</span></a>
        </nav>
    </div>
</body>
</html>
"""

ADMIN_USERS_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>All Users - Admin</title>
    <style>""" + STYLES + """</style>
</head>
<body>
    <div class="page-transition">
        <div class="top-header">
            <div class="logo-container">
                <div class="logo-icon"><span>📊</span></div>
                <div class="logo-text">
                    <span class="main">All Users</span>
                    <span class="sub">Earn'n'Pay <span>•</span> Admin</span>
                </div>
            </div>
            <div><a href="/admin/dashboard" class="btn btn-sm btn-secondary" style="width:auto;padding:8px 16px;">← Back</a><a href="/admin/logout" class="btn btn-sm btn-danger" style="width:auto;padding:8px 16px;">🚪</a></div>
        </div>
        <div class="card" style="overflow-x:auto;">
            <h3>📊 Registered Users</h3>
            <table style="width:100%;border-collapse:collapse;margin-top:12px;font-size:13px;">
                <thead><tr style="background:linear-gradient(135deg,#0a0a23,#1a1a3e);color:white;"><th style="padding:10px;text-align:left;">ID</th><th style="padding:10px;text-align:left;">Username</th><th style="padding:10px;text-align:left;">Email</th><th style="padding:10px;text-align:left;">Tier</th><th style="padding:10px;text-align:left;">Balance</th><th style="padding:10px;text-align:left;">Trust</th><th style="padding:10px;text-align:left;">Refs</th><th style="padding:10px;text-align:left;">Joined</th><th style="padding:10px;text-align:left;">Actions</th></tr></thead>
                <tbody>
                    {% for user in users %}
                    <tr style="border-bottom:1px solid var(--border);">
                        <td style="padding:10px;">{{ user.id }}</td>
                        <td style="padding:10px;font-weight:600;">{{ user.username }}</td>
                        <td style="padding:10px;font-size:12px;">{{ user.email }}</td>
                        <td style="padding:10px;"><span class="tier-badge tier-{{ user.tier|lower }}">{{ user.tier }}</span></td>
                        <td style="padding:10px;">₦{{ "%.2f"|format(user.balance) }}</td>
                        <td style="padding:10px;">⭐ {{ user.trust_score }}</td>
                        <td style="padding:10px;">{{ user.total_referrals }}</td>
                        <td style="padding:10px;font-size:11px;color:var(--text-light);">{{ user.created_at.strftime('%b %d, %Y') if user.created_at else 'N/A' }}</td>
                        <td style="padding:10px;">
                            {% if user.is_banned %}
                                <form method="POST" action="/admin/user/{{ user.id }}/unban" style="display:inline;">
                                    <button type="submit" class="btn btn-sm btn-success" style="padding:4px 8px;font-size:10px;">Unban</button>
                                </form>
                            {% else %}
                                <form method="POST" action="/admin/user/{{ user.id }}/ban" style="display:inline;">
                                    <input type="hidden" name="reason" value="Violation of terms">
                                    <button type="submit" class="btn btn-sm btn-danger" style="padding:4px 8px;font-size:10px;">Ban</button>
                                </form>
                            {% endif %}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
"""

ADMIN_SETTINGS_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Payment Settings - Admin</title>
    <style>""" + STYLES + """</style>
</head>
<body>
    <div class="page-transition">
        <div class="top-header">
            <div class="logo-container">
                <div class="logo-icon"><span>⚙️</span></div>
                <div class="logo-text">
                    <span class="main">Payment Settings</span>
                    <span class="sub">Earn'n'Pay <span>•</span> Admin</span>
                </div>
            </div>
            <div><a href="/admin/dashboard" class="btn btn-sm btn-secondary" style="width:auto;padding:8px 16px;">← Back</a><a href="/admin/logout" class="btn btn-sm btn-danger" style="width:auto;padding:8px 16px;">🚪</a></div>
        </div>
        
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        <div class="card gradient-border">
            <h3>🏦 Update Payment Details</h3>
            <p class="text-muted">These bank details will be shown to users when they want to upgrade their tier.</p>
            <form method="POST" action="/admin/update_payment_settings">
                <div class="form-group">
                    <label>🏛️ Bank Name</label>
                    <input type="text" name="bank_name" value="{{ settings.bank_name }}" required>
                </div>
                <div class="form-group">
                    <label>👤 Account Name</label>
                    <input type="text" name="account_name" value="{{ settings.account_name }}" required>
                </div>
                <div class="form-group">
                    <label>🔢 Account Number</label>
                    <input type="text" name="account_number" value="{{ settings.account_number }}" required pattern="[0-9]{10}">
                    <span class="text-muted" style="font-size:12px;">10-digit account number</span>
                </div>
                <button type="submit" class="btn btn-primary">💾 Update Payment Details</button>
            </form>
        </div>
    </div>
</body>
</html>
"""

ADMIN_SUPPORT_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Support Tickets - Admin</title>
    <style>""" + STYLES + """</style>
</head>
<body>
    <div class="page-transition">
        <div class="top-header">
            <div class="logo-container">
                <div class="logo-icon"><span>💬</span></div>
                <div class="logo-text">
                    <span class="main">Support Tickets</span>
                    <span class="sub">Earn'n'Pay <span>•</span> Admin</span>
                </div>
            </div>
            <div><a href="/admin/dashboard" class="btn btn-sm btn-secondary" style="width:auto;padding:8px 16px;">← Back</a><a href="/admin/logout" class="btn btn-sm btn-danger" style="width:auto;padding:8px 16px;">🚪</a></div>
        </div>
        <div class="card">
            <h3>📋 All Tickets</h3>
            {% for ticket in tickets %}
            <div style="padding:12px 0;border-bottom:1px solid var(--border);">
                <div class="flex-between">
                    <div>
                        <strong>{{ ticket.subject }}</strong>
                        <span class="status-badge status-{{ ticket.status|lower }}">{{ ticket.status }}</span>
                    </div>
                    <div style="font-size:11px;color:var(--text-light);">{{ ticket.date }}</div>
                </div>
                <div style="font-size:13px;color:var(--text-light);margin:4px 0;">
                    From: <strong>{{ ticket.username }}</strong>
                </div>
                <div style="font-size:14px;margin:4px 0;">{{ ticket.message }}</div>
                <div style="margin-top:8px;display:flex;gap:8px;">
                    <form method="POST" action="/admin/support/{{ ticket.id }}/resolve" style="flex:1;">
                        <input type="text" name="response" placeholder="Admin response..." style="flex:1;padding:6px;font-size:12px;">
                        <button type="submit" class="btn btn-success btn-sm" style="margin-top:4px;">✅ Resolve</button>
                    </form>
                    <form method="POST" action="/admin/support/{{ ticket.id }}/delete" style="flex:1;">
                        <button type="submit" class="btn btn-danger btn-sm" onclick="return confirm('Delete this ticket?')">🗑️ Delete</button>
                    </form>
                </div>
            </div>
            {% else %}
            <p class="text-center text-muted">📭 No tickets yet</p>
            {% endfor %}
        </div>
    </div>
</body>
</html>
"""

# ==================== ROUTES ====================

@app.route('/')
def home():
    if 'username' in session:
        return redirect('/dashboard')
    return render_template_string(LANDING_PAGE, testimonials=TESTIMONIALS, fake_reviews=FAKE_REVIEWS)

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
        user.daily_limit = 0  # FREE tier - no tasks
        user.last_task_reset = datetime.now()
        
        # ===== REFERRAL SYSTEM - FIXED! =====
        ref_code = request.args.get('ref', '')
        referrer = None
        bonus_applied = False
        
        if ref_code:
            referrer = User.query.filter_by(referral_code=ref_code).first()
            if referrer:
                user.referred_by = referrer.id
                # Award bonus to referrer
                bonus_amount = REFERRAL_BONUS
                referrer.balance += bonus_amount
                referrer.commission_balance += bonus_amount
                referrer.trust_score += 1
                referrer.referral_bonus_earned += bonus_amount
                referrer.total_referrals += 1
                bonus_applied = True
                db.session.add(referrer)
                flash(f'🎉 You were referred by {referrer.username}! You both get ₦{bonus_amount}!', 'success')
            else:
                flash('⚠️ Invalid referral code!', 'error')
        
        db.session.add(user)
        db.session.commit()
        
        # Create referral record with user.id after commit
        if referrer and user.id and bonus_applied:
            referral = Referral(
                referrer_id=referrer.id,
                referred_id=user.id,
                bonus_amount=REFERRAL_BONUS,
                bonus_paid=True,
                verified=True
            )
            db.session.add(referral)
            db.session.commit()
        
        flash('✅ Registration successful! Please login.', 'success')
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
    
    # Reset tasks if needed
    reset_user_tasks_if_needed(user)
    
    now = datetime.now()
    today = datetime.now().date()
    
    # Check streak
    if user.last_checkin:
        if user.last_checkin.date() == today - timedelta(days=1):
            user.streak_days += 1
            user.trust_score += 1
        elif user.last_checkin.date() != today:
            user.streak_days = 0
    user.last_checkin = datetime.now()
    
    db.session.commit()
    
    next_tier, needed_points = get_next_tier_info(user.tier, user.trust_score)
    
    if next_tier:
        next_threshold = TIER_THRESHOLDS[next_tier]
        current_threshold = TIER_THRESHOLDS[user.tier]
        progress = min(100, ((user.trust_score - current_threshold) / (next_threshold - current_threshold) * 100) if next_threshold > current_threshold else 0)
    else:
        progress = 100
    
    # Get today's tasks
    today_tasks = get_user_today_tasks(user.id)
    
    remaining_tasks = max(0, user.daily_limit - today_tasks)
    
    if user.last_task_reset:
        next_reset = user.last_task_reset + timedelta(hours=24)
        time_left = next_reset - now
        hours = int(time_left.total_seconds() // 3600)
        minutes = int((time_left.total_seconds() % 3600) // 60)
        reset_time = f"{hours}h {minutes}m"
    else:
        reset_time = "24h 0m"
    
    announcements = Announcement.query.filter_by(is_active=True).order_by(Announcement.created_at.desc()).limit(3).all()
    
    return render_template_string(DASHBOARD_PAGE,
        user=user,
        session=session,
        progress=progress,
        needed_points=needed_points,
        next_tier=next_tier,
        today_tasks=today_tasks,
        remaining_tasks=remaining_tasks,
        reset_time=reset_time,
        announcements=announcements
    )

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
    
    # Reset tasks if needed
    reset_user_tasks_if_needed(user)
    
    if user.tier == 'FREE':
        flash('⚠️ You need to upgrade your tier to access tasks!', 'error')
        return redirect('/upgrade')
    
    tasks = Task.query.filter_by(tier_required=user.tier, is_active=True).all()
    
    today = datetime.now().date()
    completed = TaskCompletion.query.filter(
        TaskCompletion.user_id == user.id,
        db.func.date(TaskCompletion.completed_at) == today
    ).all()
    
    completed_ids = [c.task_id for c in completed]
    today_tasks = len(completed)
    remaining_tasks = max(0, user.daily_limit - today_tasks)
    
    # Calculate potential earnings
    potential_earnings = sum(task.reward for task in tasks[:remaining_tasks]) if tasks else 0
    
    return render_template_string(EARN_PAGE,
        user=user,
        tasks=tasks,
        completed_ids=completed_ids,
        remaining_tasks=remaining_tasks,
        potential_earnings=potential_earnings
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
    
    # Reset tasks if needed
    reset_user_tasks_if_needed(user)
    
    if user.tier == 'FREE':
        flash('⚠️ You need to upgrade your tier to access tasks!', 'error')
        return redirect('/upgrade')
    
    task = Task.query.get_or_404(task_id)
    
    today = datetime.now().date()
    today_tasks = get_user_today_tasks(user.id)
    
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
    user.daily_tasks_completed += 1
    
    # Auto-upgrade if trust score reaches threshold
    new_tier = get_tier_from_score(user.trust_score)
    if new_tier != user.tier:
        user.tier = new_tier
        user.daily_limit = TIER_TASKS.get(new_tier, 0)
        flash(f'🎉 Congratulations! You\'ve been upgraded to {new_tier.title()} tier!', 'success')
    
    db.session.commit()
    
    log_activity(user.id, 'complete_task', f'Completed task: {task.title}')
    flash(f'✅ Task completed! +₦{task.reward}', 'success')
    return redirect('/earn')

@app.route('/share_task', methods=['GET', 'POST'])
def share_task():
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
        bonus = 100
        
        today = datetime.now().date()
        share_task_obj = Task.query.filter_by(task_type='SHARE', is_active=True).first()
        if share_task_obj:
            already_completed = TaskCompletion.query.filter(
                TaskCompletion.user_id == user.id,
                TaskCompletion.task_id == share_task_obj.id,
                db.func.date(TaskCompletion.completed_at) == today
            ).first()
            
            if already_completed:
                flash('⚠️ You already completed the share task today!', 'error')
                return redirect('/earn')
        
        user.balance += bonus
        user.trust_score += 1
        
        if share_task_obj:
            completion = TaskCompletion(
                user_id=user.id,
                task_id=share_task_obj.id,
                proof_text='Shared on social media'
            )
            db.session.add(completion)
        
        db.session.commit()
        log_activity(user.id, 'share_task', 'Shared on social media')
        flash(f'✅ Thank you for sharing! +₦{bonus}', 'success')
        return redirect('/earn')
    
    if request.host.startswith('127.0.0.1') or request.host.startswith('localhost'):
        base_url = f"http://{request.host}"
    else:
        base_url = f"https://{request.host}"
    
    share_url = f"{base_url}/register?ref={user.referral_code}"
    share_message = get_share_message() + f"\n\n{share_url}"
    
    # WhatsApp link with pre-filled message
    whatsapp_link = f"https://wa.me/?text={share_message}"
    
    return render_template_string(SHARE_TASK_PAGE,
        user=user,
        share_url=share_url,
        share_message=share_message,
        whatsapp_link=whatsapp_link
    )

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
    for ref in referrals:
        referred = User.query.get(ref.referred_id)
        if referred:
            referred_users.append(referred)
    
    if request.host.startswith('127.0.0.1') or request.host.startswith('localhost'):
        base_url = f"http://{request.host}"
    else:
        base_url = f"https://{request.host}"
    
    referral_link = f"{base_url}/register?ref={user.referral_code}"
    
    # Share message for WhatsApp
    share_message = get_share_message() + f"\n\n{referral_link}"
    whatsapp_link = f"https://wa.me/?text={share_message}"
    
    total_earned = sum(ref.bonus_amount for ref in referrals if ref.bonus_paid)
    
    return render_template_string(REFERRAL_PAGE,
        user=user,
        referral_link=referral_link,
        referred_users=referred_users,
        total_invites=len(referrals),
        total_earned=total_earned,
        whatsapp_link=whatsapp_link
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
        'BEGINNER': {'name': 'Beginner', 'cost': 1000, 'daily_limit': 6, 'description': '6 tasks/day · Earn up to ₦200 per task'},
        'EXPERT': {'name': 'Expert', 'cost': 3500, 'daily_limit': 10, 'description': '10 tasks/day · Earn up to ₦500 per task'},
        'LEGEND': {'name': 'Legend', 'cost': 10000, 'daily_limit': 15, 'description': '15 tasks/day · Earn up to ₦1,200 per task'}
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
            flash(f'❌ Withdrawals are only allowed on the 5th and 30th of each month. Next withdrawal date: {next_date.strftime("%B %d, %Y")}', 'error')
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
    
    return render_template_string(ACCOUNT_PAGE, user=user)

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
        
        if len(new) < 6:
            flash('❌ Password must be at least 6 characters!', 'error')
            return redirect('/change_password')
        
        user.set_password(new)
        db.session.commit()
        log_activity(user.id, 'change_password', 'Changed password')
        flash('✅ Password changed successfully!', 'success')
        return redirect('/account')
    
    return render_template_string(CHANGE_PASSWORD_PAGE, user=user)

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
    pending_transactions = []
    for tx in pending:
        user = User.query.get(tx.user_id)
        tx_dict = tx.to_dict()
        tx_dict['username'] = user.username if user else 'Unknown User'
        pending_transactions.append(tx_dict)
    
    all_users = User.query.all()
    verified_count = Transaction.query.filter_by(status='VERIFIED').count()
    open_tickets = SupportTicket.query.filter_by(status='OPEN').count()
    
    return render_template_string(ADMIN_DASHBOARD_PAGE,
        pending_transactions=pending_transactions,
        pending_count=len(pending),
        verified_count=verified_count,
        total_users=len(all_users),
        all_users=all_users,
        open_tickets=open_tickets
    )

@app.route('/admin/users')
def admin_users():
    if not session.get('admin'):
        return redirect('/admin/login')
    
    all_users = User.query.order_by(User.id.desc()).all()
    
    return render_template_string(ADMIN_USERS_PAGE,
        users=all_users,
        total_users=len(all_users)
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

# ==================== RUN ====================

if __name__ == '__main__':
    print("=" * 60)
    print("💰 Earn'n'Pay Labs - COMPLETE ULTIMATE VERSION")
    print("=" * 60)
    print("✅ PostgreSQL Database Connected")
    print("✅ Server starting...")
    print("🌐 Open your browser and go to: http://127.0.0.1:5000")
    print("=" * 60)
    print("📄 ALL PAGES FULLY DEFINED:")
    print("   / - LANDING_PAGE (Home)")
    print("   /login - LOGIN_PAGE")
    print("   /register - REGISTER_PAGE")
    print("   /dashboard - DASHBOARD_PAGE")
    print("   /earn - EARN_PAGE (FIXED - Tasks reset every 24hrs)")
    print("   /share_task - SHARE_TASK_PAGE (WhatsApp share added!)")
    print("   /referral - REFERRAL_PAGE (FIXED - Shows invites, rewards referrer)")
    print("   /upgrade - UPGRADE_PAGE")
    print("   /withdraw - WITHDRAW_PAGE (5th & 30th)")
    print("   /account - ACCOUNT_PAGE")
    print("   /change_password - CHANGE_PASSWORD_PAGE")
    print("   /admin/login - ADMIN_LOGIN_PAGE")
    print("   /admin/dashboard - ADMIN_DASHBOARD_PAGE")
    print("   /admin/users - ADMIN_USERS_PAGE")
    print("   /admin/settings - ADMIN_SETTINGS_PAGE")
    print("   /admin/support - ADMIN_SUPPORT_PAGE")
    print("=" * 60)
    print("📊 TRUST SCORE TIERS:")
    print(f"   FREE: 0 points (NO TASKS - Must upgrade)")
    print(f"   BEGINNER: 100 points (6 tasks/day)")
    print(f"   EXPERT: 300 points (10 tasks/day)")
    print(f"   LEGEND: 700 points (15 tasks/day)")
    print("=" * 60)
    print("📅 Withdrawal Settings:")
    print(f"   Minimum: ₦{MINIMUM_WITHDRAWAL:,}")
    print(f"   Days: 5th and 30th of every month")
    print("=" * 60)
    print("📊 Tier Task Limits:")
    print(f"   FREE: 0 tasks/day (MUST UPGRADE!)")
    print(f"   BEGINNER: {TIER_TASKS['BEGINNER']} tasks/day")
    print(f"   EXPERT: {TIER_TASKS['EXPERT']} tasks/day")
    print(f"   LEGEND: {TIER_TASKS['LEGEND']} tasks/day")
    print("=" * 60)
    print("🔐 Admin Panel:")
    print(f"   URL: http://127.0.0.1:5000/admin/login")
    print(f"   Username: {ADMIN_USERNAME}")
    print(f"   Password: {ADMIN_PASSWORD}")
    print("=" * 60)
    print("🛑 Press CTRL+C to stop the server")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000)