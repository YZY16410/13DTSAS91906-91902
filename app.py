from flask import Flask, render_template, request, redirect, session, url_for, flash
import sqlite3
from sqlite3 import Error
from flask_bcrypt import Bcrypt
from datetime import datetime


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
        print(session.get("user_id"))
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




def generate_time_slots():
    slots = []
    for i in range(6,22):
        slots.append(f"{i:02d}:00")
    return slots




@app.route('/booking', methods = ['GET'])
def render_booking_page():
    if not is_logged_in():
        flash("Error You must be logged in")
        return redirect(url_for("render_login_page"))
    
    available_lanes = [0,1,2,3,4,5,6,7,8,9]
    times_slots = generate_time_slots()
    print(f"available time slots: {times_slots}")
    
    return render_template('booking.html', logged_in = is_logged_in(), available_lane = available_lanes, time_slots = times_slots)
    
    
    
    
@app.route('/submit-booking', methods = ['POST'])
def submit_booking():
    if not is_logged_in():
        return redirect(url_for('render_login_page'))
    
    lane_id = request.form['lane_id']
    booking_date = request.form['booking_date'] 
    start_time = request.form['start_time']
    duration = int(request.form['duration'])
    user_id = session.get("user_id")
    
    
    if duration not in (1,1.5,2):
        flash("Only 1 to 2 hr bookings")
        return redirect(url_for("render_booking_page"))
    
    try:
        booking_date_obj = datetime.strptime(booking_date, "%Y-%m-%d")
        today_date = datetime.today()
        print(today_date)
        if booking_date_obj < today_date:
            flash("Error: Cannot book past dates")
            return redirect(url_for("render_booking_page"))
            
    except ValueError:
        flash("Error: Invalid date")
        return redirect(url_for("render_booking_page"))
    
    start_hr = int(start_time[:2])
    end_hr = start_hr + duration
    end_time = f"{end_hr:02d}:00"
    
    if end_hr > 21:
        flash("Error: Cannot book past 9pm")
        return redirect(url_for("render_booking_page"))
    
    time_slot = f"{start_time}-{end_time}"
    
    conn = connection_database(DATABASE)
    cur  = conn.cursor()
    query = ('''
             SELECT * FROM bookings
            WHERE lane_id = ? AND booking_date = ? AND time_slot == ?
            ''')
    
    cur.execute(query, (lane_id, booking_date, time_slot))
    
    if cur.fetchone():
        flash("Error: Lane already booked")
        return redirect(url_for("render_booking_page"))
    
    query_insert = ('''
                    INSERT INTO bookings (user_id, lane_id, booking_date, time_slot)
                    VALUES (?,?,?,?)
                    ''')
    cur.execute(query_insert, (user_id, lane_id, booking_date, time_slot))
    conn.commit()
    cur.close()
    conn.close()
    
    flash("Success! Booking created successfully")
    return redirect(url_for("render_booking_page"))
    
    
    


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for("render_homepage"))



@app.route('/login', methods = ['POST','GET'])
def render_login_page():
    if is_logged_in():
        return redirect(url_for("render_homepage"))

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
        return redirect(url_for("render_homepage"))

    return render_template('login.html', logged_in = is_logged_in())




@app.route('/signup', methods = ['POST','GET'])
def render_signup_page():
    if request.method == 'POST':
        role = request.form.get('role')
        fname = request.form.get('user_fname')
        lname = request.form.get('user_lname')
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
        return redirect(url_for("render_login_page"))

    return render_template('signup.html', logged_in = is_logged_in())




@app.route('/contact')
def render_contact_page():
    return render_template('contact.html', logged_in = is_logged_in())




app.run(host='0.0.0.0', debug=True)