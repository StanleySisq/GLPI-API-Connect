#import json
from time import sleep
import requests, html, re
from data import  add_or_update_ticket, load_tickets, remove_ticket
import settings


def init_session():

    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'user_token ' + settings.Api_Token,
        'App-Token': settings.App_Token
    }
    
    response = requests.get(f"{settings.Glpi_Url}/initSession", headers=headers)
    
    if response.status_code == 200:
        session_token = response.json()['session_token']
        return session_token
    else:
        print(f"Cannot initialize sesion: {response.status_code}")
        print(response.text)
        return None
    
def header(session_token):
    headers = {
        'Content-Type': 'application/json',
        'Session-Token': session_token,
        'App-Token': settings.App_Token
    }
    return headers

def search_latest_ticket(session_token, last_tik):
    ranga=f'0-{last_tik}'
    
    params = {
        'range': ranga, 
        'sort': 15,        # Sort by 'data'
        'order': 'DESC'   
    }
    
    response = requests.get(f"{settings.Glpi_Url}/search/Ticket", headers=header(session_token), params=params)
    
    if response.status_code == 200:
        tickets = response.json()
        if 'data' in tickets and tickets['data']:
            latest_ticket = tickets['data'][0]  # Download newest ticket
            latest_ticket_id = latest_ticket.get('2')  # Download ID ticket (pole '2')
            return latest_ticket_id
        else:
            print("No avaible tickets.")
            return None
    else:
        print(f"Error searching tickets : {response.status_code}")
        #print(response.text)
        return int(last_tik)-6
    
def get_ticket_details(session_token, ticket_id):
    
    response = requests.get(f"{settings.Glpi_Url}/Ticket/{ticket_id}", headers=header(session_token))
    
    if response.status_code == 200:
        ticket_details = response.json()
        return ticket_details
    else:
        print(f"Error extracting tickets details: {response.status_code}")
        print(response.text)
        return None

def get_user_details(session_token, user_id):
    
    response = requests.get(f"{settings.Glpi_Url}/User/{user_id}", headers=header(session_token))
    
    if response.status_code == 200:
        user_details = response.json()
        return user_details
    else:
        print(f"Error downloading user details: {response.status_code}")
        print(response.text)
        return None

def merge_ticket_and_user_details(ticket_details, user_details):
    clean = re.compile('<.*?>')
    merged_details = {
        'id': ticket_details.get('id'),
        'entities_id': ticket_details.get('entities_id'),
        'title': ticket_details.get('name'),
        'users_id_lastupdater': ticket_details.get('users_id_lastupdater'),
        'content': re.sub(clean, ' ', html.unescape(ticket_details.get('content'))),
        'priority': ticket_details.get('priority'),
        'gid': user_details.get('name'),
        'surname': user_details.get('realname'),
        'firstname': user_details.get('firstname'),
        'phone': user_details.get('phone'),
        'user_dn': user_details.get('user_dn')
    }
    return merged_details

def get_followups(ticket_id, session_token):
    url = f"{settings.Glpi_Url}/Ticket/{ticket_id}/ITILFollowup/"
    response = requests.get(url, headers=header(session_token))
    response.raise_for_status()
    return response.json()

def send_followup(followup_content, ticket_id):
    payload = {"content": followup_content,
               "ticket_id": ticket_id}
    response = requests.post(settings.Followup_Post_Link, json=payload)
    response.raise_for_status()
    print("followup sent")

def is_ticket_open(session_token, ticket_id):  
    response = requests.get(f"{settings.Glpi_Url}/Ticket/{ticket_id}", headers=header(session_token))
    
    if response.status_code == 200:
        ticket_details = response.json()
        status = ticket_details.get('status')
        return status == 1
    else:
        print(f"Error checking ticket status: {response.status_code}")
        print(response.text)
        return False  


def send_ticket_closure_info(ticket_id, user_id):
    payload = {
        "ticket_id": str(ticket_id),
        "user_id": str(user_id)
    }
    headers = {'Content-Type': 'application/json'}
    
    response = requests.post(settings.Close_Ticket_Post_Link, json=payload, headers=headers)
    response.raise_for_status()
    print("ticket closure sent")

def glpi_main(tik_aid):
    all_details = {}
    session_token = init_session()
    try:
        while True:
            sleeper = settings.Check_Time
            # New tickets
            if session_token:
                latest_ticket_id = search_latest_ticket(session_token, str(int(tik_aid) + 5))
                                                        
                if int(tik_aid) < latest_ticket_id:
                    with open(settings.Id_File, "w") as file:
                        file.write(str(latest_ticket_id))

                    if latest_ticket_id:
                        ticket_details = get_ticket_details(session_token, latest_ticket_id)

                        if ticket_details:
                            users_id_lastupdater = ticket_details.get('users_id_lastupdater')

                            if users_id_lastupdater:
                                user_details = get_user_details(session_token, users_id_lastupdater)

                                merged_details = merge_ticket_and_user_details(ticket_details, user_details)

                                all_details = merged_details
                                print("New ticket Downloaded")
                                add_or_update_ticket(latest_ticket_id, 1)
                                break
                            else:
                                print("No users_id_lastupdater in ticket details.")
                        else:
                            print("Can't download ticket details.")
                    else:
                        print("Can't find newest ticket")
                elif(latest_ticket_id < int(tik_aid)):
                    tik_nas=int(tik_aid)+1
                    with open(settings.Id_File, "w") as file:
                        file.write(str(tik_nas))
                    print("Searching for other tickets...")
                    sleeper = 2
                    break
            else:
                print("Session init error.")
                break

            # New messages
            tickets = load_tickets()

            if len(tickets) > 0:
                for ticket in tickets:
                    ticket_number, last_checked_id = ticket 
                    followups = get_followups(ticket_number, session_token)
                    for followup in followups:
                        followup_id = int(followup["id"])
                        if followup_id > last_checked_id:
                            clean = re.compile('<.*?>')
                            send_followup(re.sub(clean, ' ', html.unescape(followup["content"])), ticket_number)
                            last_checked_id = followup_id
                            add_or_update_ticket(ticket_number, last_checked_id)

                    #check if closed
                    if not is_ticket_open(session_token, ticket_number):
                        print(f"Ticket {ticket_number} is closed.")
                        ticket_details = get_ticket_details(session_token, ticket_number)
                        users_id_lastupdater = ticket_details.get('users_id_lastupdater')
                        send_ticket_closure_info(ticket_number, users_id_lastupdater)
                        remove_ticket(ticket_number, 4)    
            sleep(sleeper)

    except Exception as e:
        print(f"Main GLPI ERROR: {e}")

    return all_details
