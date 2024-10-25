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

def get_user_id_and_unit_by_gid(session_token, gid):
    search_url = f"{settings.Glpi_Url}/search/User"
    
    params = {
        "criteria[0][field]": 1,  
        "criteria[0][searchtype]": "contains",  
        "criteria[0][value]": gid, 
        "forcedisplay[0]": 2,  
        "forcedisplay[1]": 1
    }

    response = requests.get(search_url, headers=header(session_token), params=params)

    if response.status_code == 200:
        result = response.json()

        if result.get("data"):
            user_data = result["data"][0]
            user_id = user_data.get("2") 
            return user_id
        else:
            print(f"No user found with GID: {gid}")
            return None
    else:
        print(f"Error fetching user data: {response.status_code}")
        print(response.text)
        return None

def glpi_create_ticket(session_token, title, description, assigned_user_gid, assigned_technic_gid, unit_id, close_after):
    assigned_user_id = get_user_id_and_unit_by_gid(session_token, assigned_user_gid)
    assigned_technic_id = assigned_technic_gid #get_user_id_and_unit_by_gid(session_token, assigned_technic_gid)
    ticket_data = {
        "input": {
            "name": title,
            "content": description,
            "requesttypes_id": 1,  
            "urgency": 3,  
            "impact": 3,  
            "priority": 3,  
            "type": 1,  
            "entities_id": unit_id  
        }
    }

    response = requests.post(f"{settings.Glpi_Url}/Ticket", headers=header(session_token), json=ticket_data)

    if response.status_code == 201:
        ticket_info = response.json()
        ticket_id = ticket_info.get("id") 

        if not assigned_user_id:
            print(f"User with GID {assigned_user_gid} not found.")
        else:
            print(assigned_user_id)

        try:
            assign_response = glpi_assign_user_to_ticket(session_token, ticket_id, assigned_user_id, 1)
        except:
            print("Ticket created but failed to assign user")
        try:
            assign_response = glpi_assign_user_to_ticket(session_token, ticket_id, 3793, 2)
            assign_response2 = glpi_assign_user_to_ticket(session_token, ticket_id, assigned_technic_id, 2)
            #print(f"Technician assigned successfully to ticket {ticket_id}.")
            if close_after == "Yes":
                response_close = glpi_close_ticket(session_token, ticket_id, description)

            return response.json()
        except Exception as e:
            print( f"Ticket created but failed to assign technician and close: {str(e)}")
    else:
        print(f"Error creating ticket: {response.status_code} - {response.text}")

def glpi_assign_user_to_ticket(session_token, ticket_id, user_id, type):
    data = {
        "input": {
            "tickets_id": ticket_id,
            "users_id": user_id,
            "type": str(type),  
            "use_notification": "1"  
        }
    }

    response = requests.post(f"{settings.Glpi_Url}/Ticket_User", headers=header(session_token), json=data)

    if response.status_code == 201:
        return response.json()
    else:
        print(f"Error assigning technician: {response.status_code} - {response.text}")

def glpi_close_ticket(session_token, ticket_id, content):

    solution_content="<p>Zgłoszenie zamknięto</p>"

    data = {
        "input": {
            "status": 6,  
            "solution": solution_content,  
            "content": content,  
            "solutiontypes_id": 3,  
            "solutiontemplates_id": 5  
        }
    }

    response = requests.put(
        f"{settings.Glpi_Url}/Ticket/{ticket_id}", 
        headers=header(session_token), 
        json=data
    )

    if response.status_code == 200:
        print(f"Ticket {ticket_id} was closed succesfully.")
        return response.json()
    else:
        print(f"Error closing ticket {ticket_id}: {response.status_code} - {response.text}")
        response.raise_for_status()