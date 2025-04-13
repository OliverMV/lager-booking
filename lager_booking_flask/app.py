from flask import Flask, render_template, request, redirect, url_for, session
from tinydb import TinyDB, Query
import os
from werkzeug.utils import secure_filename

# === Flask setup ===
app = Flask(__name__)
app.secret_key = 'secret_key_for_session_management'

# === Brugerkonti ===
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'password123'

booking_users = {
    'bruger1': 'kode123',
    'bruger2': 'hemmelig'
}

# === TinyDB setup ===
DB_PATH = os.path.join('data', 'tools_db.json')
os.makedirs('data', exist_ok=True)
db = TinyDB(DB_PATH)
Tool = Query()

# === Upload-konfiguration ===
UPLOAD_FOLDER = os.path.join('static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# === Hjælpefunktioner ===
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_tools():
    return db.all()

def save_tool(tool):
    db.upsert(tool, Tool.name == tool['name'])

def is_logged_in():
    return session.get('role') == 'admin'

def is_user_logged_in():
    return session.get('role') == 'user'

@app.context_processor
def inject_logged_in_status():
    return dict(
        is_logged_in=is_logged_in,
        is_user_logged_in=is_user_logged_in,
        session=session
    )

# === Forside (bruger) ===
@app.route('/')
def index():
    if not is_user_logged_in():
        return redirect(url_for('login'))
    tools = get_tools()
    bookings = [t for t in tools if t['status'] == 'booked']
    error_message = session.pop('error_message', None)
    return render_template('index.html', tools=tools, bookings=bookings, error=error_message)

# === Booking værktøj ===
@app.route('/book', methods=['POST'])
def book_tool():
    if not is_user_logged_in():
        return redirect(url_for('login'))

    name = request.form['name']
    tool_name = request.form['tool']
    start_date = request.form['start_date']
    end_date = request.form['end_date']

    if not name or not start_date or not end_date:
        session['error_message'] = "Udfyld venligst alle felter."
        return redirect(url_for('index'))

    tools = get_tools()
    for tool in tools:
        if tool['name'] == tool_name and tool['status'] == 'available':
            tool['status'] = 'booked'
            tool['booked_by'] = name
            tool['start_date'] = start_date
            tool['end_date'] = end_date
            tool['booking_time'] = f"{start_date} til {end_date}"
            save_tool(tool)
            break

    return redirect(url_for('index'))

# === Returnering af værktøj ===
@app.route('/return_tool', methods=['POST'])
def return_tool():
    if not (is_user_logged_in() or is_logged_in()):
        return redirect(url_for('login'))

    tool_name = request.form['tool_name']
    tools = get_tools()

    for tool in tools:
        if tool['name'] == tool_name and tool['status'] == 'booked':
            tool['status'] = 'available'
            tool['booked_by'] = None
            tool['start_date'] = None
            tool['end_date'] = None
            tool['booking_time'] = None
            save_tool(tool)
            break

    return redirect(url_for('index'))

# === Admin-side ===
@app.route('/admin')
def admin():
    if not is_logged_in():
        return redirect(url_for('login'))
    tools = get_tools()
    error_message = session.pop('error_message', None)
    return render_template('admin.html', tools=tools, error=error_message)

@app.route('/add_tool', methods=['POST'])
def add_tool():
    if not is_logged_in():
        return redirect(url_for('login'))

    tool_name = request.form['tool_name']
    file = request.files.get('tool_image')

    for tool in get_tools():
        if tool['name'].lower() == tool_name.lower():
            session['error_message'] = "Værktøjet findes allerede."
            return redirect(url_for('admin'))

    filename = None
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    new_tool = {
        'name': tool_name,
        'status': 'available',
        'booked_by': None,
        'booking_time': None,
        'start_date': None,
        'end_date': None,
        'image': filename
    }

    save_tool(new_tool)
    return redirect(url_for('admin'))

@app.route('/remove_tool/<string:tool_name>', methods=['POST'])
def remove_tool(tool_name):
    if not is_logged_in():
        return redirect(url_for('login'))

    db.remove(Tool.name == tool_name)
    return redirect(url_for('admin'))

# === Fælles login for både admin og brugere ===
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['logged_in'] = True
            session['role'] = 'admin'
            session['username'] = username
            return redirect(url_for('admin'))

        elif username in booking_users and booking_users[username] == password:
            session['user_logged_in'] = True
            session['role'] = 'user'
            session['username'] = username
            return redirect(url_for('index'))

        else:
            session['error_message'] = "Forkert brugernavn eller adgangskode"
            return redirect(url_for('login'))

    error_message = session.pop('error_message', None)
    return render_template('login.html', error=error_message,
                           header_text="LOGIN",
                           welcome_text="Velkommen til Lager Booking",
                           form_action=url_for('login'))

# === Logout ===
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# === Start server ===
if __name__ == '__main__':
    app.run(debug=True)
