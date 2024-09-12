import sqlite3
from datetime import datetime, timedelta

def init_database():
    # Connect database (create if doesnt exist)
    conn = sqlite3.connect('tickets.db')
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tickets (
        ticket_number TEXT PRIMARY KEY,
        last_checked_id INTEGER,
        delete_time TIMESTAMP
    )
    ''')

    conn.commit()
    return conn, cursor

def add_or_update_ticket(ticket_number, last_checked_id):
    conn, cursor = init_database()

    cursor.execute('''
        INSERT INTO tickets (ticket_number, last_checked_id)
        VALUES (?, ?)
        ON CONFLICT(ticket_number)
        DO UPDATE SET last_checked_id=excluded.last_checked_id
        ''', (ticket_number, last_checked_id))

    conn.commit()
    print(f"SQL: Ticket {ticket_number} added/updated - watch list")
    conn.close()

def load_tickets():
    conn, cursor = init_database()
    cursor.execute('SELECT ticket_number, last_checked_id FROM tickets WHERE delete_time IS NULL')
    reta = cursor.fetchall()
    conn.close()
    return reta

def remove_ticket(ticket_number, when=48):
    #add expire date to ticket
    conn, cursor = init_database()
    delete_time = datetime.now() + timedelta(hours=when)  # when delete? 48h from now
    try:
        cursor.execute('''
            UPDATE tickets 
            SET delete_time = ? 
            WHERE ticket_number = ?
            ''', (delete_time, ticket_number))
        conn.commit()
    except:
        cursor.execute('''
        INSERT INTO tickets (ticket_number, last_checked_id, delete_time)
        VALUES (?, ?, ?)
        ON CONFLICT(ticket_number)
        DO UPDATE SET last_checked_id=excluded.last_checked_id
        ''', (ticket_number, 1, delete_time))
        conn.commit()

    print(f"SQL: Ticket {ticket_number} scheduled for deletion at {delete_time}.")
    conn.close()

def perform_deletions():
    # Somewhere can be run once/twice a day - now add_solution()
    conn, cursor = init_database()
    current_time = datetime.now()
    cursor.execute('DELETE FROM tickets WHERE delete_time <= ?', (current_time,))
    conn.commit()
    conn.close()
    print(f"SQL: Scheduled deletions performed at {current_time}.")