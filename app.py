from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import uuid
import os
import json
import logging

# Create required directories
def ensure_directories():
    dirs = ['static/uploads', 'logs']
    for directory in dirs:
        os.makedirs(directory, exist_ok=True)
        print(f"✅ Ensured directory: {directory}")

ensure_directories()

# Initialize Flask app
app = Flask(__name__)

# Simple, working configuration
app.config['SECRET_KEY'] = 'dev-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///telemedicine.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# Initialize extensions
db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Simple logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Utility functions - ADD THESE BEFORE DATABASE MODELS
def generate_consultation_id():
    """Generate unique consultation ID"""
    return str(uuid.uuid4())

def validate_appointment_time(scheduled_time):
    """Validate if appointment time is in the future and within business hours"""
    now = datetime.utcnow()
    if scheduled_time <= now:
        return False, "Appointment time must be in the future"
    
    # Check if time is within business hours (9 AM - 6 PM)
    hour = scheduled_time.hour
    if hour < 9 or hour >= 18:
        return False, "Appointments are only available between 9 AM and 6 PM"
    
    return True, "Valid appointment time"

# Application Metadata
APP_NAME = "Vaidhya-vani"
APP_TAGLINE = "Voice of Healing"
APP_VERSION = "1.0.0"

@app.context_processor
def inject_app_info():
    return {
        'app_name': APP_NAME,
        'app_tagline': APP_TAGLINE,
        'app_version': APP_VERSION
    }

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    user_type = db.Column(db.String(20), nullable=False)  # 'patient' or 'doctor'
    full_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_online = db.Column(db.Boolean, default=False)
    socket_id = db.Column(db.String(100))
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)

class Doctor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    specialty = db.Column(db.String(100), nullable=False)
    license_number = db.Column(db.String(50))
    experience_years = db.Column(db.Integer)
    consultation_fee = db.Column(db.Float, default=0.0)
    rating = db.Column(db.Float, default=0.0)
    total_consultations = db.Column(db.Integer, default=0)
    is_available = db.Column(db.Boolean, default=True)
    bio = db.Column(db.Text)
    user = db.relationship('User', backref=db.backref('doctor_profile', uselist=False))

class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date_of_birth = db.Column(db.Date)
    gender = db.Column(db.String(10))
    emergency_contact = db.Column(db.String(20))
    medical_history = db.Column(db.Text)
    blood_type = db.Column(db.String(5))
    allergies = db.Column(db.Text)
    user = db.relationship('User', backref=db.backref('patient_profile', uselist=False))

class Consultation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)
    consultation_id = db.Column(db.String(36), unique=True, default=generate_consultation_id)
    status = db.Column(db.String(20), default='requested')  # requested, active, completed, cancelled
    scheduled_time = db.Column(db.DateTime)
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    symptoms = db.Column(db.Text)
    diagnosis = db.Column(db.Text)
    prescription = db.Column(db.Text)
    notes = db.Column(db.Text)
    rating = db.Column(db.Integer)  # 1-5 rating from patient
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    patient = db.relationship('Patient', backref='consultations')
    doctor = db.relationship('Doctor', backref='consultations')

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    consultation_id = db.Column(db.Integer, db.ForeignKey('consultation.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    message_type = db.Column(db.String(20), default='text')  # text, image, file
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    consultation = db.relationship('Consultation', backref='messages')
    sender = db.relationship('User', backref='sent_messages')

class MedicalRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    consultation_id = db.Column(db.Integer, db.ForeignKey('consultation.id'))
    record_type = db.Column(db.String(50))  # 'prescription', 'lab_report', 'image', etc.
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    file_path = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    patient = db.relationship('Patient', backref='medical_records')
    consultation = db.relationship('Consultation', backref='medical_records')

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login_page():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/register')
def register_page():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    return render_template('dashboard.html')

@app.route('/consultation/<consultation_id>')
def consultation_room(consultation_id):
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    
    # Verify user has access to this consultation
    if session['user_type'] == 'patient':
        patient = Patient.query.filter_by(user_id=session['user_id']).first()
        consultation = Consultation.query.filter_by(
            consultation_id=consultation_id,
            patient_id=patient.id
        ).first()
    else:
        doctor = Doctor.query.filter_by(user_id=session['user_id']).first()
        consultation = Consultation.query.filter_by(
            consultation_id=consultation_id,
            doctor_id=doctor.id
        ).first()
    
    if not consultation:
        flash('Consultation not found or access denied', 'error')
        return redirect(url_for('dashboard'))
    
    return render_template('consultation.html', consultation_id=consultation_id)

# API Routes
@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['username', 'email', 'password', 'user_type', 'full_name']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        # Check if user already exists
        if User.query.filter_by(username=data['username']).first():
            return jsonify({'error': 'Username already exists'}), 400
        
        if User.query.filter_by(email=data['email']).first():
            return jsonify({'error': 'Email already exists'}), 400
        
        # Create new user
        user = User(
            username=data['username'],
            email=data['email'],
            password_hash=generate_password_hash(data['password']),
            user_type=data['user_type'],
            full_name=data['full_name'],
            phone=data.get('phone', '')
        )
        
        db.session.add(user)
        db.session.commit()
        
        # Create profile based on user type
        if data['user_type'] == 'doctor':
            doctor = Doctor(
                user_id=user.id,
                specialty=data.get('specialty', ''),
                license_number=data.get('license_number', ''),
                experience_years=data.get('experience_years', 0),
                consultation_fee=data.get('consultation_fee', 0.0),
                bio=data.get('bio', '')
            )
            db.session.add(doctor)
        else:
            patient = Patient(
                user_id=user.id,
                gender=data.get('gender', ''),
                emergency_contact=data.get('emergency_contact', ''),
                medical_history=data.get('medical_history', ''),
                blood_type=data.get('blood_type', ''),
                allergies=data.get('allergies', '')
            )
            db.session.add(patient)
        
        db.session.commit()
        logger.info(f"New user registered: {user.username} ({user.user_type})")
        
        return jsonify({'message': 'User registered successfully', 'user_id': user.id}), 201
        
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return jsonify({'error': 'Registration failed'}), 500

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        user = User.query.filter_by(username=data['username']).first()
        
        if user and check_password_hash(user.password_hash, data['password']):
            session['user_id'] = user.id
            session['user_type'] = user.user_type
            session['username'] = user.username
            session.permanent = True
            
            # Update online status
            user.is_online = True
            user.last_seen = datetime.utcnow()
            db.session.commit()
            
            logger.info(f"User logged in: {user.username}")
            
            return jsonify({
                'message': 'Login successful',
                'user_id': user.id,
                'user_type': user.user_type,
                'username': user.username
            }), 200
        
        return jsonify({'error': 'Invalid credentials'}), 401
        
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({'error': 'Login failed'}), 500

@app.route('/api/logout', methods=['POST'])
def logout():
    try:
        if 'user_id' in session:
            user = User.query.get(session['user_id'])
            if user:
                user.is_online = False
                user.socket_id = None
                user.last_seen = datetime.utcnow()
                db.session.commit()
                logger.info(f"User logged out: {user.username}")
        
        session.clear()
        return jsonify({'message': 'Logout successful'}), 200
        
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        return jsonify({'error': 'Logout failed'}), 500

@app.route('/api/available-doctors')
def get_available_doctors():
    try:
        doctors = db.session.query(Doctor, User).join(User).filter(
            Doctor.is_available == True,
            User.is_online == True
        ).all()
        
        doctor_list = []
        for doctor, user in doctors:
            doctor_list.append({
                'id': doctor.id,
                'name': user.full_name,
                'specialty': doctor.specialty,
                'experience_years': doctor.experience_years,
                'consultation_fee': doctor.consultation_fee,
                'rating': doctor.rating,
                'total_consultations': doctor.total_consultations,
                'bio': doctor.bio
            })
        
        return jsonify(doctor_list)
        
    except Exception as e:
        logger.error(f"Error loading doctors: {str(e)}")
        return jsonify({'error': 'Failed to load doctors'}), 500

@app.route('/api/request-consultation', methods=['POST'])
def request_consultation():
    try:
        if 'user_id' not in session or session['user_type'] != 'patient':
            return jsonify({'error': 'Unauthorized'}), 401
        
        data = request.get_json()
        
        # Get patient profile
        patient = Patient.query.filter_by(user_id=session['user_id']).first()
        if not patient:
            return jsonify({'error': 'Patient profile not found'}), 404
        
        # Create consultation request
        consultation = Consultation(
            patient_id=patient.id,
            doctor_id=data['doctor_id'],
            symptoms=data.get('symptoms', ''),
            scheduled_time=datetime.utcnow() + timedelta(minutes=5)
        )
        
        db.session.add(consultation)
        db.session.commit()
        
        # Notify doctor via Socket.IO
        doctor = Doctor.query.get(data['doctor_id'])
        if doctor and doctor.user.socket_id:
            socketio.emit('consultation_request', {
                'consultation_id': consultation.consultation_id,
                'patient_name': patient.user.full_name,
                'symptoms': consultation.symptoms
            }, room=doctor.user.socket_id)
        
        logger.info(f"Consultation requested: {consultation.consultation_id}")
        
        return jsonify({
            'message': 'Consultation requested successfully',
            'consultation_id': consultation.consultation_id
        }), 201
        
    except Exception as e:
        logger.error(f"Error requesting consultation: {str(e)}")
        return jsonify({'error': 'Failed to request consultation'}), 500

@app.route('/api/consultations')
def get_consultations():
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        
        if session['user_type'] == 'patient':
            patient = Patient.query.filter_by(user_id=session['user_id']).first()
            consultations = Consultation.query.filter_by(patient_id=patient.id).order_by(Consultation.created_at.desc()).all()
        else:
            doctor = Doctor.query.filter_by(user_id=session['user_id']).first()
            consultations = Consultation.query.filter_by(doctor_id=doctor.id).order_by(Consultation.created_at.desc()).all()
        
        consultation_list = []
        for consultation in consultations:
            consultation_list.append({
                'id': consultation.id,
                'consultation_id': consultation.consultation_id,
                'patient_name': consultation.patient.user.full_name,
                'doctor_name': consultation.doctor.user.full_name,
                'status': consultation.status,
                'scheduled_time': consultation.scheduled_time.isoformat() if consultation.scheduled_time else None,
                'symptoms': consultation.symptoms,
                'created_at': consultation.created_at.isoformat()
            })
        
        return jsonify(consultation_list)
        
    except Exception as e:
        logger.error(f"Error loading consultations: {str(e)}")
        return jsonify({'error': 'Failed to load consultations'}), 500

# Socket.IO Events
@socketio.on('connect')
def handle_connect():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            user.socket_id = request.sid
            user.is_online = True
            user.last_seen = datetime.utcnow()
            db.session.commit()
        join_room(f"user_{session['user_id']}")
        logger.info(f"User connected: {session.get('username', 'Unknown')}")

@socketio.on('disconnect')
def handle_disconnect():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            user.socket_id = None
            user.is_online = False
            user.last_seen = datetime.utcnow()
            db.session.commit()
        logger.info(f"User disconnected: {session.get('username', 'Unknown')}")

@socketio.on('join_consultation')
def handle_join_consultation(data):
    consultation_id = data['consultation_id']
    join_room(f"consultation_{consultation_id}")
    
    # Update consultation status to active if both parties have joined
    consultation = Consultation.query.filter_by(consultation_id=consultation_id).first()
    if consultation and consultation.status == 'requested':
        consultation.status = 'active'
        consultation.start_time = datetime.utcnow()
        db.session.commit()
        
        emit('consultation_started', {
            'consultation_id': consultation_id,
            'message': 'Consultation has started'
        }, room=f"consultation_{consultation_id}")
        
        logger.info(f"Consultation started: {consultation_id}")

@socketio.on('send_message')
def handle_message(data):
    try:
        consultation_id = data['consultation_id']
        message_text = data['message']
        
        consultation = Consultation.query.filter_by(consultation_id=consultation_id).first()
        if not consultation:
            return
        
        # Save message to database
        message = Message(
            consultation_id=consultation.id,
            sender_id=session['user_id'],
            message=message_text
        )
        db.session.add(message)
        db.session.commit()
        
        # Broadcast message to consultation room
        emit('receive_message', {
            'message': message_text,
            'sender': session['username'],
            'timestamp': message.timestamp.isoformat()
        }, room=f"consultation_{consultation_id}")
        
    except Exception as e:
        logger.error(f"Error sending message: {str(e)}")

@socketio.on('webrtc_offer')
def handle_webrtc_offer(data):
    consultation_id = data['consultation_id']
    emit('webrtc_offer', data, room=f"consultation_{consultation_id}", include_self=False)

@socketio.on('webrtc_answer')
def handle_webrtc_answer(data):
    consultation_id = data['consultation_id']
    emit('webrtc_answer', data, room=f"consultation_{consultation_id}", include_self=False)

@socketio.on('webrtc_ice_candidate')
def handle_ice_candidate(data):
    consultation_id = data['consultation_id']
    emit('webrtc_ice_candidate', data, room=f"consultation_{consultation_id}", include_self=False)

@socketio.on('end_consultation')
def handle_end_consultation(data):
    try:
        consultation_id = data['consultation_id']
        
        # Update consultation status
        consultation = Consultation.query.filter_by(consultation_id=consultation_id).first()
        if consultation:
            consultation.status = 'completed'
            consultation.end_time = datetime.utcnow()
            if 'diagnosis' in data:
                consultation.diagnosis = data['diagnosis']
            if 'prescription' in data:
                consultation.prescription = data['prescription']
            if 'notes' in data:
                consultation.notes = data['notes']
            
            # Update doctor's consultation count
            consultation.doctor.total_consultations += 1
            db.session.commit()
            
            logger.info(f"Consultation ended: {consultation_id}")
        
        emit('consultation_ended', {
            'consultation_id': consultation_id,
            'message': 'Consultation has ended'
        }, room=f"consultation_{consultation_id}")
        
    except Exception as e:
        logger.error(f"Error ending consultation: {str(e)}")

@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        logger.info("✅Database tables created successfully!")
    
    print("🏥 Starting Vaidhya-vani - Voice of Healing")
    print("🚀 Server available at: http://localhost:5000")
    print("📋 Features: Video consultations, Real-time chat, Medical records")
    print("⚡ Press Ctrl+C to stop the server")
    
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
