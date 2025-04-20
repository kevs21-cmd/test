from flask import Flask, app
from flask_mysqldb import MySQL
import os

mysql = MySQL()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'kevin'
    app.config['MYSQL_HOST'] = 'localhost'
    app.config['MYSQL_PORT'] = 3306
    app.config['MYSQL_USER'] = 'root'
    app.config['MYSQL_PASSWORD'] = 'Password01'
    app.config['MYSQL_DB'] = 'enrollment_student'

    mysql.init_app(app)

    from .views import views
    from .auth import auth  # This is okay as long as auth.py doesn't import create_app or app

    app.register_blueprint(views, url_prefix='/')
    app.register_blueprint(auth, url_prefix='/')

    return app



