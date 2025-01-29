#import json
from datetime import datetime
from time import sleep
import requests, html, re
from data import  add_or_update_ticket, load_tickets, remove_ticket, load_local_viewer_id,perform_deletions
import settings
from glpi_upload import glpi_unassign_user_from_ticket, glpi_close_ticket, get_customfield_id
from glpi_utiles import header

#DOWNLOAD FROM GLPI
    
def search_latest_ticket(session_token, last_tik):
    ranga=f'0-100'
    
    params = {
        'range': ranga, 
        'sort': 2,        # Sort by ID ,by 'data' set 15
        'order': 'DESC'   
    }
    
    response = requests.get(f"{settings.Glpi_Url}/search/Ticket", headers=header(session_token), params=params)
    
    if response.status_code == 200 or response.status_code == 206 :
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

def merge_ticket_and_user_details(ticket_details, user_details, technic_id):
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
        'user_dn': user_details.get('user_dn'),
        'technic_id': str(technic_id)
    }
    return merged_details

#Not used 
"""
def get_followups(ticket_id, session_token):
    url = f"{settings.Glpi_Url}/Ticket/{ticket_id}/ITILFollowup/"
    response = requests.get(url, headers=header(session_token))
    response.raise_for_status()
    return response.json()

#Not used
def send_followup(followup_content, ticket_id, owner_id):
    payload = {"content": followup_content,
               "ticket_id": ticket_id,
               "owner_id": owner_id
               }
    response = requests.post(settings.Followup_Post_Link, json=payload)
    response.raise_for_status()
    print("followup sent")
"""
def is_ticket_open(session_token, ticket_id):  
    response = requests.get(f"{settings.Glpi_Url}/Ticket/{ticket_id}", headers=header(session_token))
    status = 6
    if response.status_code == 200:
        ticket_details = response.json()
        status = ticket_details.get('status')
        
        return status in [1, 2], status 
    else:
        print(f"Error checking ticket status: {response.status_code}")
        print(response.text)
        return False, status
"""
#Not used
def send_ticket_closure_info(ticket_id, user_id):
    payload = {
        "ticket_id": str(ticket_id),
        "user_id": str(user_id)
    }
    headers = {'Content-Type': 'application/json'}
    
    response = requests.post(settings.Close_Ticket_Post_Link, json=payload, headers=headers)
    response.raise_for_status()
    print("ticket closure sent")
"""
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

                if str(user_type) == "1" and requester == "None":
                    requester = user.get('users_id')
                
                if str(user_type) == "2":
                    if str(technician) in ["None", "8", "7", "2747", "2702", "2703", "2731", "2555", "2662", "3793"]:
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

def check_ticket_state_and_technic(session_token, ticket_id):
    assigned_to = "Other"
    state = "Open"

    is_it, state_num = is_ticket_open(session_token, ticket_id)

    if not is_it:
        state = "Closed"
    else:
        user, technic = get_assigned_users_from_ticket(session_token, ticket_id)
        if str(technic) in ["None", "8", "7", "2747", "2702", "2703", "2731", "2555", "2662", "3793"]:
            assigned_to = str(technic)

    return state, assigned_to

def is_ticket_source_xxx(session_token, ticket_id):

    try:
        ticket_details = get_ticket_details(session_token, ticket_id)
        if not ticket_details:
            print(f"Ticket {ticket_id} not found.")
            return False

        request_type_id = ticket_details.get('requesttypes_id')
        if request_type_id == 9:
            print(f"Ticket {ticket_id} source is 'xxx'.")
            return True
        else:
            #print(f"Ticket {ticket_id} source is not 'xxx'. RequestType ID is {request_type_id}.")
            return False  

    except Exception as e:
        print(f"Error while checking ticket source: {e}")
        return False

def glpi_main(tik_aid_main, session_token):
    all_details = {}
    data = {}
    try:
        tik_aid = tik_aid_main
        entities_map = settings.entities_names

        while True:
            sleeper = settings.Check_Time
            if not session_token:
                print("Session token is invalid or missing.")
                break
            #Find if new ticket and send out
            try:
                latest_ticket_id = search_latest_ticket(session_token, str(int(tik_aid) + 5))
            except Exception as e:
                print(f"Error searching for latest ticket: {e}")
                break
            
            if latest_ticket_id is None:
                print("No new tickets found, skipping iteration.")
                break

            if int(tik_aid) < latest_ticket_id:

                if int(tik_aid)+1 < latest_ticket_id:
                    if int(tik_aid)+10 > latest_ticket_id:
                        latest_ticket_id = int(tik_aid)+1
                
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
                        print("No Requester Eror")
                    if users_id_lastupdater=="None":
                        users_id_lastupdater = ticket_details.get('users_id_lastupdater')

                    last_modified = ticket_details.get('date_mod')
                    
                    print(f"Download: Technician ID {ass_technician_id}")
                    try:
                        user_details = get_user_details(session_token, users_id_lastupdater)
                    except Exception as e:
                        print(f"Error getting user details: {e}")
                        break
                        
                    merged_details = merge_ticket_and_user_details(ticket_details, user_details, ass_technician_id)
                    all_details = merged_details
                    print("New ticket downloaded.")
                        
                    add_or_update_ticket(latest_ticket_id, 1, last_modified)

                    id, entitlement = get_customfield_id(session_token, latest_ticket_id)
                    
                    data = {
                        "title": str(all_details.get('title')),
                        "contact": str(all_details.get('firstname')+" "+all_details.get('surname')), 
                        "client": str(entities_map.get(all_details.get('entities_id'))),
                        "gid": str(all_details.get('gid')),
                        "link": settings.link+str(all_details.get('id')),
                        "queue": entitlement
                    }
                    
                    hide_ticket = True
                    if str(ass_technician_id) in ["None", "8", "7", "2747", "2702", "2703", "2731", "2555", "2662", "3793"]:
                        hide_ticket = False
                        stat, num = is_ticket_open(session_token, latest_ticket_id)
                        if not stat:
                            hide_ticket = True

                    return data, hide_ticket, latest_ticket_id
                    
                else:
                    print("No ticket details available.")
            else:
                sleeper = 3  

            
            tickets = load_tickets()
            
            if tickets:
                for ticket in tickets:
                                       
                    if len(ticket) < 2:
                        print(f"Skipping ticket due to missing data: {ticket}")
                        continue  
                    ticket_number, prev_last_modified = ticket
                    last_modified_data = prev_last_modified
                    try:
                        date_format = "%Y-%m-%d %H:%M:%S"
                        tick_details = get_ticket_details(session_token, ticket_number)
                        if tick_details is None:
                            print(f"Ticket details for ticket {ticket_number} are None. Skipping...")
                            continue
                        last_modified = tick_details.get('date_mod')
                        last_modified_data =  datetime.strptime(last_modified, date_format)
                        prev_last_modified =  datetime.strptime(prev_last_modified, date_format) 
                    except Exception as e:
                        print("Error while get last modified: ")
                        continue
                    if prev_last_modified < last_modified_data: 
                        
                        local_viewer_id = load_local_viewer_id(ticket_number)
                        if not local_viewer_id or local_viewer_id == 0:
                            #print(f"No local viewer ID found for ticket {ticket_number}. Skipping...")
                            continue
                        try:
                            users_id_lastupdater, ass_technician_id = get_assigned_users_from_ticket(session_token, ticket_number)
                        except Exception as e:
                            print("No Requester Eror")
                        if users_id_lastupdater=="None":
                            users_id_lastupdater = tick_details.get('users_id_lastupdater')
                        try:
                            user_details = get_user_details(session_token, users_id_lastupdater)
                        except Exception as e:
                            print("Error getting user details: ")
                            break
                        
                        try:
                            all_details = merge_ticket_and_user_details(tick_details, user_details, ass_technician_id)

                            
                            updata_link = settings.Ticket_Local_Viewer_Link + f"/{local_viewer_id}"

                            id, entitlement = get_customfield_id(session_token, ticket_number)

                            update_data = {
                                        'title':str(all_details.get('title')),
                                        'contact': str(all_details.get('firstname')+" "+all_details.get('surname')),
                                        'client':str(entities_map.get(all_details.get('entities_id'))),
                                        'gid': str(all_details.get('gid')),
                                        'visible': '',
                                        'migacz':'',
                                        'queue': entitlement
                                    }

                            response = requests.put(updata_link, json=update_data) 
                            #response.raise_for_status()
                            if response.status_code == 200:
                                add_or_update_ticket(ticket_number, 1, last_modified)
                            else:
                                remove_ticket(ticket_number, 0)
                                perform_deletions()
                        except Exception as e:
                            print(f"Error geting sending update: {e}")
                                  
                        """
                        #Send outside new followups in observed tickets / off ?
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
                                    try:
                                        users_id_lastupdater, ass_technician_id = get_assigned_users_from_ticket(session_token, ticket_number)
                                    except Exception as e:
                                        ass_technician_id = ticket_details["users_id_lastupdater"]
                                        continue

                                    send_followup(content_cleaned, ticket_number, ass_technician_id)
                                    
                                    last_checked_id = followup_id
                                    add_or_update_ticket(ticket_number, last_checked_id)
                                except Exception as e:
                                    print(f"Error sending follow-up for ticket {ticket_number}: {e}")
                                    continue """

                        #Send info if ticked closed in GLPI  
                        try:
                            state, assigned_to = check_ticket_state_and_technic(session_token, ticket_number)
                            if state == "Closed" or assigned_to == "Other" or ticket_details.get('is_deleted') == 1:
                                print(f"Ticket {ticket_number} is closed/in progres/Other user.")
                                """
                                ticket_details = get_ticket_details(session_token, ticket_number)
                                requester, ass_technician_id = get_assigned_users_from_ticket(session_token, ticket_number)
                                if( ass_technician_id == "None"):
                                    ass_technician_id = ticket_details.get('users_id_lastupdater')
                                send_ticket_closure_info(ticket_number, ass_technician_id)
                                """
                                
                                update_data = {
                                    'title':'',
                                    'contact':'',
                                    'client':'',
                                    'gid':'',
                                    'visible': 'False',
                                    'migacz':'',
                                    'queue': entitlement
                                }
                                
                                response = requests.put(updata_link, json=update_data)
                                #response.raise_for_status()
                                if response.status_code == 200:
                                    is_it, state_num = is_ticket_open(session_token, ticket_number)
                                                                
                                    if state_num > 4 or ticket_details.get('is_deleted') == 1:
                                        remove_ticket(ticket_number, 72)
                                else:
                                    remove_ticket(ticket_number, 0)
                                    perform_deletions()

                            elif assigned_to != "Other":
                                update_data = {
                                    'title':'',
                                    'contact':'',
                                    'client':'',
                                    'gid':'',
                                    'visible': 'True',
                                    'migacz':'',
                                    'queue': entitlement
                                }

                                response = requests.put(updata_link, json=update_data)
                                #response.raise_for_status()
                                if response.status_code != 200:
                                    remove_ticket(ticket_number, 0)
                                    perform_deletions()
                                
                        except Exception as e:
                            print(f"Error checking or closing ticket {ticket_number}: {e}")
                            continue
 
                        #Send ticket outside if xxx source selected
                        try:
                            if is_ticket_source_xxx(session_token, ticket_number):

                                ticket_details = get_ticket_details(session_token, ticket_number)
                                try:
                                    requester_id, technician_id = get_assigned_users_from_ticket(session_token, ticket_number)
                                    user_details = get_user_details(session_token, requester_id)
                                except Exception as e:
                                    print("Error getting users details(is source xxx)")
                                    user_details = get_user_details(session_token, 2662)
                                    technician_id = 2662
                                
                                all_info = merge_ticket_and_user_details(ticket_details, user_details, technician_id)

                                try: 
                                    response = glpi_unassign_user_from_ticket(session_token, ticket_number, requester_id) 
                                    response = glpi_close_ticket(session_token, ticket_number, "Ticket Forwarded")
                                except Exception as e:
                                    print(f"Error occured: unassign/close ticket: {response}")

                                try:
                                    if all_info:  
                                        print(f"Ticket download result: {all_info.get('title')}")
                                        
                                        response = requests.post(settings.Ticket_Post_Link, json=all_info)
                                        response.raise_for_status()
                                        print("New ticket sent successfully.")

                                except Exception as e:
                                    print(f"Error while downloading or sending the ticket XXX (): || ")
                                    print(f"Error: {str(e)}")
                                
                        except Exception as e:
                            print(f"Error checking requestype of ticket {ticket_number}: ")

            sleep(sleeper)

    except Exception as e:
        print(f"Main GLPI Connector ERROR: {e}")

    return data, False, 1
