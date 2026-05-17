from flask import Flask, render_template, request, redirect, session, url_for, flash
import sqlite3
from sqlite3 import Error
from flask_bcrypt import Bcrypt
from datetime import datetime

# Global settings for the application
DATABASE = "swim"
app = Flask(__name__)
bcrypt = Bcrypt(app)
app.secret_key = "helloworld"
ADMIN_SECRET_KEY = "very_secret_key"


def is_logged_in():
    """
    Checks if a user_id exists in the current session.
    :return: Boolean (True if logged in, False otherwise)
    """
    # Check if the user ID is missing from the session folder
    if session.get("user_id") is None:
        print("Not logged in")
        return False
    else:
        print("Successfully logged in")
        print(session.get("user_id"))
        return True


def connection_database(db_file):
    """
    Creates a connection with the database.
    :param db_file: The path to the database file (e.g., 'swim')
    :return: A connection object or None if an error occurs
    """
    try:
        connection = sqlite3.connect(db_file)
        return connection
    # Handle cases where the database file might be missing or locked
    except Error as e:
        print(e)
        print(f'An error occurred when connecting to the database. ')
    return None


@app.route('/')
def render_homepage():
    """
    Renders the main landing page.
    :return: HTML template for home.html
    """
    return render_template('home.html', logged_in = is_logged_in())


def generate_time_slots():
    """
    Creates a list of time strings for the booking dropdown.
    :return: A list of strings representing hours (06:00 to 21:00)
    """
    slots = []
    # Create hourly slots starting from 6 AM to 9 PM
    for i in range(6,22):
        slots.append(f"{i:02d}:00")
    return slots

def format_swim_time(time):
    """
    Ensures a time like 2:27.30000000 or 2:27.3 
    is always formatted as 2 dp e.g. 2:27.30
    Cleans up human errors when admin changes times in the database
    :param time: The time string of the selected swimmer_id
    :return: A formatted time with specifically 2 dp
    """
    time = time.strip()
    if '.' in time:
        base, milli_seconds = time.split('.', 1)
        # Pad with zeros if short (e.g., .3 -> .30), truncate if long (e.g., .3000 -> .30)
        milli_seconds = milli_seconds.ljust(2, '0')[:2]
        return f"{base}.{milli_seconds}"
    else:
        # If there was no decimal point then, append .00
        return f"{time}.00"
    
    
def parse_sortable_time(time_str):
    """
    Converts everything into the same time format for accurate sorting
    For example it converts 56.60 into 00:56.60 and 1:23.20 to 01:23.20
    Fixes text sorting math errors
    :param time_str: The time string of the swimmer
    :return: Formatted time for accurate sorting
    """
    time = time_str.strip()
    if ':' not in time:
        time = "00:" + time  # Adds 00 minutes if it's just seconds so it can sort in minutes.
    parts = time.split(':')
    # Fills the minute block with a zero if it's a single digit
    parts[0] = parts[0].zfill(2)
    return ":".join(parts)

def get_sortable_key(row_tuple):
    """
    Key for for list.sort(). 
    Takes a database row tuple (result_id, time) and returns 
    the normalized, sortable time string from index 1.
    :param row_tuple: The swimmer_id and the time string
    :return: Time string index 1 of row_tuple
    """
    time_str = row_tuple[1]
    return parse_sortable_time(time_str)


@app.route('/dashboard/modify-times', methods=['GET', 'POST'])
def render_modify_times_page():
    """
    Handles viewing and adding performance records.
    :return: HTML template for modify_times.html, all results of the swimmers, if user is logged in
    """
    # Security gate: Kick guests back to the login page
    if not is_logged_in():
        flash("You must be admin to modify times")
        return redirect(url_for("render_login_page"))

    conn = connection_database(DATABASE)
    cur = conn.cursor()

    # Handle the submission of a new swim result
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
            conn.commit() # Save the changes permanently
            flash("New result added successfully!")
        except Error as e:
            print(f"Error: {e}")
            flash("An error occurred while adding the result")

    # Fetch data for the display table using JOIN to get data from other tables
    fetch_query = ('''
        SELECT r.result_id, s.first_name, s.last_name, e.stroke, e.distance, r.time, r.placing, c.name, e.pool_length
        FROM results r
        JOIN swimmers s ON r.swimmer_id = s.swimmer_id
        JOIN events e ON r.event_id = e.event_id
        JOIN competitions c ON r.competition_id = c.competition_id
    ''')
    
    cur.execute(fetch_query)
    all_results = cur.fetchall()
    print(all_results)

    conn.close()
    
    return render_template(
        "modify_times.html",
        results=all_results,
        logged_in=is_logged_in()
    )


@app.route('/delete-result/<int:result_id>')
def delete_result(result_id):
    """
    Deletes a specific result record from the database.
    :param result_id: The unique ID of the result to be deleted
    :return: Redirects to the modify times page
    """
    # Permission check for active login
    if not is_logged_in():
        return redirect(url_for("render_login_page"))
    
    conn = connection_database(DATABASE)
    cur = conn.cursor()
    delete_query = "DELETE FROM results WHERE result_id = ?"
    cur.execute(delete_query, (result_id,))
    conn.commit()
    conn.close()
    flash("Result successfully deleted")
    return redirect(url_for('render_modify_times_page'))

@app.route('/edit-result/<int:result_id>', methods=['GET', 'POST'])
def edit_result(result_id):
    """
    Updates an existing result record, ensures 2 decimal point precision,
    and automatically recalculates event rankings for the race field.
    :param result_id: The unique ID of the result to be edited
    :return: HTML template for edit_result.html or a redirect on success, the result of all swimmers, the result for the swimmer id, if the user is logged in
    """
    conn = connection_database(DATABASE)
    cur = conn.cursor()

    # Process user edits for an existing record
    if request.method == 'POST':
        raw_time = request.form.get('time')
        
        # Changes time string to exactly 2 decimal places
        clean_time = format_swim_time(raw_time)
        
        try:
            # Fetch event_id and competition_id to find all swimmmers in the same race
            fetch_info_query = ('''
                SELECT event_id, competition_id FROM results 
                WHERE result_id = ?
            ''')
            cur.execute(fetch_info_query, (result_id,))
            result_info = cur.fetchone()
            
            if result_info:
                event_id, competition_id = result_info[0], result_info[1]
                
                # Update formatted time to the targeted swimmer
                update_time_query = ('''
                    UPDATE results SET time = ? 
                    WHERE result_id = ?
                ''')
                cur.execute(update_time_query, (clean_time, result_id))
                
                # Fetch all results needed to sort the placing of the race
                fetch_race_results_query = ('''
                    SELECT result_id, time FROM results 
                    WHERE event_id = ? AND competition_id = ?
                ''')
                cur.execute(fetch_race_results_query, (event_id, competition_id))
                all_results = cur.fetchall()
                
                # Sort using a specific key to using helper function
                all_results.sort(key=get_sortable_key)
                
                # For loop through the sorted index pool to update new placements
                for index, row in enumerate(all_results):
                    new_placing = index + 1
                    update_placing_query = ('''
                        UPDATE results SET placing = ? 
                        WHERE result_id = ?
                    ''')
                    cur.execute(update_placing_query, (new_placing, row[0]))
                
                conn.commit()
                flash("Result updated and standings re-ranked successfully!")
                
        except Error as e:
            conn.rollback()
            print(f"Error recalculating rankings: {e}")
            flash("An error occurred while updating the data.")
        finally:
            conn.close()
            
        return redirect(url_for('render_modify_times_page'))

    # Load existing data for admin
    fetch_query = ('''
        SELECT r.time, r.placing, e.distance, e.stroke, s.first_name, s.last_name
        FROM results r
        JOIN events e ON e.event_id = r.event_id
        JOIN swimmers s ON r.swimmer_id = s.swimmer_id
        WHERE result_id = ?
    ''')
    
    cur.execute(fetch_query, (result_id,))
    result_data = cur.fetchone()
    print(result_data)
    conn.close()
    
    return render_template(
        "edit_result.html", 
        result=result_data, 
        result_id=result_id, 
        logged_in=is_logged_in()
    )

    
    
@app.route('/dashboard/user-bookings/<int:booking_id>')
def remove_user_bookings(booking_id):
    """
    Removes a booking entry.
    :param booking_id: The unique ID of the booking to delete
    :return: Redirects to the user bookings page
    """
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
    # Prevent crashes incase of database error
    except Error as e:
        print(f"Error:{e}")
        flash("An error occured while removing the booking")
    finally:
        conn.close()
    
    return redirect(url_for("render_user_bookings_page"))
    

@app.route('/manage_team/<int:swimmer_id>')
def remove_swimmer_from_team(swimmer_id):
    """
    Removes a swimmer from the team associated with the current coach.
    :param swimmer_id: The unique ID of the swimmer to remove
    :return: Redirects to the manage team page
    """
    if not is_logged_in():
        flash("You must be logged in to manage teams")
        return redirect(url_for("render_login_page"))

    user_id = session.get("user_id")
    
    conn = connection_database(DATABASE)
    cur = conn.cursor()
    
    # Deletes swimmer coach relationship
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
    """
    Searches for swimmers on the coach's team.
    :return: HTML template for manage_team.html with filtered results, if user is logged in, search filter is in use, search query
    """
    if not is_logged_in():
        flash("You must be logged in to manage teams")
        return redirect(url_for("render_login_page"))
    
    search = request.form.get("swimmer-search", "")
    user_id = session.get("user_id")
    conn = connection_database(DATABASE)
    cur = conn.cursor()
    
    # Filter team members by name or club using LIKE 
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
    """
    Adds a swimmer to the current coach's team.
    :param swimmer_id: The unique ID of the swimmer to add
    :return: Redirects to manage team or add swimmers page
    """
    if not is_logged_in():
        flash("You must be logged in to manage teams")
        return redirect(url_for("render_login_page"))

    user_id = session.get("user_id")
    
    conn = connection_database(DATABASE)
    cur = conn.cursor()
    
    # Query to check if the swimmer is already assigned to this coach
    check_query = ('''
                    SELECT * FROM team_members
                    WHERE coach_id = ? 
                    AND swimmer_id = ?
                ''')
    
    cur.execute(check_query, (user_id,swimmer_id,))
    
    # If fetchone() returns data, the coach already has this swimmer
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
    """
    Lists all available swimmers that can be added to a team.
    :return: HTML template for add_swimmers.html, all swimmers in the database, if the user is logged in
    """
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
    """
    Displays the swimmers currently on the coach's team.
    :return: HTML template for manage_team.html, if user is logged in, swimmers in coach users team
    """
    if not is_logged_in():
        flash("You must be logged in to view your team")
        return redirect(url_for("render_login_page"))
    
    user_id = session.get("user_id")
    
    conn = connection_database(DATABASE)
    cur = conn.cursor()
    
    # Fetch team members assigned specifically to the logged-in coach
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
    """
    Displays performance records for a specific swimmer.
    :param swimmer_id: The unique ID of the swimmer whose results are requested
    :return: HTML template for swim_results.html, if user is logged in, swim results of the swimmer, all results
    """
    if not is_logged_in():
        flash("Please log in first")
        return redirect(url_for("render_login_page"))
    
    user_id = session.get("user_id")
    conn = connection_database(DATABASE)
    cur = conn.cursor()
    
    # Retrieve the user's role to check viewing privileges
    query_1 = ("SELECT role FROM users WHERE user_id = ?")
    
    cur.execute(query_1, (user_id,))
    
    try:
        role = cur.fetchone()[0]
    # Handle boundary cases where a user session exists but the database record is gone
    except Error as e:
        flash("User session expired. Please log in again.")
        return redirect(url_for("render_login_page"))
    
    # If the user is a swimmer check they are only trying to see their own results
    if role == 'swimmer':
        query_2 = ("SELECT swimmer_id FROM swimmers WHERE user_id = ?")
        cur.execute(query_2, (user_id,))
        own_profile = cur.fetchone()
        
        if own_profile:
            my_id = own_profile[0] 
        else:
            return None
        
        # Stops swimmers from checking on other swimmers results using url manipulation
        if swimmer_id != my_id:
            flash("You only have permission to view your own results.")
            return redirect(url_for('render_dashboard_page'))

    # Join results with event and competition data for entire display
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
        logged_in= is_logged_in(), 
        swim_results=swim_results, 
        role=role
    )


@app.route('/dashboard/user-bookings')
def render_user_bookings_page():
    """
    Shows bookings for the current user and all bookings for admins.
    :return: HTML template for user_bookings.html, if user is logged in or not, user role, all bookings for admin use
    """
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
    """
    Renders the appropriate dashboard based on user role.
    :return: HTML template for dashboard.html, if user is logged in, user role
    """
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
    """
    Shows the lane booking form.
    :return: HTML template for booking.html, lanes available and all time slots
    """
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
    """
    Processes a lane booking submission.
    :return: Redirects back to the booking page with a success or error message
    """
    if not is_logged_in():
        return redirect(url_for('render_login_page'))
    
    lane_id = request.form['lane_id']
    booking_date = request.form['booking_date'] 
    start_time = request.form['start_time']
    duration = int(request.form['duration'])
    user_id = session.get("user_id")
    
    # Business logic check: bookings must be exactly 1 or 2 hours
    if duration not in (1,2):
        flash("Only 1 to 2 hr bookings")
        return redirect(url_for("render_booking_page"))
    
    try:
        booking_date_obj = datetime.strptime(booking_date, "%Y-%m-%d")
        today_date = datetime.today()
        print(today_date)
        # Prevent users from booking pool lanes in the past
        if booking_date_obj < today_date:
            flash("Error: Cannot book past dates")
            return redirect(url_for("render_booking_page"))
            
    except ValueError:
        flash("Error: Invalid date")
        return redirect(url_for("render_booking_page"))
    
    # Calculate end time based on the starting hour and duration selected
    start_hr = int(start_time[:2])
    end_hr = start_hr + duration
    end_time = f"{end_hr:02d}:00"
    
    # Pool operational hours check: facility closes at 9 PM
    if end_hr > 21:
        flash("Error: Cannot book past 9pm")
        return redirect(url_for("render_booking_page"))
    
    time_slot = f"{start_time}-{end_time}"
    
    conn = connection_database(DATABASE)
    cur  = conn.cursor()
    # SQL query to check if the specific lane is already reserved for this time/date
    query = ('''
             SELECT * FROM bookings
            WHERE lane_id = ? AND booking_date = ? AND time_slot = ?
            ''')
    
    cur.execute(query, (lane_id, booking_date, time_slot))
    
    # If fetchone() finds a record, it means a conflict exists
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
    """
    Clears the session and logs the user out.
    :return: Redirects to the homepage
    """
    session.clear() # Wipes all active user data from the browser session
    return redirect(url_for("render_homepage"))



@app.route('/login', methods = ['POST','GET'])
def render_login_page():
    """
    Handles user login.
    :return: HTML template for login.html or redirects on successful login
    """
    # If the user is already authenticated, send them to the home page
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
        
        try:
            user_id = user_info[0]
            first_name = user_info[1]
            user_password = user_info[3]
        # Handle the case where the provided email does not exist in the database
        except (IndexError, TypeError):
            cur.close()
            conn.close()
            flash("Error email or passwords invalid")
            return redirect(url_for("render_login_page"))

        # Use Bcrypt to securely verify the hashed password
        if not bcrypt.check_password_hash(user_password, password):
            cur.close()
            conn.close()
            flash("Error email or passwords invalid")
            return redirect(url_for("render_login_page"))

        # Store essential user data in the session for state management
        session['email'] = email
        session['user_id'] = user_id
        session['first_name'] = first_name
        
        data_query = "SELECT swimmer_id FROM swimmers WHERE user_id = ?"

        cur.execute(data_query, (user_id,))
        swimmer_data = cur.fetchone()
        
        # Link the swimmer profile if one exists for the user account
        if swimmer_data:
            session['swimmer_id'] = swimmer_data[0]
        else:
            session['swimmer_id'] = None

        cur.close()
        conn.close()
        
        print(session)
        flash(f"Successfully logged in Welcome {first_name}")
        return redirect(url_for("render_homepage"))

    return render_template(
        'login.html',
        logged_in = is_logged_in()
    )




@app.route('/signup', methods = ['POST','GET'])
def render_signup_page():
    """
    Registers a new user and creates a swimmer profile.
    :return: HTML template for signup.html or redirect to login on success
    """
    if request.method == 'POST':
        role = request.form.get('role')
        fname = request.form.get('user_fname').title().strip()
        lname = request.form.get('user_lname').title().strip()
        email = request.form.get('user_email')
        password = request.form.get('user_password')
        confirm_password = request.form.get('user_confirm_password')
        
        # Checks if role is admin and then verifies the secret key
        if role == 'admin':
            secret_key_input = request.form.get('admin_secret_key')
            # If the secret key is incorrect, flash an error and reload signup
            if secret_key_input != ADMIN_SECRET_KEY:
                flash("Invalid Admin Secret Key. Access denied.")
                return redirect(url_for("render_signup_page"))

        # Form validation: ensure passwords match and are long enough for security
        if password != confirm_password:
            flash("Passwords do not match")
            return redirect(url_for("render_signup_page"))

        if len(password) < 8:
            flash("Password must be over 8 characters")
            return redirect(url_for("render_signup_page"))
        
        if len(password) > 72:
            flash("Password cannot be over 72 characters")
            return redirect(url_for("render_signup_page"))

        # Encrypt the password before storing it in the database
        hashed_password = bcrypt.generate_password_hash(password)

        con = connection_database(DATABASE)
        cur = con.cursor()
        
        # Query for the submitted email
        email_query = "SELECT email FROM users WHERE email = ?"
        cur.execute(email_query, (email.strip().lower(),))

        email_check = cur.fetchone()

        # Checks if there is any existing emails and if there is then sends error message
        if email_check is not None:
            flash("Email already has a user")
            return redirect(url_for("render_signup_page"))
        
        try:
        
            # Create the main user account record
            query_user = "INSERT INTO users (first_name, last_name, email, password, role) VALUES(?,?,?,?,?)"
            cur.execute(query_user, (fname, lname, email, hashed_password, role))
            
            # Retrieve the newly created unique user ID to link other tables
            new_user_id = cur.lastrowid 

            # Every account is set to a swimmer profile
            query_swimmer = "INSERT INTO swimmers (first_name, last_name, user_id, gender, club) VALUES(?,?,?,?,?)"
            cur.execute(query_swimmer, (fname, lname, new_user_id, "TBD", "TBD"))

            con.commit()
            flash(f"Welcome {fname}! Your account and swimmer profile are ready.")
            return redirect(url_for("render_login_page"))

        # Handle errors and unexpected cases 
        except Exception as e:
            print(f"Error during signup: {e}")
            flash("An error occurred. The email might already be taken.")
            return redirect(url_for("render_signup_page"))
        finally:
            con.close()

    return render_template(
        'signup.html', 
        logged_in = is_logged_in()
    )




@app.route('/contact')
def render_contact_page():
    """
    Shows contact information.
    :return: HTML template for contact.html, if user is logged in
    """
    return render_template(
        'contact.html', 
        logged_in = is_logged_in()
        )




app.run(host='0.0.0.0', debug=True)