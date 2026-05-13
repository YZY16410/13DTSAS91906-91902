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

@app.route('/dashboard/modify-times', methods=['GET', 'POST'])
def render_modify_times_page():
    if not is_logged_in():
        flash("You must be admin to modify times")
        return redirect(url_for("render_login_page"))

    conn = connection_database(DATABASE)
    cur = conn.cursor()

    if request.method == 'POST':
        # Retrieve form data 
        swimmer_id = request.form.get('swimmer_id')
        event_id = request.form.get('event_id')
        comp_id = request.form.get('competition_id')
        swim_time = request.form.get('time')
        placing = request.form.get('placing')

        try:
            # Insert new record into results table 
            query = ('''
                    INSERT INTO results (swimmer_id, event_id, competition_id, time, placing) 
                    VALUES (?, ?, ?, ?, ?)
                ''')
            
            cur.execute(query, (swimmer_id, event_id, comp_id, swim_time, placing))
            conn.commit()
            flash("New result added successfully!")
        except Error as e:
            print(f"Error: {e}")
            flash("An error occurred while adding the result")

    fetch_query = ('''
        SELECT r.result_id, s.first_name, s.last_name, e.stroke, e.distance, r.time, r.placing, c.name
        FROM results r
        JOIN swimmers s ON r.swimmer_id = s.swimmer_id
        JOIN events e ON r.event_id = e.event_id
        JOIN competitions c ON r.competition_id = c.competition_id
    ''')
    
    cur.execute(fetch_query)
    all_results = cur.fetchall()

    cur.execute("SELECT swimmer_id, first_name, last_name FROM swimmers")
    swimmers_list = cur.fetchall()
    
    cur.execute("SELECT event_id, stroke, distance FROM events")
    events_list = cur.fetchall()
    
    cur.execute("SELECT competition_id, name FROM competitions")
    comps_list = cur.fetchall()

    conn.close()
    
    return render_template(
        "modify_times.html",
        results=all_results,
        swimmers=swimmers_list,
        events=events_list,
        comps=comps_list,
        logged_in=is_logged_in()
    )

@app.route('/delete-result/<int:result_id>')
def delete_result(result_id):
    if not is_logged_in():
        return redirect(url_for("render_login_page"))
    
    conn = connection_database(DATABASE)
    cur = conn.cursor()
    cur.execute("DELETE FROM results WHERE result_id = ?", (result_id,))
    conn.commit()
    conn.close()
    flash("Result successfully deleted")
    return redirect(url_for('render_modify_times_page'))

@app.route('/edit-result/<int:result_id>', methods=['GET', 'POST'])
def edit_result(result_id):
    conn = connection_database(DATABASE)
    cur = conn.cursor()

    if request.method == 'POST':
        new_time = request.form.get('time')
        new_placing = request.form.get('placing')
        
        
        query = ('''
                UPDATE results SET time = ?, placing = ? 
                WHERE result_id = ?"
            ''')
        
        cur.execute(query, (new_time, new_placing, result_id))
        conn.commit()
        conn.close()
        flash("Result updated!")
        return redirect(url_for('render_modify_times_page'))

    fetch_query = ('''
                SELECT r.time, r.placing, e.distance, e.stroke, s.first_name, s.last_name
                FROM results r
                JOIN events e ON e.event_id = r.event_id
                JOIN swimmers s ON s.swimmer_id = r.swimmer_id
                WHERE result_id = ?
                
            ''')
    cur.execute(fetch_query, (result_id,))
    data = cur.fetchone()
    print(data)
    conn.close()
    return render_template("edit_result.html", data=data, result_id=result_id, logged_in=is_logged_in())

@app.route('/dashboard/user-bookings/<int:booking_id>')
def remove_user_bookings(booking_id):
    
    if not is_logged_in():
        flash("You must be logged in to manage bookings")
        return redirect(url_for("render_login_page"))
    
    conn = connection_database(DATABASE)
    cur = conn.cursor()
    
    try:
        query = ('''
                DELETE FROM bookings
                WHERE booking_id = ?
            ''')
        cur.execute(query, (booking_id,))
        conn.commit()
        flash("Booking successfully removed")
        
    except Error as e:
        print(f"Error:{e}")
        flash("An error occured while removing the booking")
    finally:
        conn.close()
    
    return redirect(url_for("render_user_bookings_page"))
    

@app.route('/manage_team/<int:swimmer_id>')
def remove_swimmer_from_team(swimmer_id):
    
    if not is_logged_in():
        flash("You must be logged in to manage teams")
        return redirect(url_for("render_login_page"))

    user_id = session.get("user_id") # The coach's user id
    
    conn = connection_database(DATABASE)
    cur = conn.cursor()
    
    query = ('''
            DELETE FROM team_members
            WHERE swimmer_id = ? 
            AND coach_id = ?
        ''')
    
    cur.execute(query, (swimmer_id,user_id,))
    conn.commit()
    flash("Swimmmer successfully removes from team")
    
    
    return redirect(url_for("render_manage_team_page"))
    


@app.route('/dashboard/manage-team/search', methods = ['GET', 'POST'])
def manage_team_search():
    if not is_logged_in():
        flash("You must be logged in to manage teams")
        return redirect(url_for("render_login_page"))
    
    search = request.form.get("swimmer-search", "")
    user_id = session.get("user_id")
    conn = connection_database(DATABASE)
    cur = conn.cursor()
    
    query = ('''
            SELECT s.swimmer_id, s.first_name, s.last_name, s.gender, s.club
            FROM swimmers s
            JOIN team_members tm ON s.swimmer_id = tm.swimmer_id
            WHERE tm.coach_id = ?
            AND (s.first_name LIKE ? OR s.last_name LIKE ? OR s.club LIKE ?)

        ''')
    
    search = f"%{search}%"
    cur.execute(query,(user_id,search,search,search))
    
    swimmers = cur.fetchall()
    print(swimmers)
    conn.close()
    
    return render_template(
        "manage_team.html", 
        swimmers = swimmers,
        logged_in = is_logged_in,
        is_search = True,
        search_term = search
        )

@app.route('/add-swimmer/<int:swimmer_id>')
def add_swimmer_to_team(swimmer_id):
    if not is_logged_in():
        flash("You must be logged in to manage teams")
        return redirect(url_for("render_login_page"))

    user_id = session.get("user_id") # The Coach/Admin's ID
    
    conn = connection_database(DATABASE)
    cur = conn.cursor()
    
    check_query = ('''
                    SELECT * FROM team_members
                    WHERE coach_id = ? 
                    AND swimmer_id = ?
                ''')
    
    cur.execute(check_query, (user_id,swimmer_id,))
    
    if cur.fetchone():
        flash("This swimmer is already on your team")
        return redirect(url_for("render_add_swimmers_page"))
    
    else:
        
        try:
            query = ('''
                    INSERT INTO team_members (coach_id, swimmer_id) VALUES(?, ?)
                ''')
            cur.execute(query,(user_id,swimmer_id,))
            conn.commit()
            flash("Swimmer successfully added to your team!")
            
        except Exception as e:
            print(f"Error: {e}")
            flash("Swimmer is already on your team")
            
        finally:
            conn.close()
        
    
    return redirect(url_for("render_manage_team_page"))

@app.route('/add-swimmers')
def render_add_swimmers_page():
    if not is_logged_in():
        flash("You must be logged in to manage teams")
        return redirect(url_for("render_login_page"))
    
    user_id = session.get("user_id")
    
    conn = connection_database(DATABASE)
    cur = conn.cursor()
    query = ('''
            SELECT * FROM swimmers
        ''')
    
    cur.execute(query)
    all_swimmers = cur.fetchall()
    print(all_swimmers)
    
    return render_template(
                        "add_swimmers.html",
                        all_swimmers = all_swimmers,
                        logged_in = is_logged_in()
                    )
    
    

@app.route('/dashboard/manage-team')
def render_manage_team_page():
    if not is_logged_in():
        flash("You must be logged in to view your team")
        return redirect(url_for("render_login_page"))
    
    user_id = session.get("user_id")
    
    conn = connection_database(DATABASE)
    cur = conn.cursor()
    
    query = ('''
        SELECT s.swimmer_id, s.first_name, s.last_name, s.gender, s.club
        FROM swimmers s
        JOIN team_members tm ON s.swimmer_id = tm.swimmer_id
        WHERE tm.coach_id = ?
    ''')
    
    cur.execute(query, (user_id,))
    swimmers = cur.fetchall()
    conn.close()
    
    
    
    return render_template(
                        "manage_team.html",
                        logged_in = is_logged_in(),
                        swimmers = swimmers
                    )



@app.route('/dashboard/swim-results/<int:swimmer_id>')
def render_swim_results_page(swimmer_id):
    
    if not is_logged_in():
        flash("You must be logged in to view your teams results")
        return redirect(url_for("render_login_page"))
    
    
    user_id = session.get("user_id")
    print(f"session user_id:{user_id}")
    
    
    conn = connection_database(DATABASE)
    cur = conn.cursor()
    
    role_query = ('''
                SELECT role FROM users
                WHERE user_id = ?
            ''')
    cur.execute(role_query,(user_id,))
    
    role = cur.fetchone()[0]
    
    query = ('''
        SELECT e.stroke, e.distance, r.time, r.placing, c.name, c.date, s.first_name, s.last_name
        FROM results r
        JOIN swimmers s ON r.swimmer_id = s.swimmer_id
        JOIN events e ON r.event_id = e.event_id
        JOIN competitions c ON r.competition_id = c.competition_id
        WHERE r.swimmer_id = ?
    ''')
    
    cur.execute(query, (swimmer_id,))
    swim_results = cur.fetchall()
    print(swim_results)
    
    conn.close()
    
    
    
    return render_template(
        "swim_results.html",
        logged_in = is_logged_in(),
        swim_results = swim_results,
        role = role,
    )


@app.route('/dashboard/user-bookings')
def render_user_bookings_page():
    
    user_id = session.get("user_id")
    print(f"session user_id:{user_id}")
    
    
    conn = connection_database(DATABASE)
    cur = conn.cursor()
    
    role_query = ('''
                SELECT role FROM users
                WHERE user_id = ?
            ''')
    cur.execute(role_query,(user_id,))
    
    role = cur.fetchone()[0]
    
    booking_query = ('''
                SELECT * FROM bookings
                WHERE user_id = ?
            ''')

    
    cur.execute(booking_query,(user_id,))
    user_bookings = cur.fetchall()
    print(user_bookings)
    
    all_bookings_query = ('''
                        SELECT * FROM bookings
                    ''')
    
    cur.execute(all_bookings_query)
    all_bookings = cur.fetchall()
    print(all_bookings)
    
    
    return render_template(
                        'user_bookings.html',
                        logged_in = is_logged_in(),
                        user_bookings = user_bookings,
                        role = role,
                        all_bookings = all_bookings
                    )
    
    


@app.route('/dashboard')
def render_dashboard_page():
    if not is_logged_in():
        flash("Error You must be logged in")
        return redirect(url_for("render_login_page"))
    
    user_id = session.get("user_id")
    print(f"session user_id:{user_id}")
    
    
    conn = connection_database(DATABASE)
    cur = conn.cursor()
    
    
    role_query = ('''
                SELECT role FROM users
                WHERE user_id = ?
            ''')
    cur.execute(role_query,(user_id,))
    
    role = cur.fetchone()[0]
    
    
    return render_template(
                    'dashboard.html', 
                    logged_in = is_logged_in(), 
                    role = role
                )
    




@app.route('/booking', methods = ['GET'])
def render_booking_page():
    if not is_logged_in():
        flash("Error You must be logged in")
        return redirect(url_for("render_login_page"))
    
    available_lanes = [0,1,2,3,4,5,6,7,8,9]
    times_slots = generate_time_slots()
    print(f"available time slots: {times_slots}")
    
    return render_template(
                        'booking.html',
                        logged_in = is_logged_in(),
                        available_lane = available_lanes, 
                        time_slots = times_slots
                    )
    
    
    
    
@app.route('/submit-booking', methods = ['POST'])
def submit_booking():
    if not is_logged_in():
        return redirect(url_for('render_login_page'))
    
    lane_id = request.form['lane_id']
    booking_date = request.form['booking_date'] 
    start_time = request.form['start_time']
    duration = int(request.form['duration'])
    user_id = session.get("user_id")
    
    
    if duration not in (1,2):
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
            WHERE lane_id = ? AND booking_date = ? AND time_slot = ?
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
            flash("Error email or passwords invalid")
            return redirect(url_for("render_login_page"))

        if not bcrypt.check_password_hash(user_password, password):
            flash("Error email or passwords invalid")
            return redirect(url_for("render_login_page"))

        session['email'] = email
        session['user_id'] = user_id
        session['first_name'] = first_name
        print(session)
        flash(f"Successfully logged in Welcome {first_name}")
        return redirect(url_for("render_homepage"))

    return render_template(
                        'login.html',
                        logged_in = is_logged_in()
                        )




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

    return render_template(
        'signup.html', 
        logged_in = is_logged_in()
        )




@app.route('/contact')
def render_contact_page():
    return render_template(
        'contact.html', 
        logged_in = is_logged_in()
        )




app.run(host='0.0.0.0', debug=True)