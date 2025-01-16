import sqlite3
from datetime import datetime, timedelta
import settings
import requests

def init_database():
    # Connect database (create if doesnt exist)
    conn = sqlite3.connect('tickets.db')
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tickets (
        ticket_number TEXT PRIMARY KEY,
        last_checked_id INTEGER,
        delete_time TIMESTAMP,
        local_viewer_id INTEGER,
        last_modified STRING
    )
    ''')

    conn.commit()
    return conn, cursor


def add_or_update_ticket(ticket_number, last_checked_id, last_modified):
    conn, cursor = init_database()

    cursor.execute('''
        INSERT INTO tickets (ticket_number, last_checked_id, last_modified)
        VALUES (?, ?, ?)
        ON CONFLICT(ticket_number) DO UPDATE SET 
            last_checked_id = ?,
            last_modified = ?
    ''', (ticket_number, last_checked_id, last_modified, last_checked_id, last_modified))

    conn.commit()
    print(f"SQL: Ticket {ticket_number} added/updated - watch list")
    conn.close()

def add_local_viewer_id_ticket(ticket_number, local_viewer_id):
    conn, cursor = init_database()

    cursor.execute('''
        INSERT INTO tickets (ticket_number, local_viewer_id)
        VALUES (?, ?)
        ON CONFLICT(ticket_number)
        DO UPDATE SET local_viewer_id=excluded.local_viewer_id
        ''', (ticket_number, local_viewer_id))

    conn.commit()
    print(f"SQL: Ticket {ticket_number} TV ID added - watch list")
    conn.close()

def load_local_viewer_id(ticket_number):
    conn, cursor = init_database()
    cursor.execute('''SELECT local_viewer_id FROM tickets WHERE ticket_number = ?''', (ticket_number,))
    reta = cursor.fetchone()  
    conn.close()
    
    if reta:  
        return reta[0]  
    else:
        return None  

def load_tickets():
    conn, cursor = init_database()
    cursor.execute('SELECT ticket_number, last_modified FROM tickets')
    reta = cursor.fetchall()
    conn.close()
    return reta

def remove_ticket(ticket_number, when=72):
    #add expire date to ticket
    conn, cursor = init_database()
    if when == 0:
        delete_time = datetime.now()
    else:
        delete_time = datetime.now() + timedelta(hours=when)  # when delete? 72h from now
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
    # Somewhere can be run once/twice a day
    conn, cursor = init_database()
    current_time = datetime.now()
    try:
        loc_viewers = cursor.execute('SELECT local_viewer_id FROM tickets WHERE delete_time <= ?', (current_time,)).fetchall()
        for loc_viewer in loc_viewers:
            l_id = loc_viewer[0]  
            
            response = requests.delete(settings.Ticket_Local_Viewer_Link + "/"+str(l_id), json={})
            response.raise_for_status()
    except Exception as e:
        print('ERROR PERFORM DELETE from local viewer:', e)
    
    cursor.execute('DELETE FROM tickets WHERE delete_time <= ?', (current_time,))
    conn.commit()
    conn.close()
    print(f"SQL: Scheduled deletions performed at {current_time}.")