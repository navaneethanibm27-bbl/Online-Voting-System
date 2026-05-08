from flask import Flask, render_template, request, redirect, session, flash
import sqlite3, random
from werkzeug.security import generate_password_hash, check_password_hash 

app = Flask(__name__)
app.secret_key = "supersecretkey"

# 🔐 Admin Credentials
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"

# ---------------- DATABASE ----------------
def get_db():
    return sqlite3.connect("voting.db", timeout=10)

def init_db():
    with get_db() as conn:
        c = conn.cursor()

        c.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            phone TEXT,
            aadhaar TEXT,
            email TEXT UNIQUE,
            password TEXT,
            has_voted INTEGER DEFAULT 0
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            candidate_id INTEGER
        )''')

init_db()

# ---------------- HOME ----------------
@app.route('/')
def home():
    return render_template('index.html')

# ---------------- REGISTER ----------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.form

        # Basic validation
        if not data['email'] or not data['password']:
            return "All fields required"

        otp = str(random.randint(1000, 9999))
        print("🔑 OTP:", otp)  # 👉 CHECK TERMINAL

        session['otp'] = otp
        session['temp_user'] = dict(data)

        return f"Your OTP is: {otp} <br><a href='/verify'>Verify</a>"

    return render_template('register.html')

# ---------------- OTP VERIFY ----------------
@app.route('/verify', methods=['GET', 'POST'])
def verify():
    if 'otp' not in session:
        return redirect('/register')

    if request.method == 'POST':
        user_otp = request.form.get('otp')

        if user_otp == session.get('otp'):
            data = session.get('temp_user')

            try:
                with get_db() as conn:
                    c = conn.cursor()
                    hashed = generate_password_hash(data['password'])

                    c.execute("""
                        INSERT INTO users(name, phone, aadhaar, email, password)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        data['name'],
                        data['phone'],
                        data['aadhaar'],
                        data['email'],
                        hashed
                    ))

                session.pop('otp', None)
                session.pop('temp_user', None)

                return "✅ Registration Successful! <a href='/login'>Login</a>"

            except sqlite3.IntegrityError:
                return "❌ Email already registered"

        else:
            return "❌ Wrong OTP"

    return render_template('otp.html')

# ---------------- LOGIN ----------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        with get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE email=?", (email,))
            user = c.fetchone()

        if user and check_password_hash(user[5], password):
            session['user_id'] = user[0]
            return redirect('/vote')

        return "❌ Invalid Email or Password"

    return render_template('login.html')

# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# ---------------- VOTE ----------------
@app.route('/vote', methods=['GET', 'POST'])
def vote():
    if 'user_id' not in session:
        return redirect('/login')

    with get_db() as conn:
        c = conn.cursor()

        uid = session['user_id']

        # Check if user already voted
        c.execute("SELECT has_voted FROM users WHERE id=?", (uid,))
        voted = c.fetchone()[0]

        if voted == 1:
            return redirect('/leader')

        # Get candidates
        c.execute("SELECT * FROM candidates")
        candidates = c.fetchall()

        if request.method == 'POST':
            cid = request.form.get('candidate')

            if not cid:
                return "⚠️ Select candidate"

            c.execute("INSERT INTO votes(user_id, candidate_id) VALUES (?, ?)", (uid, cid))
            c.execute("UPDATE users SET has_voted=1 WHERE id=?", (uid,))
            conn.commit()

            return redirect('/leader')

    return render_template('vote.html', candidates=candidates)

# ---------------- LEADERBOARD ----------------
@app.route('/leader')
def leader():
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT candidates.name, COUNT(votes.id) as votes
            FROM candidates
            LEFT JOIN votes ON candidates.id = votes.candidate_id
            GROUP BY candidates.id
            ORDER BY votes DESC
        """)
        rows = c.fetchall()

    total_votes = sum(row[1] for row in rows)
    stats = []
    for name, votes in rows:
        percentage = round((votes / total_votes) * 100, 1) if total_votes else 0
        stats.append({
            'name': name,
            'votes': votes,
            'percentage': percentage
        })

    leader = stats[0] if stats else None
    return render_template('leader.html', stats=stats, total_votes=total_votes, leader=leader)


# ---------------- ADMIN LOGIN ----------------
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        user = request.form['user']
        password = request.form['pass']

        if user == ADMIN_USER and password == ADMIN_PASS:
            session['admin'] = True
            return redirect('/admin')

        return "❌ Wrong Admin Credentials"

    return render_template('admin_login.html')

# ---------------- ADMIN PANEL ----------------
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if not session.get('admin'):
        return redirect('/admin_login')

    with get_db() as conn:
        c = conn.cursor()

        if request.method == 'POST':
            edit_id = request.form.get('edit_id')
            if edit_id:
                edit_name = request.form.get('edit_name')
                if edit_name:
                    c.execute("UPDATE candidates SET name=? WHERE id=?", (edit_name, edit_id))
                    conn.commit()
            else:
                name = request.form.get('name')
                if name:
                    c.execute("INSERT INTO candidates(name) VALUES(?)", (name,))
                    conn.commit()

        c.execute("SELECT * FROM candidates")
        candidates = c.fetchall()

    return render_template('admin.html', candidates=candidates)

# ---------------- RESULTS ----------------
@app.route('/results')
def results():
    with get_db() as conn:
        c = conn.cursor()

        c.execute("""
            SELECT candidates.name, COUNT(votes.id)
            FROM candidates
            LEFT JOIN votes ON candidates.id = votes.candidate_id
            GROUP BY candidates.name
        """)

        results = c.fetchall()

    return render_template('results.html', results=results)

# ---------------- RUN ----------------
if __name__ == '__main__':
    app.run(debug=True)