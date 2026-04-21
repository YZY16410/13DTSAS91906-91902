from flask import Flask, render_template, request, redirect, session
import sqlite3
from sqlite3 import Error
from flask_bcrypt import Bcrypt


DATABASE = "swim"
app = Flask(__name__)
bcrypt = Bcrypt(app)
app.secret_key = "helloworld"


def is_logged_in():
    if session.get("user_id") is None:
        print("Not logged in")
        return False
    else:
        print("Successfully logged in")
        return True

def connection_database(db_file):
    """
    creates a connection with the database
    :param db_file:
    :return: conn
    """
    try:
        connection = sqlite3.connect(db_file)
        return connection
    except Error as e:
        print(e)
        print(f'An error occurred when connecting to the database. ')
    return None


@app.route('/')
def render_homepage():
    return render_template('home.html', logged_in = is_logged_in())

@app.route('/login', methods = ['POST','GET'])
def render_login_page():
    if is_logged_in():
        return redirect("/menu/1")

    if request.method == 'POST':
        email = request.form['user_email'].strip().lower()
        password = request.form['user_password']

        query = "SELECT user_id, first_name, last_name, password, role FROM users WHERE email = ?"
        conn = connection_database(DATABASE)
        cur = conn.cursor()
        cur.execute(query, (email,))
        user_info = cur.fetchone()
        print(user_info)
        cur.close()

        try:
            user_id = user_info[0]
            first_name = user_info[1]
            user_password = user_info[3]
        except (IndexError, TypeError):
            return redirect("/login?error=email+or+password+invalid")

        if not bcrypt.check_password_hash(user_password, password):
            return redirect("/login?error=email+or+password+invalid")

        session['email'] = email
        session['user_id'] = user_id
        session['first_name'] = first_name
        print(session)
        return redirect("/")

    return render_template('login.html', logged_in = is_logged_in())

@app.route('/signup', methods = ['POST','GET'])
def render_signup_page():
    if request.method == 'POST':
        role = request.form.get('role')
        fname = request.form.get('user_fname').title().strip()
        lname = request.form.get('user_lname').title().strip()
        email = request.form.get('user_email').lower().strip()
        password = request.form.get('user_password')
        confirm_password = request.form.get('user_confirm_password')

        if password != confirm_password:
            return redirect("/signup?error=passwords+do+not+match")

        if len(password) < 8:
            return redirect("/signup?error=password+must+be+over+8+characters")

        hashed_password = bcrypt.generate_password_hash(password)

        con = connection_database(DATABASE)
        query_insert = "INSERT INTO users (first_name, last_name, email, password, role) VALUES(?,?,?,?,?)"
        cur = con.cursor()
        cur.execute(query_insert, (fname, lname, email, hashed_password, role))
        con.commit()
        con.close()
        return(render_template('login.html'))

    return render_template('signup.html', logged_in = is_logged_in())

@app.route('/contact')
def render_contact_page():
    return render_template('contact.html')




app.run(host='0.0.0.0', debug=True)