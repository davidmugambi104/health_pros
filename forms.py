# In your forms.py
from flask_wtf import FlaskForm
from wtforms import SelectField, DateField, TextAreaField, BooleanField, SubmitField
from wtforms.validators import DataRequired

class CreateAppointmentForm(FlaskForm):
    patient = SelectField('Patient', coerce=int, validators=[DataRequired()])
    date = DateField('Appointment Date', validators=[DataRequired()])
    is_urgent = BooleanField('Urgent Appointment')
    notes = TextAreaField('Notes')
    submit = SubmitField('Schedule Appointment')

