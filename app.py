from flask import Flask, request, redirect, url_for, render_template, session, flash, make_response, jsonify
from booking_system import init_db, register_user, authenticate_user, book_meal, cancel_booking, get_booking_counts, reset_bookings
from datetime import datetime, timedelta
import sqlite3
import random

app = Flask(__name__)
app.secret_key = 'your-secret-key'

init_db()

@app.route('/', methods=['GET', 'POST'])
def signin():
    if 'user_email' in session:
        return redirect(url_for('booking'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        roll = request.form.get('roll')
        password = request.form.get('password')
        
        if not roll.isdigit() or len(roll) != 7:
            flash('Roll number must be exactly 7 digits')
        else:
            user = authenticate_user(email, roll, password)
            if user:
                session['user_email'] = email
                session['username'] = user[1]
                session['roll'] = user[2]
                print(f"User signed in: {email}")
                return redirect(url_for('booking'))
            else:
                flash('Invalid email, roll number, or password')
    
    return render_template('signin.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if 'user_email' in session:
        return redirect(url_for('booking'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        username = request.form.get('username')
        roll = request.form.get('roll')
        password = request.form.get('password')
        
        if not roll.isdigit() or len(roll) != 7:
            flash('Roll number must be exactly 7 digits')
        elif register_user(email, username, roll, password):
            flash('Registration successful! Please sign in.')
            return redirect(url_for('signin'))
        else:
            flash('Email already registered or invalid roll number')
    
    return render_template('signup.html')

@app.route('/booking', methods=['GET', 'POST'])
def booking():
    if 'user_email' not in session:
        flash('Please sign in to book a meal')
        return redirect(url_for('signin'))
    
    now = datetime.now()
    current_time = now.hour * 100 + now.minute
    booking_date = (now + timedelta(days=1)).date().strftime('%Y-%m-%d') if 2000 <= current_time or current_time < 800 else now.date().strftime('%Y-%m-%d')
    
    if request.method == 'POST':
        hall = request.form.get('hall')
        meal_type = request.form.get('meal_type')
        booking_date_form = request.form.get('booking_date')
        try:
            ticket_count = int(request.form.get('ticket_count'))
        except (ValueError, TypeError):
            ticket_count = 0
        print(f"Booking attempt - Hall: {hall}, Meal Type: {meal_type}, Date: {booking_date_form}, Tickets: {ticket_count}, User: {session['user_email']}")
        
        if not (hall and meal_type and booking_date_form and ticket_count):
            flash('Please fill in all fields')
            return render_template('booking.html', counts={}, username=session.get('username'), booking_date=booking_date)
        
        if meal_type not in ['Lunch', 'Dinner']:
            flash('Invalid meal type selected')
            return render_template('booking.html', counts={}, username=session.get('username'), booking_date=booking_date)
        
        if ticket_count < 1 or ticket_count > 5:
            flash('Number of tickets must be between 1 and 5')
            return render_template('booking.html', counts={}, username=session.get('username'), booking_date=booking_date)
        
        try:
            datetime.strptime(booking_date_form, '%Y-%m-%d')
        except ValueError:
            flash('Invalid date format. Use YYYY-MM-DD.')
            return render_template('booking.html', counts={}, username=session.get('username'), booking_date=booking_date)
        
        valid_halls = ['Shahidul Hall', 'Selim Hall', 'Zia Hall', 'Bangabandhu Hall']
        if hall not in valid_halls:
            flash('Invalid hall selected')
            return render_template('booking.html', counts={}, username=session.get('username'), booking_date=booking_date)
        
        selected_date = datetime.strptime(booking_date_form, '%Y-%m-%d')
        prev_day = selected_date - timedelta(days=1)
        start_window = prev_day.replace(hour=20, minute=0, second=0, microsecond=0)
        end_window = selected_date.replace(hour=8, minute=0, second=0, microsecond=0)
        if not (start_window <= now <= end_window):
            flash(f'Bookings for {booking_date_form} are only allowed from 8 PM the previous day to 8 AM.')
            return render_template('booking.html', counts={}, username=session.get('username'), booking_date=booking_date)
        
        booking_ids, error = book_meal(session['user_email'], hall, meal_type, booking_date_form, ticket_count)
        print(f"Book meal result - IDs: {booking_ids}, Error: {error}")
        if booking_ids:
            slip_number = str(random.randint(100000, 999999))
            session['latest_booking'] = {
                'hall': hall,
                'meal_type': meal_type,
                'booking_ids': booking_ids,
                'booking_date': booking_date_form,
                'ticket_count': ticket_count,
                'slip_number': slip_number
            }
            print(f"Booking saved in session: {session['latest_booking']}")
            
            conn = sqlite3.connect('bookings.db')
            c = conn.cursor()
            c.execute('SELECT * FROM bookings WHERE id IN ({})'.format(','.join('?' * len(booking_ids))), booking_ids)
            booking_records = c.fetchall()
            print(f"Booking records in database: {booking_records}")
            conn.close()
            
            return redirect(url_for('payment'))
        else:
            flash(error or f'Failed to book {ticket_count} {meal_type} ticket(s) for {hall} on {booking_date_form}')
    
    counts, user_bookings = get_booking_counts(booking_date, session['user_email'])
    print(f"Booking page - Counts: {counts}, User Bookings: {user_bookings}")
    response = make_response(render_template('booking.html', counts=counts, username=session.get('username'), booking_date=booking_date))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response

@app.route('/get_counts', methods=['GET'])
def get_counts():
    if 'user_email' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    date = request.args.get('date', datetime.now().date().strftime('%Y-%m-%d'))
    counts, user_bookings = get_booking_counts(date, session['user_email'])
    max_tickets = 250
    for hall in counts:
        counts[hall]['LunchRemaining'] = max_tickets - counts[hall]['Lunch']
        counts[hall]['DinnerRemaining'] = max_tickets - counts[hall]['Dinner']
    user_booking_count = len(user_bookings)
    print(f"Get counts - Date: {date}, Counts: {counts}, User Bookings: {user_booking_count}")
    return jsonify({'counts': counts, 'userBookings': user_booking_count})

@app.route('/reset_bookings', methods=['POST'])
def reset_bookings_route():
    if 'user_email' not in session:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    date = request.args.get('date')
    try:
        reset_bookings(date)
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/payment', methods=['GET', 'POST'])
def payment():
    if 'user_email' not in session:
        flash('Please sign in to make a payment')
        return redirect(url_for('signin'))
    
    if 'latest_booking' not in session:
        flash('No booking found. Please book a meal first.')
        return redirect(url_for('booking'))
    
    booking = session['latest_booking']
    hall = booking.get('hall')
    meal_type = booking.get('meal_type')
    booking_ids = booking.get('booking_ids')
    ticket_count = booking.get('ticket_count')
    booked_date = booking.get('booking_date')
    slip_number = booking.get('slip_number')
    
    if not (hall and meal_type and booking_ids and ticket_count and booked_date and slip_number):
        flash('Invalid booking data. Please book again.')
        session.pop('latest_booking', None)
        return redirect(url_for('booking'))
    
    print(f"Payment route - Session latest_booking: {booking}")
    
    conn = sqlite3.connect('bookings.db')
    c = conn.cursor()
    c.execute('SELECT hall, meal_type, booking_date FROM bookings WHERE id IN ({})'.format(','.join('?' * len(booking_ids))), booking_ids)
    booking_records = c.fetchall()
    print(f"Payment route - Booking records for IDs {booking_ids}: {booking_records}")
    
    if not booking_records:
        flash(f'No bookings found for IDs {booking_ids}. Please book again.')
        session.pop('latest_booking', None)
        conn.close()
        return redirect(url_for('booking'))
    
    total_cost = ticket_count * 50
    halls = hall
    
    print(f"Payment route - User: {session['user_email']}, Meal Type: {meal_type}, Booked Date: {booked_date}, Ticket Count: {ticket_count}, Halls: {halls}, Total Cost: {total_cost}, Slip Number: {slip_number}")
    
    if request.method == 'POST':
        payment_method = request.form.get('payment_method')
        print(f"Payment attempt - Method: {payment_method}, Booking IDs: {booking_ids}")
        if payment_method == 'Cancel':
            try:
                for booking_id in booking_ids:
                    cancel_booking(booking_id)
                print(f"Cancelled booking IDs: {booking_ids}")
                flash('Booking cancelled successfully')
            except Exception as e:
                flash(f'Error cancelling bookings: {str(e)}')
            session.pop('latest_booking', None)
            conn.close()
            return redirect(url_for('booking'))
        elif payment_method in ['Pay with bKash', 'Pay with Rocket']:
            try:
                flash(f'Payment processed successfully with {payment_method}. Ready for new booking.')
                session.pop('latest_booking', None)
                conn.close()
                response = make_response(redirect(url_for('booking')))
                response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
                return response
            except Exception as e:
                flash(f'Error processing payment: {str(e)}')
        else:
            flash('Invalid payment method selected')
    
    conn.close()
    response = make_response(render_template('payment.html', 
                                           booking=booking,
                                           username=session.get('username'),
                                           roll=session.get('roll'),
                                           booking_date=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                           meal_type=meal_type,
                                           ticket_count=ticket_count,
                                           halls=halls,
                                           total_cost=total_cost,
                                           slip_number=slip_number))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response

@app.route('/logout')
def logout():
    session.pop('user_email', None)
    session.pop('username', None)
    session.pop('roll', None)
    session.pop('latest_booking', None)
    flash('Logged out successfully')
    return redirect(url_for('signin'))

if __name__ == '__main__':
    app.run(debug=True)