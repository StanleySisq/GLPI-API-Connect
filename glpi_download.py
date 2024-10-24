#import json
from time import sleep
import requests, html, re
from data import  add_or_update_ticket, load_tickets, remove_ticket
import settings

    
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
        'sort': 2,        # Sort by ID ,by 'data' set 15
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

def send_followup(followup_content, ticket_id, owner_id):
    payload = {"content": followup_content,
               "ticket_id": ticket_id,
               "owner_id": owner_id
               }
    response = requests.post(settings.Followup_Post_Link, json=payload)
    response.raise_for_status()
    print("followup sent")

def is_ticket_open(session_token, ticket_id):  
    response = requests.get(f"{settings.Glpi_Url}/Ticket/{ticket_id}", headers=header(session_token))
    
    if response.status_code == 200:
        ticket_details = response.json()
        status = ticket_details.get('status')
        
        return status in [1, 2] 
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

def get_assigned_users_from_ticket(session_token, ticket_id):

    url = f"{settings.Glpi_Url}/Ticket/{ticket_id}/Ticket_User"

    response = requests.get(url, headers=header(session_token))

    if response.status_code == 200:
        result = response.json() 

        if result:
            requester = "None"
            technician = "None"

            for user in result:
                user_type = user.get('type')  

                # (requester)
                if str(user_type) == "1" and requester == "None":
                    requester = user.get('users_id')
                
                # (technician)
                if str(user_type) == "2" and technician == "None":
                    technician = user.get('users_id')

            #print(technician)
            #print(requester)
            return requester, technician
        else:
            print(f"No users found for ticket ID {ticket_id}.")
            return "None", "None"
    else:
        print(f"Error fetching assigned users: {response.status_code} - {response.text}")
        return "None", "None"

def glpi_main(tik_aid_main, session_token):
    all_details = {}
    try:
        tik_aid = tik_aid_main

        while True:
            sleeper = settings.Check_Time
            if not session_token:
                print("Session token is invalid or missing.")
                break
            
            try:
                latest_ticket_id = search_latest_ticket(session_token, str(int(tik_aid) + 5))
            except Exception as e:
                print(f"Error searching for latest ticket: {e}")
                break
            
            if latest_ticket_id is None:
                print("No new tickets found, skipping iteration.")
                break

            if int(tik_aid) < latest_ticket_id:
                try:
                    with open(settings.Id_File, "w") as file:
                        file.write(str(latest_ticket_id))
                except Exception as e:
                    print(f"Error writing to file: {e}")
                    break
                
                try:
                    ticket_details = get_ticket_details(session_token, latest_ticket_id)
                except Exception as e:
                    print(f"Error getting ticket details: {e}")
                    break
                
                if ticket_details:
                    try:
                        users_id_lastupdater, ass_technician_id = get_assigned_users_from_ticket(session_token, latest_ticket_id)
                    except Exception as e:
                        print("No Requester")
                    if users_id_lastupdater=="None":
                        users_id_lastupdater = ticket_details.get('users_id_lastupdater')
                    
                    if str(ass_technician_id) in ["None", "8", "7", "2747", "2702", "2703", "2731", "2555", "2662", "3793"]:
                        try:
                            user_details = get_user_details(session_token, users_id_lastupdater)
                        except Exception as e:
                            print(f"Error getting user details: {e}")
                            break
                        
                        merged_details = merge_ticket_and_user_details(ticket_details, user_details)
                        all_details = merged_details
                        print("New ticket downloaded.")
                        
                        add_or_update_ticket(latest_ticket_id, 1)
                        break
                    else:
                        print("   Not our ticket. Its already assigned!!")
                else:
                    print("No ticket details available.")
            else:
                sleeper = 3  

            tickets = load_tickets()
            
            if tickets:
                for ticket in tickets:
                    ticket_number, last_checked_id = ticket
                    try:
                        followups = get_followups(ticket_number, session_token)
                    except Exception as e:
                        print(f"Error getting follow-ups for ticket {ticket_number}: {e}")
                        continue 
                    
                    for followup in followups:
                        followup_id = int(followup["id"])
                        
                        if followup_id > last_checked_id:
                            try:
                                clean = re.compile('<.*?>')
                                content_cleaned = re.sub(clean, ' ', html.unescape(followup["content"]))
                                send_followup(content_cleaned, ticket_number, ticket_details["users_id_lastupdater"])
                                
                                last_checked_id = followup_id
                                add_or_update_ticket(ticket_number, last_checked_id)
                            except Exception as e:
                                print(f"Error sending follow-up for ticket {ticket_number}: {e}")
                                continue 

                    try:
                        if not is_ticket_open(session_token, ticket_number):
                            print(f"Ticket {ticket_number} is closed.")
                            ticket_details = get_ticket_details(session_token, ticket_number)
                            users_id_lastupdater = ticket_details.get('users_id_lastupdater')
                            send_ticket_closure_info(ticket_number, users_id_lastupdater)
                            remove_ticket(ticket_number, 4)
                    except Exception as e:
                        print(f"Error checking or closing ticket {ticket_number}: {e}")
                        continue

            sleep(sleeper)

    except Exception as e:
        print(f"Main GLPI Connector ERROR: {e}")

    return all_details
