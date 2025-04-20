from datetime import datetime
from flask import Blueprint, flash, render_template, session, redirect, url_for
from .models import get_student_by_id  # Import function to get student by ID


views = Blueprint('views', __name__)


@views.route('/about')
def about():
    return render_template('about.html')

@views.route('/contact')
def contact():
    return render_template('contact.html')
