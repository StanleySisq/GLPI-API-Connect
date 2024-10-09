import requests
from glpi_download import header
from data import remove_ticket, perform_deletions
import settings

def glpi_add_solution(ticket_id, solution_content, session_token):
    try:
        remove_ticket(ticket_id)
        perform_deletions()
    except Exception as e:
        print(f"SQL Error: {e}")

    data = {
    "input": {
        "items_id": ticket_id,  
        "content": solution_content,  
        "solutiontypes_id": 2,  
        "itemtype": "Ticket"  
        }
    }
    response = requests.post(f"{settings.Glpi_Url}/ITILSolution/", headers=header(session_token), json=data)
    #print(response)
    response.raise_for_status()
    return response.json()

def glpi_add_followup(ticket_id, followup_content, session_token):
    data = {
        "input": {
            "items_id": ticket_id,  
            "content": followup_content,  
            "itemtype": "Ticket"  
        }
    }
    response = requests.post(f"{settings.Glpi_Url}ITILFollowup/", headers=header(session_token), json=data)
    response.raise_for_status()  # check HTTP
    return response.json()

def glpi_add_task_to_ticket(ticket_id, task_content, duration, session_token):
    if not session_token:
        raise Exception("Cannot initialize sesion")

    task_data = {
        "input": {
            "tickets_id": ticket_id,
            "content": task_content,
            "users_id": 3793,
            "taskcategories_id": 1,
            "state": 2,  #  (2 = Donee)
            "actiontime": duration  # in secondes
        }
    }

    response = requests.post(f"{settings.Glpi_Url}TicketTask", headers=header(session_token), json=task_data)

    if response.status_code == 201:  
        return response.json()
    else:
        raise Exception(f"Error adding tasks: {response.status_code} - {response.text}")

def get_user_id_by_email(session_token, email):
    search_url = f"{settings.Glpi_Url}/search/User"
    
    params = {
        "criteria[0][field]": 5,  
        "criteria[0][searchtype]": "equals", 
        "criteria[0][value]": email,
        "forcedisplay[0]": 2,  # "2" is user ID in GLPI
        "forcedisplay[1]": 9,  # "9" is user e-mail adress
    }

    response = requests.get(search_url, headers=header(session_token), params=params)

    if response.status_code == 200:
        result = response.json()

        if result.get("data"):
            user_id = result["data"][0]["2"]  # Take user ID
            return user_id
        else:
            print("No user found with this email.")
            return None
    else:
        print(f"Error fetching user data: {response.status_code}")
        print(response.text)
        return None

def glpi_create_ticket(session_token, title, description, assigned_user_email, assigned_technic_id):
    assigned_user_id = get_user_id_by_email(session_token, assigned_user_email)
    
    if not assigned_user_id:
        raise Exception(f"User with email {assigned_user_email} not found.")

    ticket_data = {
        "input": {
            "name": title,
            "content": description,
            "requesttypes_id": 2,  # 2 is request  1 is incident
            "urgency": 3,  # (1-5)
            "impact": 3,  # (1-5)
            "priority": 3,  #(1-5)
            "type": 2,  # 1 is incident, 2 is request
            "users_id_recipient": assigned_user_id  
        }
    }

    response = requests.post(f"{settings.Glpi_Url}/Ticket", headers=header(session_token), json=ticket_data)

    if response.status_code == 201:
        ticket_info = response.json()
        ticket_id = ticket_info.get("id") 

        if ticket_id:
            print(f"Ticket created successfully with ID: {ticket_id}")

            try:
                assign_response = glpi_assign_technician_to_ticket(session_token, ticket_id, assigned_technic_id)
                print(f"Technician assigned successfully to ticket {ticket_id}.")
                return {
                    "ticket": ticket_info,
                    "technician_assignment": assign_response
                }
            except Exception as e:
                raise Exception(f"Ticket created but failed to assign technician: {str(e)}")
        else:
            raise Exception("Ticket created but ID not found in response.")
    else:
        raise Exception(f"Error creating ticket: {response.status_code} - {response.text}")
    
def glpi_assign_technician_to_ticket(session_token, ticket_id, technician_user_id):
    data = {
        "input": {
            "itemtype": "Ticket",  
            "items_id": ticket_id, 
            "users_id": technician_user_id,  
            "type": 2  # 2 means "Technician"
        }
    }

    response = requests.post(f"{settings.Glpi_Url}/Ticket_User", headers=header(session_token), json=data)

    if response.status_code == 201:
        return response.json()
    else:
        raise Exception(f"Error assigning technician: {response.status_code} - {response.text}")