from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from sqlalchemy import Enum, UniqueConstraint, ForeignKey, Index, func, text
from sqlalchemy.orm import relationship, backref

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Enum definitions for better type safety
class UserRole(Enum):
    DOCTOR = 'doctor'
    ADMIN = 'admin'
    STAFF = 'staff'

class AppointmentStatus(Enum):
    SCHEDULED = 'scheduled'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'

class ActionType(Enum):
    APPROVAL = 'approval'
    FOLLOWUP = 'followup'
    REVIEW = 'review'

class EnrollmentStatus(Enum):
    ACTIVE = 'active'
    COMPLETED = 'completed'
    TERMINATED = 'terminated'

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.Enum('doctor', 'admin', 'staff', name='user_role'), default='doctor', nullable=False)
    last_login = db.Column(db.DateTime)
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, server_default=func.now())
    
    # Relationships
    appointments = relationship('Appointment', back_populates='doctor')
    audit_logs = relationship('AuditLog', back_populates='user')
    pending_actions = relationship('PendingAction', back_populates='user')
    
    def __repr__(self):
        return f'<User {self.username} ({self.role.value})>'

class Client(db.Model):
    __tablename__ = 'clients'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    dob = db.Column(db.Date, nullable=False)
    contact = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120), unique=True)
    created_at = db.Column(db.DateTime, server_default=func.now())
    
    # Relationships
    enrollments = relationship('Enrollment', back_populates='client', 
                              cascade='all, delete-orphan')
    medical_records = relationship('MedicalRecord', back_populates='client',
                                  cascade='all, delete-orphan')
    appointments = relationship('Appointment', back_populates='client')
    
    __table_args__ = (
        Index('ix_clients_dob', 'dob'),
        UniqueConstraint('email', name='uq_clients_email'),
    )
    
    def __repr__(self):
        return f'<Client {self.name}>'

class PendingAction(db.Model):
    __tablename__ = 'pending_actions'
    id = db.Column(db.Integer, primary_key=True)
    action_type = db.Column(db.Enum('action1', 'action2', 'action3', name='action_type'), nullable=False)
    related_id = db.Column(db.Integer, nullable=False)
    description = db.Column(db.String(200))
    due_date = db.Column(db.DateTime, index=True)
    completed = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, server_default=func.now())
    
    # Relationships
    user_id = db.Column(db.Integer, ForeignKey('users.id'), nullable=False)
    user = relationship('User', back_populates='pending_actions')
    
    __table_args__ = (
        Index('ix_pending_action_completed', 'completed'),
        Index('ix_pending_action_type_completed', 'action_type', 'completed'),
    )
    
    def __repr__(self):
        return f'<PendingAction {self.action_type.value} {self.related_id}>'

class Appointment(db.Model):
    __tablename__ = 'appointments'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=False, index=True)
    notes = db.Column(db.Text)
    status = db.Column(db.Enum('scheduled', 'cancelled', 'rescheduled', name='appointment_status'), default='scheduled')
    is_urgent = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime, server_default=func.now())
    
    # Foreign Keys
    client_id = db.Column(db.Integer, ForeignKey('clients.id'), nullable=False)
    doctor_id = db.Column(db.Integer, ForeignKey('users.id'), nullable=False)
    
    # Relationships
    client = relationship('Client', back_populates='appointments')
    doctor = relationship('User', back_populates='appointments')
    
    __table_args__ = (
        Index('ix_appointment_date_status', 'date', 'status'),
        Index('ix_appointment_urgent_status', 'is_urgent', 'status'),
    )
    
    def __repr__(self):
        return f'<Appointment {self.date} ({self.status.value})>'

class Program(db.Model):
    __tablename__ = 'programs'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    code = db.Column(db.String(10), unique=True)
    
    enrollments = relationship('Enrollment', back_populates='program')
    
    def __repr__(self):
        return f'<Program {self.name}>'

class Enrollment(db.Model):
    __tablename__ = 'enrollments'
    id = db.Column(db.Integer, primary_key=True)
    enrolled_at = db.Column(db.DateTime, server_default=func.now())
    status = db.Column(db.Enum('active', 'inactive', 'pending', name='enrollment_status'), default='active')
    
    # Foreign Keys
    client_id = db.Column(db.Integer, ForeignKey('clients.id'), nullable=False)
    program_id = db.Column(db.Integer, ForeignKey('programs.id'), nullable=False)
    
    # Relationships
    client = relationship('Client', back_populates='enrollments')
    program = relationship('Program', back_populates='enrollments')
    
    __table_args__ = (
        UniqueConstraint('client_id', 'program_id', name='uq_enrollment_client_program'),
    )
    
    def __repr__(self):
        return f'<Enrollment {self.client.name} in {self.program.name}>'

class MedicalRecord(db.Model):
    __tablename__ = 'medical_records'
    id = db.Column(db.Integer, primary_key=True)
    diagnosis = db.Column(db.Text, nullable=False)
    prescriptions = db.Column(db.Text)
    visit_date = db.Column(db.DateTime, server_default=func.now())
    
    # Foreign Keys
    client_id = db.Column(db.Integer, ForeignKey('clients.id'), nullable=False)
    doctor_id = db.Column(db.Integer, ForeignKey('users.id'), nullable=False)
    
    # Relationships
    client = relationship('Client', back_populates='medical_records')
    doctor = relationship('User')
    
    def __repr__(self):
        return f'<MedicalRecord {self.visit_date} for {self.client.name}>'

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.DateTime, server_default=func.now())
    details = db.Column(db.Text)
    record_id = db.Column(db.Integer)  # ID of affected record
    
    # Foreign Key
    user_id = db.Column(db.Integer, ForeignKey('users.id'), nullable=False)
    
    # Relationship
    user = relationship('User', back_populates='audit_logs')
    
    __table_args__ = (
        Index('ix_audit_logs_timestamp', 'timestamp'),
        Index('ix_audit_logs_action', 'action'),
    )
    
    def __repr__(self):
        return f'<AuditLog {self.action} by {self.user.username}>'

class Medication(db.Model):
    __tablename__ = 'medications'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    interactions = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, server_default=func.now())
    
    def __repr__(self):
        return f'<Medication {self.name}>'

class Task(db.Model):
    __tablename__ = 'tasks'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    due_date = db.Column(db.DateTime)
    completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, server_default=func.now())
    
    # Foreign Key
    assigned_to = db.Column(db.Integer, ForeignKey('users.id'))
    
    # Relationship
    assignee = relationship('User')
    
    __table_args__ = (
        Index('ix_tasks_due_date', 'due_date'),
        Index('ix_tasks_completed', 'completed'),
    )
    
    def __repr__(self):
        return f'<Task {self.title} ({self.due_date})>'