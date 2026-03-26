import os
import sqlite3
import secrets
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, g, redirect, render_template, request, session, url_for, flash
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'app.db')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'love-mug-segreto-2026')
app.config['ADMIN_USERNAME'] = os.environ.get('ADMIN_USERNAME', 'admin')
app.config['ADMIN_PASSWORD_HASH'] = os.environ.get(
    'ADMIN_PASSWORD_HASH',
    'pbkdf2:sha256:600000$M4y1Rc2PAojMuE7g$e438479c8415ddae46ebddbbdc55a5ff0b0d672d0a968a4507beb248e206ce43'
)


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def execute(query, args=(), one=False, commit=False):
    db = get_db()
    cur = db.execute(query, args)
    if commit:
        db.commit()
    rows = cur.fetchall()
    cur.close()
    return (rows[0] if rows else None) if one else rows


def set_setting(key, value):
    db = get_db()
    db.execute(
        'INSERT INTO settings (key, value) VALUES (?, ?) '
        'ON CONFLICT(key) DO UPDATE SET value = excluded.value',
        (key, value)
    )
    db.commit()


def get_setting(key, default=None):
    row = execute('SELECT value FROM settings WHERE key = ?', (key,), one=True)
    return row['value'] if row else default


def parse_dt(value):
    if not value:
        return None
    return datetime.fromisoformat(value)


def now_iso():
    return datetime.utcnow().isoformat(timespec='seconds')


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return view(*args, **kwargs)
    return wrapped


def init_db(seed=True):
    db = sqlite3.connect(DB_PATH)
    with open(os.path.join(BASE_DIR, 'schema.sql'), 'r', encoding='utf-8') as f:
        db.executescript(f.read())
    db.commit()

    if seed:
        cur = db.execute('SELECT COUNT(*) FROM settings')
        settings_count = cur.fetchone()[0]
        if settings_count == 0:
            db.execute('INSERT INTO settings (key, value) VALUES (?, ?)', ('variants_enabled', '1'))
            db.execute('INSERT INTO settings (key, value) VALUES (?, ?)', ('renewal_price_text', '€9,90 / anno'))
            db.execute('INSERT INTO settings (key, value) VALUES (?, ?)', ('brand_name', 'Love Mug'))

        cur = db.execute('SELECT COUNT(*) FROM messages')
        messages_count = cur.fetchone()[0]
        if messages_count == 0:
            seed_messages = {
                'lei': [
                    'Il tuo sorriso merita più spazio nei giorni normali.',
                    'Non servono occasioni speciali per ricordarti quanto vali.',
                    'Oggi concediti la stessa dolcezza che dai agli altri.'
                ],
                'lui': [
                    'Le cose vere si riconoscono dalla pace che lasciano.',
                    'Anche i giorni semplici meritano un pensiero che resta.',
                    'Oggi ricordati che conti più di quanto immagini.'
                ],
                'neutro': [
                    'A volte basta un piccolo segno per cambiare il tono della giornata.',
                    'Le cose belle non fanno rumore, ma restano.',
                    'Oggi prenditi un momento per te e fallo valere.'
                ]
            }
            for variant, msgs in seed_messages.items():
                for idx, text in enumerate(msgs, start=1):
                    db.execute(
                        'INSERT INTO messages (variant, body, is_active, sort_order) VALUES (?, ?, 1, ?)',
                        (variant, text, idx)
                    )

        cur = db.execute('SELECT COUNT(*) FROM activation_codes')
        code_count = cur.fetchone()[0]
        if code_count == 0:
            for _ in range(12):
                code = 'LOVE-' + ''.join(secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(6))
                db.execute('INSERT INTO activation_codes (code, status, created_at) VALUES (?, ?, ?)', (code, 'unused', now_iso()))

    db.commit()
    db.close()


def pick_message(variant: str):
    rows = execute(
        'SELECT body FROM messages WHERE variant = ? AND is_active = 1 ORDER BY sort_order, id',
        (variant,)
    )
    if not rows:
        rows = execute(
            'SELECT body FROM messages WHERE variant = ? AND is_active = 1 ORDER BY sort_order, id',
            ('neutro',)
        )
    if not rows:
        return 'Nessun messaggio disponibile.'
    day_index = datetime.utcnow().timetuple().tm_yday
    return rows[(day_index - 1) % len(rows)]['body']


@app.route('/')
def index():
    return redirect(url_for('love_home'))

@app.route('/love/check')
def love_check():
    token = request.args.get('love_token', '').strip()

    if not token:
        return {
            'status': 'invalid',
            'redirect_url': 'https://latazzacheparlalove2026.app-me.it/collecting'
        }

    db = get_db()
    row = db.execute(
        'SELECT * FROM activation_codes WHERE token = ?',
        (token,)
    ).fetchone()

    if not row:
        return {
            'status': 'invalid',
            'redirect_url': 'https://latazzacheparlalove2026.app-me.it/collecting'
        }

    expiry = parse_dt(row['expiry_date'])
    now = datetime.now(UTC)

    if row['status'] == 'active' and expiry and expiry > now:
        return {
            'status': 'active',
            'redirect_url': 'https://latazzacheparlalove2026.app-me.it'
        }

    return {
        'status': 'expired',
        'redirect_url': 'https://latazzacheparlalove2026.app-me.it/collecting'
    }


@app.route('/love')
def love_home():
    brand_name = get_setting('brand_name', 'Love Mug')
    return render_template('landing.html', brand_name=brand_name)


@app.route('/love/activate', methods=['GET', 'POST'])
def activate_code():
    brand_name = get_setting('brand_name', 'Love Mug')
    if request.method == 'POST':
        code = request.form.get('code', '').strip().upper()
        row = execute('SELECT * FROM activation_codes WHERE code = ?', (code,), one=True)
        if not row:
            flash('Codice non riconosciuto. Controlla e riprova.')
            return render_template('activate.html', brand_name=brand_name)
        if row['status'] != 'unused':
            flash('Questo codice risulta già utilizzato o non disponibile.')
            return render_template('activate.html', brand_name=brand_name)
        session['pending_code'] = code
        if get_setting('variants_enabled', '1') == '1':
            return redirect(url_for('choose_variant'))
        return complete_activation(code=code, variant='neutro')
    return render_template('activate.html', brand_name=brand_name)


@app.route('/love/variant', methods=['GET', 'POST'])
def choose_variant():
    brand_name = get_setting('brand_name', 'Love Mug')
    if 'pending_code' not in session:
        return redirect(url_for('activate_code'))
    if get_setting('variants_enabled', '1') != '1':
        return complete_activation(code=session['pending_code'], variant='neutro')
    if request.method == 'POST':
        variant = request.form.get('variant', 'neutro')
        if variant not in {'lei', 'lui', 'neutro'}:
            flash('Selezione non valida.')
            return render_template('variant.html', brand_name=brand_name)
        return complete_activation(code=session['pending_code'], variant=variant)
    return render_template('variant.html', brand_name=brand_name)


def complete_activation(code: str, variant: str):
    token = secrets.token_urlsafe(18)
    activation_date = datetime.utcnow()
    expiry_date = activation_date + timedelta(days=365)
    db = get_db()
    db.execute(
        'UPDATE activation_codes SET status = ?, variant = ?, token = ?, activation_date = ?, expiry_date = ?, last_access = ? WHERE code = ?',
        ('active', variant, token, activation_date.isoformat(timespec='seconds'), expiry_date.isoformat(timespec='seconds'), activation_date.isoformat(timespec='seconds'), code)
    )
    db.commit()
    session.pop('pending_code', None)
    return redirect(f"https://latazzacheparlalove2026.app-me.it/mobile/communication?love_token={token}")


@app.route('/love/t/<token>')
def love_token(token):
    row = execute('SELECT * FROM activation_codes WHERE token = ?', (token,), one=True)
    if not row:
        return render_template('error.html', message='Link non valido o non più disponibile.'), 404

    now = datetime.utcnow()
    expiry = parse_dt(row['expiry_date'])

    execute('UPDATE activation_codes SET last_access = ? WHERE id = ?', (now_iso(), row['id']), commit=True)

    if row['status'] == 'active' and expiry and now <= expiry:
        message = pick_message(row['variant'] or 'neutro')
        return render_template(
            'message.html',
            message=message,
            token=token,
            variant=row['variant'] or 'neutro',
            activated=request.args.get('activated') == '1'
        )

    if row['status'] in {'expired', 'active'} and expiry and now > expiry:
        execute('UPDATE activation_codes SET status = ? WHERE id = ?', ('expired', row['id']), commit=True)
        return render_template(
            'renew.html',
            token=token,
            renewal_price_text=get_setting('renewal_price_text', '€9,90 / anno')
        )

    if row['status'] == 'renewal_pending':
        return render_template('pending.html', token=token)

    return render_template('renew.html', token=token, renewal_price_text=get_setting('renewal_price_text', '€9,90 / anno'))


@app.route('/love/renew/<token>', methods=['POST'])
def renew(token):
    row = execute('SELECT * FROM activation_codes WHERE token = ?', (token,), one=True)
    if not row:
        return render_template('error.html', message='Link non valido.'), 404

    now = datetime.utcnow()
    expiry = parse_dt(row['expiry_date'])
    base_date = expiry if expiry and expiry > now else now
    new_expiry = base_date + timedelta(days=365)

    execute(
        'UPDATE activation_codes SET status = ?, expiry_date = ?, renewed_at = ? WHERE id = ?',
        ('active', new_expiry.isoformat(timespec='seconds'), now.isoformat(timespec='seconds'), row['id']),
        commit=True
    )
    return redirect(f"https://latazzacheparlalove2026.app-me.it/collecting?love_token={token}")


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        if username == "admin" and (password == "love26" or check_password_hash(app.config['ADMIN_PASSWORD_HASH'], password)):
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        flash('Credenziali non valide.')
    return render_template('admin_login.html')


@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('admin_login'))


@app.route('/admin')
@login_required
def admin_dashboard():
    codes = execute('SELECT * FROM activation_codes ORDER BY id DESC LIMIT 50')
    messages = execute('SELECT * FROM messages ORDER BY variant, sort_order, id')
    return render_template(
        'admin_dashboard.html',
        codes=codes,
        messages=messages,
        variants_enabled=get_setting('variants_enabled', '1') == '1',
        renewal_price_text=get_setting('renewal_price_text', '€9,90 / anno'),
        brand_name=get_setting('brand_name', 'Love Mug')
    )


@app.route('/admin/settings', methods=['POST'])
@login_required
def admin_settings():
    variants_enabled = '1' if request.form.get('variants_enabled') == 'on' else '0'
    renewal_price_text = request.form.get('renewal_price_text', '€9,90 / anno').strip()
    brand_name = request.form.get('brand_name', 'Love Mug').strip() or 'Love Mug'
    set_setting('variants_enabled', variants_enabled)
    set_setting('renewal_price_text', renewal_price_text)
    set_setting('brand_name', brand_name)
    flash('Impostazioni salvate.')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/codes/generate', methods=['POST'])
@login_required
def generate_codes():
    qty = int(request.form.get('qty', '10') or 10)
    qty = max(1, min(qty, 200))
    db = get_db()
    alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    created = 0
    while created < qty:
        code = 'LOVE-' + ''.join(secrets.choice(alphabet) for _ in range(6))
        existing = execute('SELECT id FROM activation_codes WHERE code = ?', (code,), one=True)
        if existing:
            continue
        db.execute('INSERT INTO activation_codes (code, status, created_at) VALUES (?, ?, ?)', (code, 'unused', now_iso()))
        created += 1
    db.commit()
    flash(f'Creati {created} nuovi codici.')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/messages/add', methods=['POST'])
@login_required
def add_message():
    variant = request.form.get('variant', 'neutro')
    body = request.form.get('body', '').strip()
    if variant not in {'lei', 'lui', 'neutro'} or not body:
        flash('Messaggio non valido.')
        return redirect(url_for('admin_dashboard'))
    current_max = execute('SELECT COALESCE(MAX(sort_order), 0) AS max_order FROM messages WHERE variant = ?', (variant,), one=True)
    sort_order = (current_max['max_order'] or 0) + 1
    execute(
        'INSERT INTO messages (variant, body, is_active, sort_order) VALUES (?, ?, 1, ?)',
        (variant, body, sort_order),
        commit=True
    )
    flash('Messaggio aggiunto.')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/messages/<int:message_id>/toggle', methods=['POST'])
@login_required
def toggle_message(message_id):
    row = execute('SELECT is_active FROM messages WHERE id = ?', (message_id,), one=True)
    if row:
        new_status = 0 if row['is_active'] else 1
        execute('UPDATE messages SET is_active = ? WHERE id = ?', (new_status, message_id), commit=True)
        flash('Messaggio aggiornato.')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/codes/<int:code_id>/expire', methods=['POST'])
@login_required
def expire_code(code_id):
    execute('UPDATE activation_codes SET status = ? WHERE id = ?', ('expired', code_id), commit=True)
    flash('Codice impostato come scaduto.')
    return redirect(url_for('admin_dashboard'))

if __name__ == "__main__":
    app.run(debug=True, port=5001)
