from flask import Flask, request, redirect, url_for, render_template_string, session
from functools import wraps
import sqlite3
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

app = Flask(__name__)

# ================= SECURITY CONFIG =================
app.secret_key = 'kartik_super_secret_key_123'
ADMIN_USERNAME = "kartik"
ADMIN_PASSWORD = "mathur"

# ================= EMAIL CONFIG =================
EMAIL_SENDER   = "2007mathurkartik@gmail.com"
EMAIL_PASSWORD = "vurwfyabfxxppldn"

# ================= UPI CONFIG =================
UPI_ID   = "7302241715@axl"
UPI_NAME = "Helping Hands NGO"

# ================= DATABASE =================
def init_db():
    conn = sqlite3.connect("ngo.db")
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS donation(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, amount TEXT, purpose TEXT, email TEXT, dob TEXT, txn_id TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS volunteer(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, email TEXT, phone TEXT, dob TEXT)""")
    for col in ["email", "dob", "txn_id"]:
        try:
            c.execute(f"ALTER TABLE donation ADD COLUMN {col} TEXT")
        except Exception:
            pass
    try:
        c.execute("ALTER TABLE volunteer ADD COLUMN dob TEXT")
    except Exception:
        pass
    conn.commit()
    conn.close()

init_db()

# ================= UPI QR LINK GENERATOR =================
def make_upi_link(purpose, amount=None):
    import urllib.parse
    params = {
        "pa": UPI_ID,
        "pn": UPI_NAME,
        "tn": f"Donation for {purpose} - Helping Hands NGO",
        "cu": "INR",
    }
    if amount:
        params["am"] = str(amount)
    return "upi://pay?" + urllib.parse.urlencode(params)

def make_upi_qr_image(purpose):
    try:
        import qrcode
        import io, base64
        upi_link = make_upi_link(purpose)
        qr = qrcode.QRCode(version=1,
                           error_correction=qrcode.constants.ERROR_CORRECT_H,
                           box_size=8, border=2)
        qr.add_data(upi_link)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#1a3c2e", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return "data:image/png;base64," + base64.b64encode(buf.read()).decode()
    except ImportError:
        return "/static/QR.jpg"

QR_CACHE = {}
def preload_qr():
    for cat in ["Education", "Food Support", "Healthcare", "Women Empowerment"]:
        QR_CACHE[cat] = make_upi_qr_image(cat)

preload_qr()

# ================= EMAIL FUNCTION =================
def send_email(to_email, subject, html_body):
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"Helping Hands NGO <{EMAIL_SENDER}>"
        msg["To"]      = to_email
        msg.attach(MIMEText(html_body, "html", "utf-8"))
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.ehlo(); server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, to_email, msg.as_string())
        print(f"[Email Sent] -> {to_email}")
        return True, "Email bhej diya gaya!"
    except smtplib.SMTPAuthenticationError:
        return False, "Gmail Auth fail - App Password galat hai."
    except Exception as e:
        print(f"[Email Error] {e}")
        return False, str(e)

# ================= EMAIL TEMPLATES =================
def donation_thankyou_html(name, purpose, amount):
    return f"""
    <div style="font-family:'Segoe UI',sans-serif;max-width:560px;margin:0 auto;border-radius:16px;overflow:hidden;border:1px solid #e8ddd0;">
      <div style="background:linear-gradient(135deg,#1a3c2e,#2d6a4f);padding:40px 32px;text-align:center;">
        <div style="font-size:52px;margin-bottom:12px;">&#129330;</div>
        <h1 style="color:white;font-size:26px;margin:0 0 8px;">Shukriya, {name}!</h1>
        <p style="color:rgba(255,255,255,0.7);font-size:15px;margin:0;">Aapki donation register ho gayi hai &#10084;&#65039;</p>
      </div>
      <div style="background:#fffaf4;padding:32px;">
        <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:12px;padding:20px;margin-bottom:24px;">
          <p style="color:#166534;font-size:15px;margin:0;line-height:1.7;">
            &#9989; <strong>Donation:</strong> Rs.{amount} for {purpose}<br>
            &#9989; <strong>Record ho gayi hai</strong> - Helping Hands NGO Dashboard mein.<br>
            &#127874; <strong>Birthday par</strong> hum aapko ek khaas email bhejengi!
          </p>
        </div>
        <div style="text-align:center;margin-bottom:24px;">
          <a href="http://10.103.35.221:5000/donate"
             style="background:linear-gradient(135deg,#e8751a,#c45e0e);color:white;text-decoration:none;
                    padding:14px 32px;border-radius:50px;font-size:16px;font-weight:700;
                    display:inline-block;box-shadow:0 6px 18px rgba(232,117,26,0.4);">
            &#10084;&#65039; Phir Se Donate Karein
          </a>
          <p style="color:#9ca3af;font-size:12px;margin-top:10px;">
            Har choti madad se ek zindagi badal sakti hai &#127807;
          </p>
        </div>
        <p style="color:#6b7280;font-size:13px;text-align:center;margin:0;border-top:1px solid #e8ddd0;padding-top:20px;">-- Helping Hands NGO Team &#128154;</p>
      </div>
    </div>"""

def birthday_email_html(name):
    return f"""
    <div style="font-family:'Segoe UI',sans-serif;max-width:560px;margin:0 auto;border-radius:16px;overflow:hidden;border:1px solid #e8ddd0;">
      <div style="background:linear-gradient(135deg,#1a3c2e,#2d6a4f);padding:40px 32px;text-align:center;">
        <div style="font-size:56px;margin-bottom:12px;">&#127874;</div>
        <h1 style="color:white;font-size:28px;margin:0 0 8px;">Happy Birthday, {name}!</h1>
        <p style="color:rgba(255,255,255,0.7);font-size:15px;margin:0;">Helping Hands NGO ki taraf se dil se badhaai &#129330;</p>
      </div>
      <div style="background:#fffaf4;padding:32px;">
        <p style="color:#2d2d2d;font-size:16px;line-height:1.7;margin:0 0 20px;">
          Aapka yeh khaas din aur bhi khaas ban sakta hai --
          <strong>NGO ke bachhon ke saath celebrate karein!</strong>
        </p>
        <div style="text-align:center;margin:0 0 24px;">
          <a href="http://10.103.35.221:5000/donate"
             style="background:linear-gradient(135deg,#e8751a,#c45e0e);color:white;text-decoration:none;
                    padding:14px 32px;border-radius:50px;font-size:16px;font-weight:600;display:inline-block;">
            &#10084;&#65039; Donate Karein - Bachhon Ko Khushi Dein
          </a>
        </div>
        <p style="color:#6b7280;font-size:13px;text-align:center;margin:0;border-top:1px solid #e8ddd0;padding-top:20px;">-- Helping Hands NGO Team &#128154;</p>
      </div>
    </div>"""

def welcome_email_html(name):
    return f"""
    <div style="font-family:'Segoe UI',sans-serif;max-width:560px;margin:0 auto;border-radius:16px;overflow:hidden;border:1px solid #e8ddd0;">
      <div style="background:linear-gradient(135deg,#1a3c2e,#2d6a4f);padding:40px 32px;text-align:center;">
        <div style="font-size:52px;margin-bottom:12px;">&#129309;</div>
        <h1 style="color:white;font-size:26px;margin:0 0 8px;">Welcome to the Family, {name}!</h1>
        <p style="color:rgba(255,255,255,0.7);font-size:15px;margin:0;">Helping Hands NGO mein aapka swagat hai</p>
      </div>
      <div style="background:#fffaf4;padding:32px;">
        <p style="color:#2d2d2d;font-size:16px;line-height:1.7;margin:0 0 20px;">Aapne ek bahut hi sarahniya kadam uthaya hai. &#128170;</p>
        <p style="color:#6b7280;font-size:13px;text-align:center;margin:0;border-top:1px solid #e8ddd0;padding-top:20px;">-- Helping Hands NGO Team &#128154; | 2007mathurkartik@gmail.com</p>
      </div>
    </div>"""

# ================= AUTO BIRTHDAY CHECK =================
def check_birthdays():
    today = datetime.now().strftime("%m-%d")
    conn  = sqlite3.connect("ngo.db")
    c     = conn.cursor()
    c.execute("SELECT name,email,dob FROM volunteer WHERE dob!='' AND email!=''")
    c2 = conn.cursor()
    c2.execute("SELECT name,email,dob FROM donation WHERE dob IS NOT NULL AND dob!='' AND email IS NOT NULL AND email!=''")
    rows = c.fetchall() + c2.fetchall()
    conn.close()
    for name, email, dob in rows:
        if dob and len(dob) >= 10 and dob[5:] == today:
            send_email(email, f"Happy Birthday {name}! - Helping Hands NGO", birthday_email_html(name))

scheduler = BackgroundScheduler()
scheduler.add_job(check_birthdays, 'cron', hour=8, minute=0)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ================= BASE HTML =================
base_html = """<!DOCTYPE html>
<html lang="hi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<title>Helping Hands NGO</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700;900&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
<style>
:root{
  --cream:#fdf6ec;--warm-white:#fffaf4;--saffron:#e8751a;--saffron-light:#f59b4b;
  --saffron-dark:#c45e0e;--deep-green:#1a3c2e;--mid-green:#2d6a4f;--light-green:#52b788;
  --gold:#d4a017;--dark:#1c1c1c;--text:#2d2d2d;--muted:#6b7280;--border:#e8ddd0;
  --shadow:0 20px 60px rgba(0,0,0,0.08);--shadow-sm:0 4px 20px rgba(0,0,0,0.06);
  --radius:20px;--radius-sm:12px;
}
*{box-sizing:border-box;margin:0;padding:0;}
html{scroll-behavior:smooth;}
body{font-family:'DM Sans',sans-serif;background:var(--cream);color:var(--text);overflow-x:hidden;width:100%;}
::-webkit-scrollbar{width:6px;}::-webkit-scrollbar-track{background:var(--cream);}::-webkit-scrollbar-thumb{background:var(--saffron);border-radius:10px;}
.site-header{position:relative;background:var(--deep-green);overflow:hidden;padding:0;}
.header-pattern{position:absolute;inset:0;background-image:radial-gradient(circle at 20% 50%,rgba(232,117,26,0.15) 0%,transparent 50%),radial-gradient(circle at 80% 20%,rgba(82,183,136,0.12) 0%,transparent 50%);}
.header-inner{position:relative;z-index:2;display:flex;align-items:center;justify-content:space-between;padding:18px 20px;gap:12px;}
.logo-area{display:flex;align-items:center;gap:12px;min-width:0;}
.logo-icon{width:46px;height:46px;min-width:46px;background:linear-gradient(135deg,var(--saffron),var(--gold));border-radius:14px;display:flex;align-items:center;justify-content:center;font-size:22px;box-shadow:0 6px 16px rgba(232,117,26,0.4);}
.logo-text h1{font-family:'Playfair Display',serif;font-size:17px;font-weight:700;color:white;line-height:1.2;}
.logo-text span{font-size:10px;color:var(--light-green);font-weight:500;letter-spacing:1.5px;text-transform:uppercase;}
.header-tagline{font-family:'Playfair Display',serif;font-size:11px;color:rgba(255,255,255,0.5);font-style:italic;text-align:right;flex-shrink:0;display:none;}
.hero{position:relative;background:var(--deep-green);padding:50px 20px 70px;text-align:center;overflow:hidden;}
.hero::before{content:'';position:absolute;bottom:-1px;left:0;right:0;height:60px;background:var(--cream);clip-path:ellipse(55% 100% at 50% 100%);}
.hero-badge{display:inline-flex;align-items:center;gap:8px;background:rgba(232,117,26,0.15);border:1px solid rgba(232,117,26,0.3);color:var(--saffron-light);padding:6px 16px;border-radius:50px;font-size:11px;font-weight:600;letter-spacing:1px;text-transform:uppercase;margin-bottom:20px;}
.hero h2{font-family:'Playfair Display',serif;font-size:clamp(28px,7vw,56px);font-weight:900;color:white;line-height:1.15;margin-bottom:14px;}
.hero h2 em{font-style:normal;color:var(--saffron-light);}
.hero p{color:rgba(255,255,255,0.65);font-size:15px;max-width:480px;margin:0 auto 32px;line-height:1.7;}
.hero-images{display:flex;justify-content:center;gap:12px;margin-top:36px;padding-bottom:30px;flex-wrap:wrap;}
.hero-img-wrap{width:clamp(100px,28vw,200px);height:clamp(75px,20vw,145px);border-radius:14px;overflow:hidden;border:2px solid rgba(255,255,255,0.12);box-shadow:0 12px 30px rgba(0,0,0,0.3);transition:transform 0.3s ease;}
.hero-img-wrap img{width:100%;height:100%;object-fit:cover;}
nav{background:white;border-bottom:1px solid var(--border);padding:0 16px;display:flex;align-items:center;flex-wrap:wrap;gap:2px;position:sticky;top:0;z-index:100;box-shadow:0 2px 20px rgba(0,0,0,0.06);}
nav a{color:var(--muted);text-decoration:none;font-weight:500;font-size:13px;padding:16px 12px;border-bottom:3px solid transparent;transition:all 0.25s;display:flex;align-items:center;gap:6px;white-space:nowrap;}
nav a:hover{color:var(--saffron);border-bottom-color:var(--saffron);}
.nav-spacer{flex:1;min-width:8px;}
.nav-admin-btn{background:var(--saffron)!important;color:white!important;padding:8px 16px!important;border-radius:50px!important;border-bottom:none!important;margin:4px 2px;font-weight:600!important;font-size:12px!important;}
.nav-admin-btn:hover{background:var(--saffron-dark)!important;border-bottom:none!important;}
.nav-logout{background:transparent!important;color:#ef4444!important;border:1px solid #fecaca!important;padding:7px 14px!important;border-bottom:none!important;border-radius:50px!important;font-size:12px!important;}
.nav-logout:hover{background:#fef2f2!important;border-bottom:none!important;}
.container{max-width:1200px;margin:0 auto;padding:30px 16px;}
.section{background:white;border-radius:var(--radius);padding:28px 20px;margin-bottom:28px;box-shadow:var(--shadow-sm);border:1px solid var(--border);animation:fadeUp 0.5s ease both;}
@keyframes fadeUp{from{opacity:0;transform:translateY(20px);}to{opacity:1;transform:translateY(0);}}
.section-header{display:flex;align-items:flex-start;gap:14px;margin-bottom:28px;padding-bottom:22px;border-bottom:1px solid var(--border);}
.section-icon{width:46px;height:46px;min-width:46px;background:linear-gradient(135deg,var(--saffron),var(--saffron-light));border-radius:13px;display:flex;align-items:center;justify-content:center;font-size:20px;box-shadow:0 5px 14px rgba(232,117,26,0.3);}
.section-title h2{font-family:'Playfair Display',serif;font-size:22px;font-weight:700;color:var(--deep-green);line-height:1.3;}
.section-title p{color:var(--muted);font-size:13px;margin-top:3px;}
.cards-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px;}
.card{background:var(--warm-white);border:1px solid var(--border);border-radius:var(--radius-sm);padding:22px 18px;transition:all 0.3s ease;position:relative;overflow:hidden;}
.card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,var(--saffron),var(--light-green));transform:scaleX(0);transition:transform 0.3s ease;}
.card:hover{transform:translateY(-5px);box-shadow:0 16px 36px rgba(0,0,0,0.1);border-color:transparent;}
.card:hover::before{transform:scaleX(1);}
.card-emoji{font-size:30px;margin-bottom:12px;display:block;}
.card h3{font-family:'Playfair Display',serif;font-size:16px;color:var(--deep-green);margin-bottom:6px;}
.card p{color:var(--muted);font-size:13px;line-height:1.6;}
.stats-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:14px;margin-top:8px;}
.stat-card{background:linear-gradient(135deg,var(--deep-green),var(--mid-green));border-radius:var(--radius-sm);padding:24px 18px;text-align:center;color:white;position:relative;overflow:hidden;}
.stat-num{font-family:'Playfair Display',serif;font-size:26px;font-weight:700;color:var(--saffron-light);}
.stat-label{font-size:12px;color:rgba(255,255,255,0.7);margin-top:5px;font-weight:500;}
.form-group{margin-bottom:18px;}
.form-group label{display:block;font-size:13px;font-weight:600;color:var(--deep-green);margin-bottom:7px;}
.form-control{width:100%;padding:13px 16px;border:1.5px solid var(--border);border-radius:12px;font-size:15px;font-family:'DM Sans',sans-serif;color:var(--text);background:var(--warm-white);transition:all 0.25s;outline:none;-webkit-appearance:none;}
.form-control:focus{border-color:var(--saffron);background:white;box-shadow:0 0 0 3px rgba(232,117,26,0.1);}
.form-control::placeholder{color:#aaa;}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;padding:14px 28px;border-radius:50px;font-size:15px;font-weight:600;font-family:'DM Sans',sans-serif;cursor:pointer;transition:all 0.25s;border:none;text-decoration:none;}
.btn-primary{background:linear-gradient(135deg,var(--saffron),var(--saffron-dark));color:white;box-shadow:0 6px 18px rgba(232,117,26,0.35);width:100%;}
.btn-primary:hover{transform:translateY(-2px);box-shadow:0 10px 24px rgba(232,117,26,0.45);}
.btn-green{background:linear-gradient(135deg,var(--mid-green),var(--deep-green));color:white;box-shadow:0 6px 18px rgba(45,106,79,0.35);width:100%;}
.btn-green:hover{transform:translateY(-2px);box-shadow:0 10px 24px rgba(45,106,79,0.45);}
.btn-upi{background:linear-gradient(135deg,#7c3aed,#4f46e5);color:white;box-shadow:0 6px 18px rgba(124,58,237,0.35);padding:15px 28px;border-radius:50px;font-size:15px;font-weight:700;display:inline-flex;align-items:center;gap:10px;text-decoration:none;transition:all 0.25s;border:none;cursor:pointer;width:100%;justify-content:center;}
.btn-upi:hover{transform:translateY(-2px);box-shadow:0 10px 24px rgba(124,58,237,0.45);}
.btn-edit{background:#fff8ed;color:var(--saffron-dark);border:1px solid #fcd9aa;padding:6px 12px;border-radius:8px;font-size:12px;text-decoration:none;font-weight:600;transition:all 0.2s;display:inline-flex;align-items:center;gap:4px;}
.btn-edit:hover{background:var(--saffron);color:white;border-color:var(--saffron);}
.btn-delete{background:#fef2f2;color:#dc2626;border:1px solid #fecaca;padding:6px 12px;border-radius:8px;font-size:12px;text-decoration:none;font-weight:600;transition:all 0.2s;display:inline-flex;align-items:center;gap:4px;}
.btn-delete:hover{background:#dc2626;color:white;border-color:#dc2626;}
.btn-secondary{background:#f4f4f5;color:#52525b;font-weight:600;padding:12px 24px;border-radius:50px;border:none;cursor:pointer;font-family:'DM Sans',sans-serif;font-size:14px;transition:all 0.2s;display:inline-flex;align-items:center;gap:8px;text-decoration:none;margin-top:10px;}
.btn-secondary:hover{background:#e4e4e7;}
.btn-email{background:linear-gradient(135deg,#0ea5e9,#0369a1);color:white;border:none;padding:6px 12px;border-radius:8px;font-size:12px;font-weight:600;display:inline-flex;align-items:center;gap:4px;cursor:pointer;text-decoration:none;transition:all 0.2s;}
.btn-email:hover{transform:translateY(-1px);opacity:0.9;}
.table-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch;border-radius:var(--radius-sm);border:1px solid var(--border);margin-top:16px;}
table{width:100%;border-collapse:collapse;min-width:600px;}
thead tr{background:linear-gradient(90deg,var(--deep-green),var(--mid-green));}
th{padding:13px 14px;text-align:left;color:white;font-size:12px;font-weight:600;letter-spacing:0.3px;text-transform:uppercase;white-space:nowrap;}
td{padding:12px 14px;font-size:13px;border-bottom:1px solid var(--border);color:var(--text);}
tbody tr:last-child td{border-bottom:none;}
tbody tr:hover{background:var(--warm-white);}
.dash-stat{background:white;border:1px solid var(--border);border-radius:var(--radius-sm);padding:22px 18px;position:relative;overflow:hidden;transition:box-shadow 0.3s;}
.dash-stat:hover{box-shadow:0 10px 26px rgba(0,0,0,0.08);}
.dash-stat-icon{width:40px;height:40px;border-radius:11px;display:flex;align-items:center;justify-content:center;font-size:18px;margin-bottom:14px;}
.dash-stat-value{font-family:'Playfair Display',serif;font-size:30px;font-weight:700;color:var(--deep-green);}
.dash-stat-label{font-size:12px;color:var(--muted);font-weight:500;margin-top:3px;}
.dash-stat-bar{position:absolute;bottom:0;left:0;height:4px;width:100%;}
.cause-card{background:white;border:2px solid var(--border);border-radius:var(--radius-sm);padding:22px 16px;cursor:pointer;transition:all 0.3s ease;text-align:center;position:relative;overflow:hidden;}
.cause-card:hover{border-color:var(--saffron);transform:translateY(-4px);box-shadow:0 14px 34px rgba(232,117,26,0.18);}
.cause-card.active-cause{border-color:var(--saffron);background:#fff8f0;}
.cause-emoji{font-size:34px;margin-bottom:10px;display:block;}
.cause-card h3{font-family:'Playfair Display',serif;font-size:15px;color:var(--deep-green);margin-bottom:5px;}
.cause-card p{font-size:12px;color:var(--muted);}
.upi-section{display:none;background:linear-gradient(135deg,#1a3c2e,#2d6a4f);border-radius:var(--radius);padding:30px 20px;text-align:center;margin:24px 0;animation:fadeUp 0.4s ease;}
.upi-title{font-family:'Playfair Display',serif;font-size:19px;color:white;margin-bottom:5px;}
.upi-subtitle{color:rgba(255,255,255,0.6);font-size:12px;margin-bottom:22px;}
.qr-wrap{background:white;width:190px;height:190px;border-radius:14px;margin:0 auto 18px;padding:10px;box-shadow:0 16px 36px rgba(0,0,0,0.3);display:flex;align-items:center;justify-content:center;}
.qr-wrap img{width:100%;height:100%;object-fit:contain;}
.upi-or{color:rgba(255,255,255,0.5);font-size:12px;margin:14px 0;}
.upi-steps{display:flex;justify-content:center;gap:16px;margin-top:18px;flex-wrap:wrap;}
.upi-step{display:flex;flex-direction:column;align-items:center;gap:5px;}
.step-num{width:26px;height:26px;background:var(--saffron);color:white;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:12px;}
.step-txt{color:rgba(255,255,255,0.7);font-size:10px;text-align:center;max-width:65px;}
.payment-done-section{display:none;margin-top:24px;animation:fadeUp 0.4s ease;}
.badge{display:inline-flex;align-items:center;gap:4px;padding:3px 10px;border-radius:50px;font-size:11px;font-weight:600;}
.badge-green{background:#dcfce7;color:#16a34a;}
.badge-orange{background:#fff7ed;color:var(--saffron-dark);}
.badge-birthday{background:linear-gradient(135deg,#fef3c7,#fde68a);color:#92400e;}
.bday-banner{background:linear-gradient(135deg,#fefce8,#fff8f0);border:2px solid #fcd34d;border-radius:14px;padding:16px 18px;display:flex;align-items:center;gap:14px;margin-bottom:24px;flex-wrap:wrap;}
.bday-banner .ico{font-size:28px;}
.alert{border-radius:12px;padding:14px 18px;margin-bottom:20px;display:flex;align-items:center;gap:10px;font-size:14px;font-weight:500;}
.alert-error{background:#fef2f2;border:1px solid #fecaca;color:#dc2626;}
.alert-success{background:#f0fdf4;border:1px solid #bbf7d0;color:#16a34a;}
footer{background:var(--dark);color:white;text-align:center;padding:0;margin-top:0;}
.footer-top{background:var(--deep-green);padding:40px 20px;display:grid;grid-template-columns:1fr;gap:28px;text-align:left;}
.footer-brand h3{font-family:'Playfair Display',serif;font-size:20px;color:white;margin-bottom:10px;}
.footer-brand p{color:rgba(255,255,255,0.55);font-size:14px;line-height:1.7;}
.footer-col h4{font-size:12px;color:var(--saffron-light);letter-spacing:1.5px;text-transform:uppercase;font-weight:600;margin-bottom:12px;}
.footer-col a{display:block;color:rgba(255,255,255,0.55);text-decoration:none;font-size:13px;margin-bottom:8px;transition:color 0.2s;}
.footer-col a:hover{color:var(--saffron-light);}
.footer-bottom{background:var(--dark);padding:16px 20px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;}
.footer-bottom p{color:rgba(255,255,255,0.4);font-size:12px;}
@media(min-width:640px){
  .header-inner{padding:22px 40px;}
  .header-tagline{display:block;}
  .hero{padding:70px 40px 90px;}
  .container{padding:50px 30px;}
  .section{padding:40px 36px;}
  .cards-grid{grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:18px;}
  .stats-grid{grid-template-columns:repeat(4,1fr);}
  .footer-top{grid-template-columns:2fr 1fr 1fr;padding:50px 40px;}
  .footer-bottom{padding:20px 40px;}
}
@media(min-width:1024px){
  .header-inner{padding:28px 60px;}
  .container{padding:60px 30px;}
  .section{padding:48px;}
  .footer-top{padding:50px 60px;}
  .footer-bottom{padding:20px 60px;}
}
</style>
</head>
<body>
<div class="site-header">
  <div class="header-pattern"></div>
  <div class="header-inner">
    <div class="logo-area">
      <div class="logo-icon">&#129330;</div>
      <div class="logo-text"><h1>Helping Hands NGO</h1><span>Serving Since 2026</span></div>
    </div>
    <div class="header-tagline">"Manav Seva Hi Madhav Seva"<br><span style="font-size:11px;opacity:0.5;">Serving Humanity &#10084;&#65039;</span></div>
  </div>
</div>
<div class="hero">
  <div class="hero-badge"><i class="fas fa-heart" style="color:var(--saffron-light)"></i> Making a Difference Every Day</div>
  <h2>Together We Can Change <em>Many Lives</em></h2>
  <p>Join hands with us to bring hope, education, food, and health to those who need it most.</p>
  <div class="hero-images">
    <div class="hero-img-wrap"><img src="/static/Poor_Child.jpg" alt="Child" onerror="this.parentElement.style.background='rgba(255,255,255,0.05)'"></div>
    <div class="hero-img-wrap" style="transform:translateY(16px);"><img src="/static/Food_Support.jpg" alt="Food" onerror="this.parentElement.style.background='rgba(255,255,255,0.05)'"></div>
    <div class="hero-img-wrap"><img src="/static/COVID.gif" alt="Health" onerror="this.parentElement.style.background='rgba(255,255,255,0.05)'"></div>
  </div>
</div>
<nav>
  <a href="/"><i class="fas fa-home"></i> Home</a>
  <a href="/donate"><i class="fas fa-hand-holding-heart"></i> Donate</a>
  <a href="/volunteer"><i class="fas fa-users"></i> Volunteer</a>
  <div class="nav-spacer"></div>
  {% if session.get('admin_logged_in') %}
    <a href="/admin" class="nav-admin-btn"><i class="fas fa-shield-alt"></i> Admin</a>
    <a href="/logout" class="nav-logout"><i class="fas fa-sign-out-alt"></i> Logout</a>
  {% else %}
    <a href="/login"><i class="fas fa-lock"></i> Login</a>
  {% endif %}
</nav>
<div class="container">{{content|safe}}</div>
<footer>
  <div class="footer-top">
    <div class="footer-brand">
      <h3>&#129330; Helping Hands NGO</h3>
      <p>We work tirelessly for education, healthcare, food support, and women empowerment across underserved communities.</p>
      <div style="margin-top:16px;display:flex;gap:10px;flex-wrap:wrap;">
        <span class="badge badge-green"><i class="fas fa-certificate"></i> NGO Registered</span>
        <span class="badge badge-orange"><i class="fas fa-shield-alt"></i> Transparent Process</span>
      </div>
    </div>
    <div class="footer-col">
      <h4>Quick Links</h4>
      <a href="/"><i class="fas fa-angle-right"></i> Home</a>
      <a href="/donate"><i class="fas fa-angle-right"></i> Donate Now</a>
      <a href="/volunteer"><i class="fas fa-angle-right"></i> Volunteer</a>
    </div>
    <div class="footer-col">
      <h4>Contact</h4>
      <a href="#"><i class="fas fa-map-marker-alt"></i> Rampur, UP, India</a>
      <a href="#"><i class="fas fa-envelope"></i> 2007mathurkartik@gmail.com</a>
      <a href="#"><i class="fas fa-phone"></i> +91 73022 41715</a>
    </div>
  </div>
  <div class="footer-bottom">
    <p>&#169; 2026 Helping Hands NGO. All Rights Reserved.</p>
    <p>Made with &#10084;&#65039; by <strong style="color:var(--saffron-light)">Kartik Mathur</strong></p>
  </div>
</footer>
</body>
</html>
"""

# ================= HOME =================
@app.route("/")
def home():
    content = """
    <div class="section">
      <div class="section-header">
        <div class="section-icon">&#127775;</div>
        <div class="section-title"><h2>Welcome to Helping Hands NGO</h2><p>Our mission is to uplift lives through compassion and action</p></div>
      </div>
      <div class="cards-grid">
        <div class="card"><span class="card-emoji">&#127891;</span><h3>Education</h3><p>Free education and skill development for underprivileged children and youth.</p></div>
        <div class="card"><span class="card-emoji">&#127869;&#65039;</span><h3>Food Support</h3><p>Daily nutritious meals for poor, elderly, and homeless members of society.</p></div>
        <div class="card"><span class="card-emoji">&#127973;</span><h3>Healthcare</h3><p>Free health camps, check-ups, and medicine distribution in rural areas.</p></div>
        <div class="card"><span class="card-emoji">&#128105;</span><h3>Women Empowerment</h3><p>Training, employment support, and self-reliance programs for women.</p></div>
      </div>
    </div>
    <div class="section">
      <div class="section-header">
        <div class="section-icon">&#128202;</div>
        <div class="section-title"><h2>Our Impact So Far</h2><p>Numbers that represent real lives changed</p></div>
      </div>
      <div class="stats-grid">
        <div class="stat-card"><div class="stat-num">10,000+</div><div class="stat-label">&#127758; Lives Impacted</div></div>
        <div class="stat-card"><div class="stat-num">120+</div><div class="stat-label">&#127891; Education Camps</div></div>
        <div class="stat-card"><div class="stat-num">50,000+</div><div class="stat-label">&#127869;&#65039; Meals Served</div></div>
        <div class="stat-card"><div class="stat-num">500+</div><div class="stat-label">&#129309; Active Volunteers</div></div>
      </div>
    </div>
    <div class="section" style="background:linear-gradient(135deg,#1a3c2e,#2d6a4f);border:none;">
      <div style="text-align:center;padding:10px 0;">
        <div style="font-size:32px;margin-bottom:10px;">&#10084;&#65039;</div>
        <h2 style="font-family:'Playfair Display',serif;color:white;font-size:24px;margin-bottom:10px;">Ready to Make a Difference?</h2>
        <p style="color:rgba(255,255,255,0.65);margin-bottom:28px;font-size:15px;">Your small contribution can change someone's entire life.</p>
        <div style="display:flex;justify-content:center;gap:14px;flex-wrap:wrap;">
          <a href="/donate" style="background:linear-gradient(135deg,#e8751a,#c45e0e);color:white;padding:14px 28px;border-radius:50px;text-decoration:none;font-weight:600;font-size:15px;display:inline-flex;align-items:center;gap:8px;"><i class="fas fa-hand-holding-heart"></i> Donate Now</a>
          <a href="/volunteer" style="background:white;color:#1a3c2e;font-weight:700;padding:14px 28px;border-radius:50px;text-decoration:none;display:inline-flex;align-items:center;gap:8px;font-size:15px;"><i class="fas fa-users"></i> Volunteer</a>
        </div>
      </div>
    </div>"""
    return render_template_string(base_html, content=content)

# ================= DONATE =================
@app.route("/donate", methods=["GET","POST"])
def donate():
    if request.method == "POST":
        name    = request.form['name']
        amount  = request.form['amount']
        purpose = request.form['purpose']
        email   = request.form.get('email', '')
        dob     = request.form.get('dob', '')
        txn_id  = request.form.get('txn_id', '')
        conn = sqlite3.connect("ngo.db")
        c = conn.cursor()
        c.execute("INSERT INTO donation(name,amount,purpose,email,dob,txn_id) VALUES (?,?,?,?,?,?)",
                  (name, amount, purpose, email, dob, txn_id))
        conn.commit()
        conn.close()
        if email:
            send_email(email,
                       "Shukriya! Aapka Donation Register Ho Gaya - Helping Hands NGO",
                       donation_thankyou_html(name, purpose, amount))
        return redirect(url_for("donate"))

    paid     = request.args.get('paid', '')
    category = request.args.get('cat', '')

    qr_edu    = QR_CACHE.get("Education", "/static/QR.jpg")
    qr_food   = QR_CACHE.get("Food Support", "/static/QR.jpg")
    qr_health = QR_CACHE.get("Healthcare", "/static/QR.jpg")
    qr_women  = QR_CACHE.get("Women Empowerment", "/static/QR.jpg")

    import urllib.parse
    def upi_btn(cat):
        p = {"pa": UPI_ID, "pn": UPI_NAME,
             "tn": f"Donation for {cat} - Helping Hands NGO", "cu": "INR"}
        return "upi://pay?" + urllib.parse.urlencode(p)

    upi_edu    = upi_btn("Education")
    upi_food   = upi_btn("Food Support")
    upi_health = upi_btn("Healthcare")
    upi_women  = upi_btn("Women Empowerment")

    show_form  = "true" if paid == "1" else "false"
    preset_cat = category if category else ""

    content = f"""
    <div class="section">
      <div class="section-header">
        <div class="section-icon">&#128157;</div>
        <div class="section-title"><h2>Donate to a Cause</h2><p>Cause chunein &rarr; QR scan karein &rarr; form fill karein</p></div>
      </div>
      <div class="cards-grid" id="causeCards">
        <div class="cause-card" id="card-edu" onclick="showPayment('Education','{upi_edu}','{qr_edu}','card-edu')"><span class="cause-emoji">&#127891;</span><h3>Education</h3><p>Help a child learn</p></div>
        <div class="cause-card" id="card-food" onclick="showPayment('Food Support','{upi_food}','{qr_food}','card-food')"><span class="cause-emoji">&#127869;&#65039;</span><h3>Food Support</h3><p>Feed a hungry soul</p></div>
        <div class="cause-card" id="card-health" onclick="showPayment('Healthcare','{upi_health}','{qr_health}','card-health')"><span class="cause-emoji">&#127973;</span><h3>Healthcare</h3><p>Gift of health</p></div>
        <div class="cause-card" id="card-women" onclick="showPayment('Women Empowerment','{upi_women}','{qr_women}','card-women')"><span class="cause-emoji">&#128105;</span><h3>Women Empower</h3><p>Empower a woman</p></div>
      </div>
      <div class="upi-section" id="upiSection">
        <div class="upi-title" id="upiCategory">&#128157; Donate karein</div>
        <div class="upi-subtitle">&#128241; QR scan karein - GPay / PhonePe / Paytm seedha khulega</div>
        <div class="qr-wrap"><img id="qrImg" src="" alt="UPI QR"></div>
        <a id="upiDirectBtn" href="#" class="btn-upi">
          <i class="fas fa-mobile-alt"></i> GPay / PhonePe Se Pay Karein
        </a>
        <div class="upi-or">- ya QR scan karein -</div>
        <div class="upi-steps">
          <div class="upi-step"><div class="step-num">1</div><div class="step-txt">Cause chunein</div></div>
          <div class="upi-step"><div class="step-num">2</div><div class="step-txt">QR scan karein</div></div>
          <div class="upi-step"><div class="step-num">3</div><div class="step-txt">UPI se pay karein</div></div>
          <div class="upi-step"><div class="step-num">4</div><div class="step-txt">Form fill karein</div></div>
        </div>
        <button onclick="showDonationForm()" class="btn btn-primary"
                style="max-width:300px;margin:24px auto 0;display:flex;background:linear-gradient(135deg,#16a34a,#15803d);">
          <i class="fas fa-check-circle"></i> Payment Ho Gayi - Details Bharein
        </button>
      </div>
      <div class="payment-done-section" id="donationFormSection">
        <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:14px;padding:18px;margin-bottom:18px;display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
          <span style="font-size:26px;">&#9989;</span>
          <div>
            <div style="font-weight:700;color:#16a34a;font-size:15px;">Payment Ho Gayi! Ab Details Bharein</div>
            <div style="color:#166534;font-size:12px;margin-top:3px;">Aapki donation record ho jaayegi - dashboard mein save hogi.</div>
          </div>
        </div>
        <div style="background:linear-gradient(135deg,#fefce8,#fff8f0);border:2px solid #fcd34d;border-radius:14px;padding:14px 18px;margin-bottom:20px;display:flex;align-items:flex-start;gap:12px;">
          <span style="font-size:22px;">&#127874;</span>
          <div>
            <div style="font-weight:700;color:#92400e;font-size:13px;">Birthday par Special Email Paayein! (Optional)</div>
            <div style="color:#78350f;font-size:12px;margin-top:3px;">Email + DOB darj karein - birthday par wish karenge!</div>
          </div>
        </div>
        <form method="POST" id="donationForm">
          <div class="form-group">
            <label>Full Name <span style="color:red;">*</span></label>
            <input type="text" name="name" class="form-control" placeholder="Aapka poora naam" required>
          </div>
          <div class="form-group">
            <label>Donation Amount (&#8377;) <span style="color:red;">*</span></label>
            <input type="number" name="amount" class="form-control" placeholder="e.g. 500" required>
          </div>
          <div class="form-group">
            <label>Purpose of Donation</label>
            <input type="text" name="purpose" id="purposeInput" class="form-control" readonly style="background:#f4f4f5;">
          </div>
          <div class="form-group">
            <label>UPI Transaction ID <span style="color:var(--muted);font-size:11px;">(Optional)</span></label>
            <input type="text" name="txn_id" class="form-control" placeholder="e.g. 123456789012">
          </div>
          <div style="background:#f8faff;border:1px solid #dbeafe;border-radius:12px;padding:16px;margin-bottom:8px;">
            <div style="font-size:13px;font-weight:600;color:#1e40af;margin-bottom:12px;"><i class="fas fa-birthday-cake" style="margin-right:5px;"></i>Birthday Wish ke liye (Optional) &#127874;</div>
            <div class="form-group" style="margin-bottom:12px;">
              <label><i class="fas fa-envelope" style="color:var(--saffron);margin-right:5px;"></i> Email Address</label>
              <input type="email" name="email" class="form-control" placeholder="you@example.com">
            </div>
            <div class="form-group" style="margin-bottom:0;">
              <label><i class="fas fa-birthday-cake" style="color:#f59e0b;margin-right:5px;"></i> Date of Birth</label>
              <input type="date" name="dob" class="form-control">
            </div>
          </div>
          <button type="submit" class="btn btn-primary" style="margin-top:18px;">
            <i class="fas fa-heart"></i> Donation Submit Karein
          </button>
        </form>
      </div>
    </div>
    <script>
    var showFormNow = {show_form};
    var presetCat   = "{preset_cat}";
    function showPayment(category, upiLink, qrSrc, cardId) {{
      document.querySelectorAll('.cause-card').forEach(c => c.classList.remove('active-cause'));
      document.getElementById(cardId).classList.add('active-cause');
      document.getElementById('upiCategory').innerText = 'Donating for: ' + category;
      document.getElementById('qrImg').src = qrSrc;
      document.getElementById('upiDirectBtn').href = upiLink;
      document.getElementById('purposeInput').value = category;
      var sec = document.getElementById('upiSection');
      sec.style.display = 'block';
      document.getElementById('donationFormSection').style.display = 'none';
      sec.scrollIntoView({{behavior:'smooth', block:'center'}});
    }}
    function showDonationForm() {{
      document.getElementById('upiSection').style.display = 'none';
      var fs = document.getElementById('donationFormSection');
      fs.style.display = 'block';
      fs.scrollIntoView({{behavior:'smooth', block:'start'}});
    }}
    if (showFormNow && presetCat) {{
      var cardMap = {{'Education':'card-edu','Food Support':'card-food','Healthcare':'card-health','Women Empowerment':'card-women'}};
      var cid = cardMap[presetCat];
      if (cid) document.getElementById(cid).classList.add('active-cause');
      document.getElementById('purposeInput').value = presetCat;
      document.getElementById('upiSection').style.display = 'none';
      var fs = document.getElementById('donationFormSection');
      fs.style.display = 'block';
      fs.scrollIntoView({{behavior:'smooth', block:'start'}});
    }}
    </script>"""
    return render_template_string(base_html, content=content)

# ================= PAYMENT REDIRECT =================
@app.route("/payment-done")
def payment_done():
    cat = request.args.get('cat', 'Education')
    return redirect(url_for('donate', paid='1', cat=cat))

# ================= VOLUNTEER =================
@app.route("/volunteer", methods=["GET","POST"])
def volunteer():
    if request.method == "POST":
        name  = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        dob   = request.form.get('dob', '')
        conn = sqlite3.connect("ngo.db")
        c = conn.cursor()
        c.execute("INSERT INTO volunteer(name,email,phone,dob) VALUES (?,?,?,?)", (name, email, phone, dob))
        conn.commit(); conn.close()
        send_email(email, "Welcome to Helping Hands NGO!", welcome_email_html(name))
        return redirect(url_for('home'))
    content = """
    <div class="section">
      <div class="section-header">
        <div class="section-icon">&#129309;</div>
        <div class="section-title"><h2>Become a Volunteer</h2><p>Be the reason someone smiles today</p></div>
      </div>
      <div style="display:grid;grid-template-columns:1fr;gap:28px;align-items:start;">
        <div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
            <div style="background:#fff8f0;border:1px solid #fcd9aa;border-radius:13px;padding:18px;display:flex;align-items:flex-start;gap:10px;">
              <span style="font-size:22px;">&#128336;</span>
              <div><div style="font-weight:600;color:#1a3c2e;margin-bottom:4px;font-size:14px;">Flexible Hours</div><div style="color:#6b7280;font-size:12px;">Work on your schedule.</div></div>
            </div>
            <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:13px;padding:18px;display:flex;align-items:flex-start;gap:10px;">
              <span style="font-size:22px;">&#127807;</span>
              <div><div style="font-weight:600;color:#1a3c2e;margin-bottom:4px;font-size:14px;">Skill Growth</div><div style="color:#6b7280;font-size:12px;">Grow personally & professionally.</div></div>
            </div>
            <div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:13px;padding:18px;display:flex;align-items:flex-start;gap:10px;">
              <span style="font-size:22px;">&#127885;</span>
              <div><div style="font-weight:600;color:#1a3c2e;margin-bottom:4px;font-size:14px;">Certificate</div><div style="color:#6b7280;font-size:12px;">Official volunteer certificate.</div></div>
            </div>
            <div style="background:#fefce8;border:1px solid #fef08a;border-radius:13px;padding:18px;display:flex;align-items:flex-start;gap:10px;">
              <span style="font-size:22px;">&#128231;</span>
              <div><div style="font-weight:600;color:#1a3c2e;margin-bottom:4px;font-size:14px;">Welcome Email</div><div style="color:#6b7280;font-size:12px;">Register karte hi email aayega!</div></div>
            </div>
          </div>
        </div>
        <div>
          <form method="POST">
            <div class="form-group"><label><i class="fas fa-user" style="color:var(--saffron);margin-right:6px;"></i> Full Name</label><input type="text" name="name" class="form-control" placeholder="Your full name" required></div>
            <div class="form-group"><label><i class="fas fa-envelope" style="color:var(--saffron);margin-right:6px;"></i> Email Address</label><input type="email" name="email" class="form-control" placeholder="you@example.com" required></div>
            <div class="form-group"><label><i class="fas fa-phone" style="color:var(--saffron);margin-right:6px;"></i> Phone Number</label><input type="text" name="phone" class="form-control" placeholder="+91 XXXXX XXXXX" required></div>
            <div class="form-group">
              <label><i class="fas fa-birthday-cake" style="color:#f59e0b;margin-right:6px;"></i> Date of Birth (Optional)</label>
              <input type="date" name="dob" class="form-control">
            </div>
            <button type="submit" class="btn btn-green" style="margin-top:8px;"><i class="fas fa-hands-helping"></i> Register as Volunteer</button>
          </form>
        </div>
      </div>
    </div>"""
    return render_template_string(base_html, content=content)

# ================= LOGIN =================
@app.route("/login", methods=["GET","POST"])
def login():
    error = ""
    if request.method == "POST":
        if request.form['username'] == ADMIN_USERNAME and request.form['password'] == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin'))
        else:
            error = """<div class="alert alert-error"><i class="fas fa-exclamation-circle"></i> Invalid credentials.</div>"""
    content = f"""
    <div style="max-width:420px;margin:0 auto;"><div class="section">
      <div style="text-align:center;margin-bottom:28px;">
        <div style="width:58px;height:58px;background:linear-gradient(135deg,#1a3c2e,#2d6a4f);border-radius:18px;display:flex;align-items:center;justify-content:center;font-size:26px;margin:0 auto 14px;">&#128272;</div>
        <h2 style="font-family:'Playfair Display',serif;font-size:24px;color:#1a3c2e;">Admin Login</h2>
        <p style="color:#6b7280;font-size:13px;margin-top:5px;">Secure access for NGO administrators only</p>
      </div>
      {error}
      <form method="POST">
        <div class="form-group"><label><i class="fas fa-user" style="color:var(--saffron);margin-right:6px;"></i> Username</label><input type="text" name="username" class="form-control" placeholder="Enter username" required></div>
        <div class="form-group"><label><i class="fas fa-lock" style="color:var(--saffron);margin-right:6px;"></i> Password</label><input type="password" name="password" class="form-control" placeholder="Enter password" required></div>
        <button type="submit" class="btn btn-primary" style="margin-top:8px;"><i class="fas fa-sign-in-alt"></i> Login to Dashboard</button>
      </form>
      <div style="text-align:center;margin-top:18px;"><a href="/" style="color:#6b7280;font-size:13px;text-decoration:none;"><i class="fas fa-arrow-left"></i> Back to Home</a></div>
    </div></div>"""
    return render_template_string(base_html, content=content)

@app.route("/logout")
def logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('home'))

# ================= ADMIN =================
@app.route("/admin")
@login_required
def admin():
    conn = sqlite3.connect("ngo.db")
    c = conn.cursor()
    c.execute("SELECT * FROM donation")
    donations = c.fetchall()
    c.execute("SELECT * FROM volunteer")
    volunteers = c.fetchall()
    total_donations  = len(donations)
    total_volunteers = len(volunteers)
    c.execute("SELECT SUM(CAST(amount as INTEGER)) FROM donation")
    total_amount = c.fetchone()[0] or 0
    conn.close()
    today_md = datetime.now().strftime("%m-%d")

    d_rows = ""
    for d in donations:
        demail = d[4] if len(d) > 4 else ""
        ddob   = d[5] if len(d) > 5 else ""
        dtxn   = d[6] if len(d) > 6 else ""
        d_rows += f"""<tr>
          <td><span style="font-weight:600;color:#6b7280;">#{d[0]}</span></td>
          <td style="font-weight:500;">{d[1]}</td>
          <td><span class="badge badge-green">&#8377; {d[2]}</span></td>
          <td><span class="badge badge-orange">{d[3]}</span></td>
          <td style="font-size:12px;">{demail or '<span style="color:#aaa;">-</span>'}</td>
          <td style="font-size:12px;">{ddob or '<span style="color:#aaa;">-</span>'}</td>
          <td style="font-size:12px;max-width:100px;overflow:hidden;text-overflow:ellipsis;">{dtxn or '<span style="color:#aaa;">-</span>'}</td>
          <td style="white-space:nowrap;">
            <a href='/edit_donation/{d[0]}' class='btn-edit'><i class='fas fa-edit'></i></a>
            <a href='/delete_donation/{d[0]}' class='btn-delete' onclick='return confirm("Delete?")'><i class='fas fa-trash'></i></a>
          </td></tr>"""

    v_rows = ""
    today_bdays = 0
    for v in volunteers:
        vid,vname,vemail,vphone = v[0],v[1],v[2],v[3]
        vdob = v[4] if len(v) > 4 else ""
        is_bday = bool(vdob and len(vdob) >= 10 and vdob[5:] == today_md)
        if is_bday: today_bdays += 1
        bday_badge = '<span class="badge badge-birthday" style="margin-left:5px;"><i class="fas fa-birthday-cake"></i> Birthday!</span>' if is_bday else ""
        email_btn  = f'<a href="/send_wish/{vid}" class="btn-email" style="margin-right:4px;"><i class="fas fa-envelope"></i></a>' if is_bday else ""
        row_style  = 'style="background:linear-gradient(90deg,#fefce8,#fff);"' if is_bday else ""
        v_rows += f"""<tr {row_style}>
          <td><span style="font-weight:600;color:#6b7280;">#{vid}</span></td>
          <td style="font-weight:500;">{vname}{bday_badge}</td>
          <td>{vemail}</td><td>{vphone}</td>
          <td>{vdob or '<span style="color:#aaa;">-</span>'}</td>
          <td style="white-space:nowrap;">{email_btn}
            <a href='/edit_volunteer/{vid}' class='btn-edit'><i class='fas fa-edit'></i></a>
            <a href='/delete_volunteer/{vid}' class='btn-delete' onclick='return confirm("Delete?")'><i class='fas fa-trash'></i></a>
          </td></tr>"""

    bday_alert = ""
    if today_bdays > 0:
        bday_alert = f"""<div class="bday-banner">
          <div class="ico">&#127874;</div>
          <div>
            <div style="font-weight:700;color:#92400e;font-size:15px;">Aaj {today_bdays} volunteer(s) ka Birthday hai! &#127881;</div>
            <div style="color:#78350f;font-size:12px;margin-top:3px;">Email icon dabayein - birthday wish turant jaayegi!</div>
          </div></div>"""

    content = f"""
    <div class="section">
      <div class="section-header">
        <div class="section-icon">&#9881;&#65039;</div>
        <div class="section-title"><h2>Admin Control Panel</h2><p>Manage donations, volunteers and NGO records</p></div>
      </div>
      {bday_alert}
      <div class="cards-grid" style="margin-bottom:36px;">
        <div class="dash-stat"><div class="dash-stat-icon" style="background:#fff8f0;">&#128176;</div><div class="dash-stat-value">{total_donations}</div><div class="dash-stat-label">Total Donations</div><div class="dash-stat-bar" style="background:linear-gradient(90deg,var(--saffron),var(--saffron-light));"></div></div>
        <div class="dash-stat"><div class="dash-stat-icon" style="background:#f0fdf4;">&#128101;</div><div class="dash-stat-value">{total_volunteers}</div><div class="dash-stat-label">Total Volunteers</div><div class="dash-stat-bar" style="background:linear-gradient(90deg,var(--mid-green),var(--light-green));"></div></div>
        <div class="dash-stat"><div class="dash-stat-icon" style="background:#eff6ff;">&#128181;</div><div class="dash-stat-value" style="font-size:24px;">&#8377;{total_amount:,}</div><div class="dash-stat-label">Amount Collected</div><div class="dash-stat-bar" style="background:linear-gradient(90deg,#3b82f6,#60a5fa);"></div></div>
        <div class="dash-stat"><div class="dash-stat-icon" style="background:#fefce8;">&#127874;</div><div class="dash-stat-value">{today_bdays}</div><div class="dash-stat-label">Aaj ke Birthdays</div><div class="dash-stat-bar" style="background:linear-gradient(90deg,#f59e0b,#ef4444);"></div></div>
      </div>
      <h3 style="font-family:'Playfair Display',serif;font-size:18px;color:#1a3c2e;margin-bottom:4px;"><i class="fas fa-donate" style="color:var(--saffron);"></i> Donation Records</h3>
      <p style="color:#6b7280;font-size:12px;margin-bottom:10px;">{total_donations} total entries</p>
      {"<p style='color:#6b7280;'>No donations yet.</p>" if not donations else
        f'<div class="table-wrap"><table><thead><tr><th>#</th><th>Name</th><th>Amount</th><th>Purpose</th><th>Email</th><th>DOB</th><th>TXN ID</th><th>Act.</th></tr></thead><tbody>{d_rows}</tbody></table></div>'}
      <div style="margin-top:36px;">
        <h3 style="font-family:'Playfair Display',serif;font-size:18px;color:#1a3c2e;margin-bottom:4px;"><i class="fas fa-users" style="color:var(--mid-green);"></i> Volunteer Records</h3>
        <p style="color:#6b7280;font-size:12px;margin-bottom:10px;">{total_volunteers} total entries</p>
        {"<p style='color:#6b7280;'>No volunteers yet.</p>" if not volunteers else
          f'<div class="table-wrap"><table><thead><tr><th>#</th><th>Name</th><th>Email</th><th>Phone</th><th>DOB</th><th>Act.</th></tr></thead><tbody>{v_rows}</tbody></table></div>'}
      </div>
    </div>"""
    return render_template_string(base_html, content=content)

# ================= SEND WISH =================
@app.route("/send_wish/<int:vid>")
@login_required
def send_wish(vid):
    conn = sqlite3.connect("ngo.db")
    c    = conn.cursor()
    c.execute("SELECT name,email FROM volunteer WHERE id=?", (vid,))
    row  = c.fetchone()
    conn.close()
    if not row:
        return redirect(url_for('admin'))
    name, email = row
    ok, msg = send_email(email, f"Happy Birthday {name}! - Helping Hands NGO", birthday_email_html(name))
    alert_class = "alert-success" if ok else "alert-error"
    icon        = "check-circle" if ok else "exclamation-circle"
    text        = f"Birthday email bhej diya gaya - {name} ({email})" if ok else f"Error: {msg}"
    content = f"""
    <div style="max-width:520px;margin:0 auto;"><div class="section">
      <div class="section-header"><div class="section-icon">&#128231;</div><div class="section-title"><h2>Birthday Email Wish</h2><p>Result</p></div></div>
      <div class="alert {alert_class}"><i class="fas fa-{icon}"></i> {text}</div>
      <a href="/admin" class="btn-secondary"><i class="fas fa-arrow-left"></i> Admin Panel Par Wapas</a>
    </div></div>"""
    return render_template_string(base_html, content=content)

# ================= EDIT DONATION =================
@app.route("/edit_donation/<int:id>", methods=["GET","POST"])
@login_required
def edit_donation(id):
    conn = sqlite3.connect("ngo.db")
    c = conn.cursor()
    if request.method == "POST":
        c.execute("UPDATE donation SET name=?,amount=?,purpose=?,email=?,dob=?,txn_id=? WHERE id=?",
                  (request.form['name'],request.form['amount'],request.form['purpose'],
                   request.form.get('email',''),request.form.get('dob',''),
                   request.form.get('txn_id',''),id))
        conn.commit(); conn.close()
        return redirect(url_for('admin'))
    c.execute("SELECT * FROM donation WHERE id=?", (id,))
    d = c.fetchone(); conn.close()
    if not d: return redirect(url_for('admin'))
    demail = d[4] if len(d)>4 else ""
    ddob   = d[5] if len(d)>5 else ""
    dtxn   = d[6] if len(d)>6 else ""
    content = f"""
    <div style="max-width:520px;margin:0 auto;"><div class="section">
      <div class="section-header"><div class="section-icon">&#9999;&#65039;</div><div class="section-title"><h2>Edit Donation</h2><p>Record #{id}</p></div></div>
      <form method="POST">
        <div class="form-group"><label>Full Name</label><input type="text" name="name" class="form-control" value="{d[1]}" required></div>
        <div class="form-group"><label>Amount</label><input type="number" name="amount" class="form-control" value="{d[2]}" required></div>
        <div class="form-group"><label>Purpose</label><input type="text" name="purpose" class="form-control" value="{d[3]}" required></div>
        <div class="form-group"><label>Email</label><input type="email" name="email" class="form-control" value="{demail}"></div>
        <div class="form-group"><label>Date of Birth</label><input type="date" name="dob" class="form-control" value="{ddob}"></div>
        <div class="form-group"><label>UPI TXN ID</label><input type="text" name="txn_id" class="form-control" value="{dtxn}"></div>
        <button type="submit" class="btn btn-primary"><i class="fas fa-save"></i> Save Changes</button>
        <a href="/admin" class="btn-secondary"><i class="fas fa-arrow-left"></i> Cancel</a>
      </form>
    </div></div>"""
    return render_template_string(base_html, content=content)

@app.route("/delete_donation/<int:id>")
@login_required
def delete_donation(id):
    conn = sqlite3.connect("ngo.db")
    conn.cursor().execute("DELETE FROM donation WHERE id=?", (id,))
    conn.commit(); conn.close()
    return redirect(url_for('admin'))

# ================= EDIT VOLUNTEER =================
@app.route("/edit_volunteer/<int:id>", methods=["GET","POST"])
@login_required
def edit_volunteer(id):
    conn = sqlite3.connect("ngo.db")
    c = conn.cursor()
    if request.method == "POST":
        c.execute("UPDATE volunteer SET name=?,email=?,phone=?,dob=? WHERE id=?",
                  (request.form['name'],request.form['email'],
                   request.form['phone'],request.form.get('dob',''),id))
        conn.commit(); conn.close()
        return redirect(url_for('admin'))
    c.execute("SELECT * FROM volunteer WHERE id=?", (id,))
    v = c.fetchone(); conn.close()
    if not v: return redirect(url_for('admin'))
    vdob = v[4] if len(v)>4 else ""
    content = f"""
    <div style="max-width:520px;margin:0 auto;"><div class="section">
      <div class="section-header"><div class="section-icon">&#9999;&#65039;</div><div class="section-title"><h2>Edit Volunteer</h2><p>Record #{id}</p></div></div>
      <form method="POST">
        <div class="form-group"><label>Full Name</label><input type="text" name="name" class="form-control" value="{v[1]}" required></div>
        <div class="form-group"><label>Email Address</label><input type="email" name="email" class="form-control" value="{v[2]}" required></div>
        <div class="form-group"><label>Phone Number</label><input type="text" name="phone" class="form-control" value="{v[3]}" required></div>
        <div class="form-group"><label><i class="fas fa-birthday-cake" style="color:#f59e0b;margin-right:5px;"></i> Date of Birth</label><input type="date" name="dob" class="form-control" value="{vdob}"></div>
        <button type="submit" class="btn btn-green"><i class="fas fa-save"></i> Save Changes</button>
        <a href="/admin" class="btn-secondary"><i class="fas fa-arrow-left"></i> Cancel</a>
      </form>
    </div></div>"""
    return render_template_string(base_html, content=content)

@app.route("/delete_volunteer/<int:id>")
@login_required
def delete_volunteer(id):
    conn = sqlite3.connect("ngo.db")
    conn.cursor().execute("DELETE FROM volunteer WHERE id=?", (id,))
    conn.commit(); conn.close()
    return redirect(url_for('admin'))

if __name__ == "__main__":
    if not os.path.exists("static"):
        os.makedirs("static")
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "127.0.0.1"
    print(f"\n✅ Server chal raha hai!")
    print(f"   PC pe kholein:    http://localhost:5000")
    print(f"   Phone pe kholein: http://{local_ip}:5000\n")
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)