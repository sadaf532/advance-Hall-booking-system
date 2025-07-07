import sqlite3
from datetime import datetime, timedelta
import schedule
import time
import threading

def init_db():
    conn = sqlite3.connect('bookings.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            roll TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT,
            hall TEXT,
            meal_type TEXT,
            booking_date TEXT,
            FOREIGN KEY (user_email) REFERENCES users (email)
        )
    ''')
    conn.commit()
    conn.close()

def register_user(email, username, roll, password):
    conn = sqlite3.connect('bookings.db')
    c = conn.cursor()
    try:
        c.execute('INSERT INTO users (email, username, roll, password) VALUES (?, ?, ?, ?)',
                  (email, username, roll, password))
        conn.commit()
        print(f"User registered: {email}")
        return True
    except sqlite3.IntegrityError as e:
        print(f"Registration failed: {str(e)}")
        return False
    finally:
        conn.close()

def authenticate_user(email, roll, password):
    conn = sqlite3.connect('bookings.db')
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE email = ? AND roll = ? AND password = ?', (email, roll, password))
    user = c.fetchone()
    conn.close()
    print(f"Authentication attempt - Email: {email}, User found: {user is not None}")
    return user

def book_meal(user_email, hall, meal_type, booking_date, ticket_count):
    conn = sqlite3.connect('bookings.db')
    c = conn.cursor()
    
    print(f"Book meal - User: {user_email}, Hall: {hall}, Meal Type: {meal_type}, Date: {booking_date}, Tickets: {ticket_count}")
    
    c.execute('''
        SELECT COUNT(*) FROM bookings 
        WHERE user_email = ? AND meal_type = ? AND date(booking_date) = ?
    ''', (user_email, meal_type, booking_date))
    meal_bookings = c.fetchone()[0]
    print(f"Current {meal_type} bookings for {booking_date}: {meal_bookings}")
    
    if meal_bookings + ticket_count > 5:
        conn.close()
        return None, f"Maximum 5 {meal_type} bookings per day reached (currently {meal_bookings})"
    
    c.execute('''
        SELECT COUNT(*) FROM bookings 
        WHERE hall = ? AND meal_type = ? AND date(booking_date) = ?
    ''', (hall, meal_type, booking_date))
    hall_bookings = c.fetchone()[0]
    print(f"Total {meal_type} bookings for {hall} on {booking_date}: {hall_bookings}")
    
    max_tickets = {'Lunch': 250, 'Dinner': 250}
    if hall_bookings + ticket_count > max_tickets.get(meal_type, 0):
        conn.close()
        return None, f"Not enough {meal_type} tickets available for {hall} on {booking_date} (available: {max_tickets[meal_type] - hall_bookings})"
    
    try:
        booking_ids = []
        for _ in range(ticket_count):
            c.execute('''
                INSERT INTO bookings (user_email, hall, meal_type, booking_date)
                VALUES (?, ?, ?, ?)
            ''', (user_email, hall, meal_type, booking_date))
            booking_ids.append(c.lastrowid)
        conn.commit()
        print(f"Bookings inserted - IDs: {booking_ids}")
        return booking_ids, None
    except sqlite3.Error as e:
        print(f"Booking insertion failed: {str(e)}")
        return None, f"Database error: {str(e)}"
    finally:
        conn.close()

def cancel_booking(booking_id):
    conn = sqlite3.connect('bookings.db')
    c = conn.cursor()
    c.execute('DELETE FROM bookings WHERE id = ?', (booking_id,))
    conn.commit()
    conn.close()
    print(f"Booking cancelled - ID: {booking_id}")

def get_booking_counts(date, user_email):
    conn = sqlite3.connect('bookings.db')
    c = conn.cursor()
    
    halls = ['Shahidul Hall', 'Selim Hall', 'Zia Hall', 'Bangabandhu Hall']
    meal_types = ['Lunch', 'Dinner']
    counts = {}
    
    for hall in halls:
        counts[hall] = {}
        for meal_type in meal_types:
            c.execute('''
                SELECT COUNT(*) FROM bookings 
                WHERE hall = ? AND meal_type = ? AND date(booking_date) = ?
            ''', (hall, meal_type, date))
            counts[hall][meal_type] = c.fetchone()[0]
    
    c.execute('''
        SELECT hall, meal_type FROM bookings 
        WHERE user_email = ? AND date(booking_date) = ?
    ''', (user_email, date))
    user_bookings = c.fetchall()
    print(f"Booking counts - Date: {date}, User: {user_email}, Counts: {counts}, User Bookings: {user_bookings}")
    
    conn.close()
    return counts, user_bookings

def reset_bookings(date):
    conn = sqlite3.connect('bookings.db')
    c = conn.cursor()
    c.execute('DELETE FROM bookings WHERE date(booking_date) = ?', (date,))
    conn.commit()
    conn.close()
    print(f"Bookings reset for {date}")

def schedule_reset():
    now = datetime.now()
    next_day = (now + timedelta(days=1)).strftime('%Y-%m-%d')
    reset_bookings(next_day)
    print(f"Scheduled reset for {next_day}")

schedule.every().day.at("20:00").do(schedule_reset)

def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == '__main__':
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()