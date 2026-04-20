from flask import Flask, render_template, request, redirect, session
import sqlite3
from flask_bcrypt import Bcrypt

app = Flask(__name__)

@app.route("/")
def render_homepage():
    return render_template("home.html")

@app.route('/login', methods=['POST', 'GET'])
def render_login_page():
    return render_template('login.html')

@app.route('/signup', methods=['POST', 'GET'])
def render_signup_page():
    return render_template('signup.html')

@app.route('/contact')
def render_contact_page():
    return render_template('contact.html')




app.run(host='0.0.0.0', debug=True)