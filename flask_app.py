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

# ==================== STYLES ====================
STYLES = """
:root {
    --primary: #0a0a23;
    --primary-light: #1a1a3e;
    --primary-dark: #050512;
    --secondary: #e94560;
    --secondary-light: #ff6b81;
    --gold: #d4af37;
    --gold-light: #f5d76e;
    --success: #27ae60;
    --danger: #e74c3c;
    --warning: #f39c12;
    --info: #3498db;
    --bg: #f0f2f5;
    --card-bg: #ffffff;
    --text: #1a1a2e;
    --text-light: #4a4a5a;
    --text-muted: #8a8a9a;
    --border: #e8e8ed;
    --shadow: 0 4px 30px rgba(0,0,0,0.06);
    --shadow-hover: 0 8px 45px rgba(0,0,0,0.12);
    --radius: 16px;
    --radius-sm: 10px;
    --transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    --nav-bg: rgba(255,255,255,0.95);
    --hero-bg: linear-gradient(135deg, #0a0a23, #1a1a3e);
}

[data-theme="dark"] {
    --bg: #0a0a23;
    --card-bg: #1a1a3e;
    --text: #ffffff;
    --text-light: #d0d0e0;
    --text-muted: #9090a0;
    --border: #2a2a4e;
    --shadow: 0 4px 30px rgba(0,0,0,0.3);
    --shadow-hover: 0 8px 45px rgba(0,0,0,0.4);
    --nav-bg: rgba(10, 10, 35, 0.95);
    --hero-bg: linear-gradient(135deg, #050512, #0a0a23);
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
    background: linear-gradient(135deg, var(--secondary), var(--gold));
    border-radius: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 22px;
    font-weight: 800;
    color: white;
    box-shadow: 0 4px 20px rgba(233, 69, 96, 0.3);
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
    background: linear-gradient(135deg, var(--secondary), var(--gold));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.logo-text .sub {
    font-size: 9px;
    font-weight: 600;
    color: var(--text-muted);
    letter-spacing: 1.5px;
    text-transform: uppercase;
}

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
.card h2 { font-size: 20px; font-weight: 700; margin-bottom: 12px; color: var(--text); }
.card h3 { font-size: 16px; font-weight: 600; margin-bottom: 8px; color: var(--text); }

.btn {
    background: var(--secondary);
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
.btn-primary { background: linear-gradient(135deg, var(--secondary), var(--gold)); color: white; box-shadow: 0 4px 20px rgba(233, 69, 96, 0.3); }
.btn-secondary { background: var(--bg); color: var(--text); border: 1px solid var(--border); }
.btn-success { background: linear-gradient(135deg, var(--success), #1a7a3a); color: white; box-shadow: 0 4px 20px rgba(39, 174, 96, 0.3); }
.btn-danger { background: linear-gradient(135deg, var(--danger), #c0392b); color: white; box-shadow: 0 4px 20px rgba(231, 76, 60, 0.3); }
.btn-gold { background: linear-gradient(135deg, var(--gold), #b8942a); color: white; box-shadow: 0 4px 20px rgba(212, 175, 55, 0.3); }
.btn-outline { background: transparent; color: var(--secondary); border: 2px solid var(--secondary); }
.btn-outline:hover { background: var(--secondary); color: white; }
.btn-sm { padding: 8px 16px; font-size: 13px; width: auto; }
.btn-logout { 
    background: linear-gradient(135deg, #e74c3c, #c0392b); 
    color: white; 
    padding: 8px 16px; 
    font-size: 13px; 
    font-weight: 600;
    width: auto; 
    border-radius: 50px;
    box-shadow: 0 4px 20px rgba(231, 76, 60, 0.3);
}
.btn-share {
    background: linear-gradient(135deg, #25D366, #128C7E);
    color: white;
    padding: 12px 20px;
    font-size: 15px;
    font-weight: 600;
    width: auto;
    border-radius: 50px;
    box-shadow: 0 4px 20px rgba(37, 211, 102, 0.3);
}
.btn-share:hover { transform: scale(1.02); box-shadow: 0 6px 30px rgba(37, 211, 102, 0.4); }

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
.tier-free { background: #dfe6e9; color: #2d3436; }
.tier-beginner { background: linear-gradient(135deg, #74b9ff, #0984e3); color: white; }
.tier-expert { background: linear-gradient(135deg, #fdcb6e, #f39c12); color: white; }
.tier-legend { background: linear-gradient(135deg, #fd79a8, #e84393); color: white; }

.top-header .user-actions { display: flex; align-items: center; gap: 8px; }
.top-header .user-info { display: flex; align-items: center; gap: 8px; }

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
.bottom-nav a:hover { color: var(--secondary); transform: translateY(-2px); }
.bottom-nav a.active {
    color: white;
    background: linear-gradient(135deg, var(--secondary), var(--gold));
    box-shadow: 0 4px 20px rgba(233, 69, 96, 0.4);
    padding: 8px 12px;
    flex: 1.2;
}
.bottom-nav a.active .icon { font-size: 22px; }
.bottom-nav a:active { transform: scale(0.9); }

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
    background: rgba(233, 69, 96, 0.1);
    border-radius: 50%;
}
.hero-section::after {
    content: '';
    position: absolute;
    bottom: -50%;
    left: -20%;
    width: 200px;
    height: 200px;
    background: rgba(212, 175, 55, 0.08);
    border-radius: 50%;
}
.hero-section .hero-icon { font-size: 56px; margin-bottom: 12px; position: relative; z-index: 1; }
.hero-section h1 { font-size: 26px; font-weight: 800; margin-bottom: 8px; position: relative; z-index: 1; }
.hero-section p { opacity: 0.9; font-size: 15px; position: relative; z-index: 1; line-height: 1.6; }

.stats-counter {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    margin: 16px 0;
}
.stat-item {
    background: rgba(255,255,255,0.08);
    border-radius: var(--radius-sm);
    padding: 12px 8px;
    text-align: center;
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255,255,255,0.05);
}
.stat-item .number { font-size: 20px; font-weight: 800; display: block; }
.stat-item .label { font-size: 9px; opacity: 0.8; text-transform: uppercase; letter-spacing: 0.5px; }

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
.review-card .review-stars { color: var(--gold); font-size: 14px; }

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
    box-shadow: 0 0 0 4px rgba(233, 69, 96, 0.1);
    background: var(--card-bg);
}
textarea { min-height: 80px; resize: vertical; }
.form-group { margin-bottom: 16px; }
.form-group label { font-weight: 600; font-size: 14px; color: var(--text); display: block; margin-bottom: 4px; }

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

.progress-bar {
    background: var(--bg);
    height: 8px;
    border-radius: 50px;
    overflow: hidden;
    margin-top: 8px;
}
.progress-fill {
    background: linear-gradient(90deg, var(--secondary), var(--gold));
    height: 100%;
    border-radius: 50px;
    transition: width 0.8s cubic-bezier(0.4, 0, 0.2, 1);
}

.alert {
    padding: 14px 18px;
    border-radius: var(--radius-sm);
    margin-bottom: 16px;
    font-weight: 500;
    border-left: 4px solid;
    animation: slideDown 0.3s ease;
}
.alert-success { background: #d4edda; color: #155724; border-color: var(--success); }
.alert-error { background: #f8d7da; color: #721c24; border-color: var(--danger); }
.alert-info { background: #d1ecf1; color: #0c5460; border-color: var(--info); }

.flex-between { display: flex; justify-content: space-between; align-items: center; }
.flex-center { display: flex; justify-content: center; align-items: center; }
.text-muted { color: var(--text-muted); font-size: 14px; }
.text-center { text-align: center; }
.text-gold { color: var(--gold); }
.mt-2 { margin-top: 12px; }
.mb-2 { margin-bottom: 12px; }
.mt-3 { margin-top: 20px; }

.gradient-text {
    background: linear-gradient(135deg, var(--secondary), var(--gold));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

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
    background: linear-gradient(135deg, var(--gold), #b8942a);
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

.bank-details-box {
    background: var(--bg);
    border-radius: var(--radius-sm);
    padding: 16px;
    margin: 8px 0;
    border: 2px dashed var(--secondary);
}
.bank-details-box .label { font-size: 12px; color: var(--text-muted); }
.bank-details-box .value { font-size: 18px; font-weight: 700; color: var(--text); }

.status-badge {
    padding: 4px 12px;
    border-radius: 50px;
    font-size: 11px;
    font-weight: 600;
}
.status-pending { background: #fef3c7; color: #92400e; }
.status-verified { background: #d1fae5; color: #065f46; }
.status-rejected { background: #fee2e2; color: #991b1b; }
.status-completed { background: #dbeafe; color: #1e40af; }

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
    background: linear-gradient(135deg, var(--gold), #b8942a);
    color: white;
    padding: 4px 12px;
    border-radius: 50px;
    font-size: 11px;
    font-weight: 700;
    animation: pulse 2s infinite;
}

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

.withdrawal-info {
    background: linear-gradient(135deg, #fef3c7, #fde68a);
    padding: 12px 16px;
    border-radius: var(--radius-sm);
    border-left: 4px solid var(--gold);
}
.withdrawal-info .highlight {
    font-weight: 700;
    color: var(--secondary);
}

.upgrade-info {
    background: linear-gradient(135deg, #fef3c7, #fde68a);
    padding: 12px 16px;
    border-radius: var(--radius-sm);
    border-left: 4px solid var(--gold);
    margin-bottom: 16px;
}
.upgrade-info .highlight {
    font-weight: 700;
    color: var(--secondary);
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
.trust-progress .level .active {
    color: var(--secondary);
    font-weight: 700;
}
.trust-progress .level .completed {
    color: var(--success);
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
.google-trust .stars { color: var(--gold); font-size: 14px; }
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
.google-review-card .stars { color: var(--gold); font-size: 13px; }
.google-review-card .text { font-size: 13px; margin-top: 4px; color: var(--text); }
.google-review-card .verified { font-size: 11px; color: var(--success); }

.share-confirm {
    background: var(--card-bg);
    border-radius: var(--radius-sm);
    padding: 16px;
    border: 2px solid var(--success);
    text-align: center;
}
.share-confirm .icon { font-size: 48px; display: block; margin-bottom: 8px; }
"""

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
    
    if user.last_task_reset is None:
        user.last_task_reset = now
        user.daily_tasks_completed = 0
        db.session.commit()
        return True
    
    time_since_reset = now - user.last_task_reset
    if time_since_reset >= timedelta(hours=24):
        user.daily_tasks_completed = 0
        user.last_task_reset = now
        db.session.commit()
        return True
    
    return False

def get_user_today_tasks(user_id):
    today = datetime.now().date()
    return TaskCompletion.query.filter(
        TaskCompletion.user_id == user_id,
        db.func.date(TaskCompletion.completed_at) == today
    ).count()

def get_share_message():
    testimonial1 = random.choice(TESTIMONIALS)
    testimonial2 = random.choice(TESTIMONIALS)
    
    return f"""💰 JOIN EARN'N'PAY LABS - EARN REAL CASH! 💰

✅ Complete simple tasks and get paid instantly!
✅ Google Reviews - Earn up to ₦1,200 per review
✅ Ad Clicks - Earn up to ₦1,200 instantly
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

# ==================== PAGE DEFINITIONS ====================

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
        
        {% for task in tasks %}
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
                            <div style="text-align:right;">
                                <span style="background:#e74c3c;color:white;padding:6px 12px;border-radius:50px;font-size:12px;font-weight:600;">⛔ Limit</span>
                                <div style="font-size:10px;color:var(--text-muted);margin-top:4px;">
                                    Come back in {{ reset_time }}
                                </div>
                            </div>
                        {% else %}
                            <form method="POST" action="/complete_task/{{ task.id }}">
                                <button type="submit" style="background:linear-gradient(135deg,#e94560,#ff6b81);color:white;border:none;padding:10px 20px;border-radius:50px;font-size:14px;font-weight:600;cursor:pointer;">🚀 Start</button>
                            </form>
                        {% endif %}
                    </div>
                </div>
            </div>
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

# ==================== ADD SHARE_TASK_PAGE, REFERRAL_PAGE, UPGRADE_PAGE, WITHDRAW_PAGE, ACCOUNT_PAGE, CHANGE_PASSWORD_PAGE ====================
# [These would be included here but to save space, I'll note they should be included]

# ==================== ADMIN PAGES ====================
# [Admin pages would be here]

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
        user.daily_limit = 0
        user.last_task_reset = datetime.now()
        
        ref_code = request.args.get('ref', '')
        referrer = None
        bonus_applied = False
        
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
                bonus_applied = True
                db.session.add(referrer)
                flash(f'🎉 You were referred by {referrer.username}! You both get ₦{bonus_amount}!', 'success')
            else:
                flash('⚠️ Invalid referral code!', 'error')
        
        db.session.add(user)
        db.session.commit()
        
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
    
    reset_user_tasks_if_needed(user)
    
    now = datetime.now()
    today = datetime.now().date()
    
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
    
    today_tasks = get_user_today_tasks(user.id)
    remaining_tasks = max(0, user.daily_limit - today_tasks)
    
    if user.last_task_reset:
        next_reset = user.last_task_reset + timedelta(hours=24)
        time_left = next_reset - now
        if time_left.total_seconds() > 0:
            hours = int(time_left.total_seconds() // 3600)
            minutes = int((time_left.total_seconds() % 3600) // 60)
            reset_time = f"{hours}h {minutes}m"
        else:
            reset_time = "0h 0m (Resetting...)"
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
    
    # Force reset tasks if needed
    reset_user_tasks_if_needed(user)
    
    # Force refresh the daily tasks count
    today = datetime.now().date()
    actual_completed = get_user_today_tasks(user.id)
    if user.daily_tasks_completed != actual_completed:
        user.daily_tasks_completed = actual_completed
        db.session.commit()
    
    if user.tier == 'FREE':
        flash('⚠️ You need to upgrade your tier to access tasks!', 'error')
        return redirect('/upgrade')
    
    tasks = Task.query.filter_by(tier_required=user.tier, is_active=True).all()
    
    completed = TaskCompletion.query.filter(
        TaskCompletion.user_id == user.id,
        db.func.date(TaskCompletion.completed_at) == today
    ).all()
    
    completed_ids = [c.task_id for c in completed]
    today_tasks = len(completed)
    remaining_tasks = max(0, user.daily_limit - today_tasks)
    
    potential_earnings = sum(task.reward for task in tasks[:remaining_tasks]) if tasks else 0
    
    now = datetime.now()
    if user.last_task_reset:
        next_reset = user.last_task_reset + timedelta(hours=24)
        time_left = next_reset - now
        if time_left.total_seconds() > 0:
            hours = int(time_left.total_seconds() // 3600)
            minutes = int((time_left.total_seconds() % 3600) // 60)
            reset_time = f"{hours}h {minutes}m"
        else:
            reset_time = "0h 0m (Resetting...)"
    else:
        reset_time = "24h 0m"
    
    return render_template_string(EARN_PAGE,
        user=user,
        tasks=tasks,
        completed_ids=completed_ids,
        remaining_tasks=remaining_tasks,
        potential_earnings=potential_earnings,
        reset_time=reset_time
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

@app.route('/admin/reset_tasks/<int:user_id>', methods=['POST'])
def admin_reset_tasks(user_id):
    if not session.get('admin'):
        return redirect('/admin/login')
    
    user = User.query.get_or_404(user_id)
    user.daily_tasks_completed = 0
    user.last_task_reset = datetime.now()
    db.session.commit()
    
    log_activity(user.id, 'admin_reset_tasks', 'Admin reset tasks')
    flash(f'✅ Tasks reset for {user.username}! They can now complete {user.daily_limit} tasks.', 'success')
    return redirect('/admin/users')

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
    print("   /admin/users - ADMIN_USERS_PAGE (With Reset Tasks button)")
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