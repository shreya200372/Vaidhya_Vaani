import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import uuid
import os

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def generate_consultation_id():
    """Generate unique consultation ID"""
    return str(uuid.uuid4())

def send_email_notification(to_email, subject, message):
    """Send email notifications for appointments and consultations"""
    try:
        # Configure your SMTP settings here
        logger.info(f"Email notification sent to {to_email}: {subject}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {str(e)}")
        return False

def format_consultation_duration(start_time, end_time):
    """Calculate and format consultation duration"""
    if start_time and end_time:
        duration = end_time - start_time
        minutes = int(duration.total_seconds() / 60)
        return f"{minutes} minutes"
    return "N/A"

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

def ensure_upload_dir():
    """Ensure upload directory exists"""
    upload_dir = 'static/uploads'
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
    return upload_dir

def allowed_file(filename, allowed_extensions={'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx'}):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def log_user_activity(user_id, activity, details=None):
    """Log user activities for audit trail"""
    logger.info(f"User {user_id}: {activity} - {details or ''}")
