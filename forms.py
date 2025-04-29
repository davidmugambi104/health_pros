from flask_wtf import FlaskForm
from wtforms import DateTimeLocalField, TextAreaField, BooleanField, SelectField
from wtforms.validators import DataRequired

class AppointmentForm(FlaskForm):
    patient_id = SelectField('Patient', coerce=int, validators=[DataRequired()])
    date = DateTimeLocalField('Appointment Date', validators=[DataRequired()], format='%Y-%m-%dT%H:%M')
    notes = TextAreaField('Notes')
    is_urgent = BooleanField('Urgent Appointment')