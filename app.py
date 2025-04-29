from sqlalchemy.exc import IntegrityError
# app.py
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import requests
import os
from forms import AppointmentForm 
from datetime import datetime

# ----------------------
# Initialization
# ----------------------
def calculate_age(dob):
    if not dob:
        return 'N/A'
    today = datetime.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

app = Flask(__name__)

app.add_template_global(calculate_age, name='calculate_age')





app.config.update({
    'SECRET_KEY': os.environ.get('SECRET_KEY', os.urandom(24)),
    'SQLALCHEMY_DATABASE_URI': os.environ.get('DATABASE_URL', 'sqlite:///health.db'),
    'SQLALCHEMY_TRACK_MODIFICATIONS': False,
    'CLINICAL_API_KEY': os.environ.get('CLINICAL_API_KEY', ''),
    'ENCRYPTION_KEY': os.environ.get('ENCRYPTION_KEY', 'supersecretencryptionkey123'),
    'RATE_LIMITS': "200/day;50/hour"
})

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
migrate = Migrate(app, db)
limiter = Limiter(app=app, key_func=get_remote_address, default_limits=["200 per day", "50 per hour"])



# ----------------------
# Flask-Login Setup
# ----------------------
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
# ----------------------
# Database Models (Enhanced)
# ----------------------
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='doctor', nullable=False)
    last_login = db.Column(db.DateTime)
    active = db.Column(db.Boolean, default=True)
    audit_logs = db.relationship('AuditLog', backref='user', lazy=True)

class Client(db.Model):
    __tablename__ = 'clients'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    dob = db.Column(db.Date, nullable=False)
    contact = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    enrollments = db.relationship('Enrollment', backref='client', lazy=True)
    medical_records = db.relationship('MedicalRecord', backref='client', lazy=True)
    appointments = db.relationship('Appointment', backref='client', lazy=True) # scheduled/completed/cancelled


class PendingAction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    action_type = db.Column(db.String(50))  # 'approval', 'followup', 'review'
    related_id = db.Column(db.Integer)  # ID of related record
    description = db.Column(db.String(200))
    due_date = db.Column(db.DateTime)
    completed = db.Column(db.Boolean, default=False)
class Appointment(db.Model):
    __tablename__ = 'appointments'
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    notes = db.Column(db.Text)
    status = db.Column(db.String(20), default='scheduled')
    is_urgent = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship for easy access
    doctor = db.relationship('User', backref='appointments')
class Program(db.Model):
    __tablename__ = 'programs'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    code = db.Column(db.String(10))
    enrollments = db.relationship('Enrollment', backref='program', lazy=True)

class Enrollment(db.Model):
    __tablename__ = 'enrollments'
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    program_id = db.Column(db.Integer, db.ForeignKey('programs.id'), nullable=False)
    enrolled_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='active')

class MedicalRecord(db.Model):
    __tablename__ = 'medical_records'
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    diagnosis = db.Column(db.Text, nullable=False)
    prescriptions = db.Column(db.Text)
    visit_date = db.Column(db.DateTime, default=datetime.utcnow)
    doctor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    details = db.Column(db.Text)

class Medication(db.Model):
    __tablename__ = 'medications'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    interactions = db.Column(db.JSON)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    completed = db.Column(db.Boolean, default=False)

# ----------------------
# Security Enhancements
# ----------------------@app.route('/dashboard')
def dashboard():
    # Appointment stats
    upcoming_count = Appointment.query.filter(
        Appointment.date >= datetime.now(),
        Appointment.status == 'scheduled'
    ).count()
    
    urgent_count = Appointment.query.filter(
        Appointment.is_urgent == True,
        Appointment.status == 'scheduled'
    ).count()
    
    # Pending actions
    pending_total = PendingAction.query.filter_by(completed=False).count()
    pending_approvals = PendingAction.query.filter_by(
        action_type='approval', 
        completed=False
    ).count()
    
    return render_template('dashboard.html',
                         appointment_count=upcoming_count,
                         urgent_count=urgent_count,
                         pending_actions=pending_total,
                         pending_approvals=pending_approvals)
def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if current_user.role != role:
                log_action('UNAUTHORIZED_ACCESS')(lambda: None)()
                flash('Unauthorized access', 'danger')
                return redirect(url_for('home'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def log_action(action):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            result = f(*args, **kwargs)
            log = AuditLog(
                user_id=current_user.id,
                action=action,
                details=f"{request.method} {request.path}"
            )
            db.session.add(log)
            db.session.commit()
            return result
        return decorated_function
    return decorator

# ----------------------
# Clinical Features
# ----------------------
def get_clinical_guidelines(diagnosis):
    try:
        response = requests.post(
            'https://clinical-api.example.com/v3/analysis',
            json={'symptoms': diagnosis},
            headers={'Authorization': f'Bearer {app.config["CLINICAL_API_KEY"]}'},
            timeout=5
        )
        return response.json().get('recommendations', [])
    except Exception as e:
        return []

def check_medication_interactions(medications):
    return Medication.query.filter(Medication.name.in_(medications)).all()

# ----------------------
# Updated Routes
# ----------------------
@app.route('/telemedicine/<int:client_id>')
@login_required
@log_action('TELECONSULTATION')
def telemedicine(client_id):
    client = Client.query.get_or_404(client_id)
    return render_template('telemedicine.html', client=client)

@app.route('/api/clinical-guidelines', methods=['POST'])
@login_required
def clinical_guidelines_api():
    data = request.json
    recommendations = get_clinical_guidelines(data.get('diagnosis'))
    return jsonify({'recommendations': recommendations})

@app.route('/api/check-interactions', methods=['POST'])
@login_required
def check_interactions_api():
    medications = request.json.get('medications', [])
    interactions = check_medication_interactions(medications)
    return jsonify([{'name': m.name, 'interactions': m.interactions} for m in interactions])

@app.route('/emergency-mode', methods=['POST'])
@role_required('admin')
@log_action('EMERGENCY_MODE')
def emergency_mode():
    app.config['MAINTENANCE_MODE'] = not app.config.get('MAINTENANCE_MODE', False)
    status = "activated" if app.config['MAINTENANCE_MODE'] else "deactivated"
    return jsonify({'status': f'Emergency mode {status}'})

# ----------------------
# Error Handlers
# ----------------------
@app.errorhandler(404)
def not_found(error):
    return render_template('error.html', code=404, message="Resource not found"), 404

@app.errorhandler(403)
def forbidden(error):
    return render_template('error.html', code=403, message="Access forbidden"), 403

@app.errorhandler(500)
def internal_error(error):
    return render_template('error.html', code=500, message="Internal server error"), 500

# ----------------------
# Existing Routes Remain Unchanged Below This Point
# ----------------------
# # Routes
# # ----------------------
@app.route('/')
@login_required
def home():
    recent_enrollments = Enrollment.query.order_by(
        Enrollment.enrolled_at.desc()
    ).limit(5).all()
    
    client_count = Client.query.count()
    program_count = Program.query.count()  # Add this
    
    return render_template('dashboard.html',
                         recent_enrollments=recent_enrollments,
                         client_count=client_count,
                         program_count=program_count)  # Pass new variable

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            user.last_login = datetime.utcnow()
            db.session.commit()
            return redirect(url_for('home'))
        
        flash('Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))
@app.route('/appointments')
def appointments():
    # Get upcoming appointments
    upcoming = Appointment.query.filter(
        Appointment.date >= datetime.now(),
        Appointment.status == 'scheduled'
    ).order_by(Appointment.date.asc()).all()
    
    # Get pending actions
    pending = PendingAction.query.filter_by(completed=False).all()
    
    return render_template('appointments.html',
                         upcoming_appointments=upcoming,
                         pending_actions=pending)

@app.route('/create_appointment', methods=['GET', 'POST'])
def create_appointment():
    form = AppointmentForm()
    
    if form.validate_on_submit():
        new_appointment = Appointment(
            patient_id=form.patient_id.data,
            date=form.date.data,
            notes=form.notes.data,
            is_urgent=form.is_urgent.data
        )
        db.session.add(new_appointment)
        db.session.commit()
        return redirect(url_for('appointments'))
    
    return render_template('create_appointment.html', form=form)

@app.route('/complete_action/<int:action_id>')
def complete_action(action_id):
    action = PendingAction.query.get_or_404(action_id)
    action.completed = True
    db.session.commit()
    return redirect(url_for('appointments'))
@app.route('/create-program', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def create_program():
    if request.method == 'POST':
        try:
            program = Program(
                name=request.form['name'],
                description=request.form['description'],
                code=request.form['code']
            )
            db.session.add(program)
            db.session.commit()
            flash('Program created successfully', 'success')
        except:
            db.session.rollback()
            flash('Error creating program', 'danger')
    return render_template('create_program.html')

@app.route('/register-client', methods=['GET', 'POST'])
@login_required
def register_client():
    if request.method == 'POST':
        try:
            client = Client(
                name=request.form['name'],
                dob=datetime.strptime(request.form['dob'], '%Y-%m-%d'),
                contact=request.form['contact']
            )
            db.session.add(client)
            db.session.commit()
            flash('Client registered successfully', 'success')
        except:
            db.session.rollback()
            flash('Error registering client', 'danger')
    return render_template('register_client.html')

@app.route('/enroll', methods=['GET', 'POST'])
@login_required
def enroll_client():
    if request.method == 'POST':
        try:
            enrollment = Enrollment(
                client_id=request.form['client'],
                program_id=request.form['program']
            )
            db.session.add(enrollment)
            db.session.commit()
            flash('Enrollment successful', 'success')
        except IntegrityError as e:
            db.session.rollback()
            flash('Error processing enrollment: {}'.format(e), 'danger')
        except Exception as e:
            db.session.rollback()
            flash('An unexpected error occurred: {}'.format(e), 'danger')
    
    clients = Client.query.all()
    programs = Program.query.all()
    return render_template('enroll.html', 
                         clients=clients, 
                         programs=programs)@app.route('/search', methods=['GET', 'POST'])
@login_required
def search_clients():
    clients = []
    if request.method == 'POST':
        search_term = f"%{request.form['search']}%"
        clients = Client.query.filter(Client.name.like(search_term)).all()
    return render_template('search.html', clients=clients)

@app.route('/client/<int:client_id>')
@login_required
def client_profile(client_id):
    client = Client.query.get_or_404(client_id)
    return render_template('client_profile.html', client=client)

@app.route('/medical-record/<int:client_id>', methods=['GET', 'POST'])
@login_required
def medical_record(client_id):
    client = Client.query.get_or_404(client_id)
    if request.method == 'POST':
        try:
            record = MedicalRecord(
                client_id=client_id,
                diagnosis=request.form['diagnosis'],
                prescriptions=request.form['prescriptions'],
                doctor_id=current_user.id
            )
            db.session.add(record)
            db.session.commit()
            flash('Medical record added', 'success')
        except:
            db.session.rollback()
            flash('Error saving record', 'danger')
    return render_template('medical_record.html', client=client)

@app.route('/api/client/<int:client_id>')
@login_required
def api_client(client_id):
    client = Client.query.get_or_404(client_id)
    return jsonify({
        'id': client.id,
        'name': client.name,
        'dob': client.dob.isoformat(),
        'contact': client.contact,
        'enrollments': [{
            'program': enrollment.program.name,
            'status': enrollment.status,
            'enrolled_at': enrollment.enrolled_at.isoformat()
        } for enrollment in client.enrollments],
        'medical_history': [{
            'diagnosis': record.diagnosis,
            'prescriptions': record.prescriptions,
            'visit_date': record.visit_date.isoformat()
        } for record in client.medical_records]
    })

# ----------------------
# Initialization
# ----------------------
@app.shell_context_processor
def make_shell_context():
    return {
        'db': db,
        'User': User,
        'Client': Client,
        'Program': Program,
        'Enrollment': Enrollment,
        'MedicalRecord': MedicalRecord
    }

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Create default admin with encrypted password
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                password=generate_password_hash(os.environ.get('ADMIN_PWD', 'admin123')),
                role='admin'
            )
            db.session.add(admin)
            db.session.commit()
        # Create default doctor user
        if not User.query.filter_by(username='doctor').first():
            doctor = User(
                username='doctor',
                password=generate_password_hash(os.environ.get('DOCTOR_PWD', 'password123')),
                role='doctor'
            )
            db.session.add(doctor)
            db.session.commit()
    app.run(debug=os.environ.get('FLASK_DEBUG', False))