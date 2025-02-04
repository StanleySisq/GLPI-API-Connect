import os
import requests
from glpi_utiles import header
from data import remove_ticket, perform_deletions
import settings
import json
import mimetypes
import base64

#ADD CHANGE OR STH IN GLPI

def glpi_add_solution(ticket_id, solution_content, session_token, technic_id):
    try:
        remove_ticket(ticket_id)
        perform_deletions()
    except Exception as e:
        print(f"SQL Error: {e}")
    try:
        respona = glpi_assign_user_to_ticket(session_token, ticket_id, 3793, 2)
        respona = glpi_assign_user_to_ticket(session_token, ticket_id, technic_id, 2)
    except Exception as e:
        print(f"Cannot assign technic to ticket {ticket_id}, technic {technic_id}")    

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
    response = requests.post(f"{settings.Glpi_Url}/ITILFollowup/", headers=header(session_token), json=data)
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

    response = requests.post(f"{settings.Glpi_Url}/TicketTask", headers=header(session_token), json=task_data)

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

def glpi_create_ticket(session_token, title, description, assigned_user_gid, assigned_technic_gid, unit_id, close_after, tick_type):
    assigned_user_id = get_user_id_and_unit_by_gid(session_token, assigned_user_gid)
    assigned_technic_id = assigned_technic_gid #get_user_id_and_unit_by_gid(session_token, assigned_technic_gid)
    if tick_type == "Wniosek":
        tick_type = 2
    else:
        tick_type = 1
    
    ticket_data = {
        "input": {
            "name": title,
            "content": description,
            "requesttypes_id": 1,  
            "urgency": 3,  
            "impact": 3,  
            "priority": 3,  
            "type": tick_type,  
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

def glpi_create_ticket_instant(session_token, title, description, assigned_user_gid, unit_id, tick_type):
    assigned_user_id = get_user_id_and_unit_by_gid(session_token, assigned_user_gid)

    if tick_type == "Wniosek":
        tick_type = 2
    else:
        tick_type = 1
    
    ticket_data = {
        "input": {
            "name": title,
            "content": description,
            "requesttypes_id": 1,  
            "urgency": 3,  
            "impact": 3,  
            "priority": 3,  
            "type": tick_type,  
            "entities_id": unit_id,
            "_users_id_requester": assigned_user_id
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
            assign_response = glpi_assign_user_to_ticket(session_token, ticket_id, 3793, 2)

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

def glpi_unassign_user_from_ticket(session_token, ticket_id, user_id):
    
    url = f"{settings.Glpi_Url}/Ticket/{ticket_id}/Ticket_User"
    response = requests.get(url, headers=header(session_token))

    if response.status_code != 200:
        print(f"Error fetching Ticket_User associations: {response.status_code} - {response.text}")
        response.raise_for_status()

    ticket_users = response.json()

    ticket_user_id = None
    for association in ticket_users:
        if association.get("users_id") == user_id:
            ticket_user_id = association.get("id")
            break

    if not ticket_user_id:
        print(f"No association found for user {user_id} in ticket {ticket_id}.")
        return None

    delete_url = f"{settings.Glpi_Url}/Ticket_User/{ticket_user_id}"
    delete_response = requests.delete(delete_url, headers=header(session_token))

    if delete_response.status_code == 200:
        print(f"User {user_id} successfully unassigned from ticket {ticket_id}.")
        return delete_response.json()
    else:
        print(f"Error unassigning user: {delete_response.status_code} - {delete_response.text}")
        delete_response.raise_for_status()

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

def get_customfield_id(session_token, ticket_id):
    ticket_id = int(ticket_id)
    #endpoint = f"{settings.Glpi_Url}/{settings.Custom_Fields}?criteria[0][field]=items_id&criteria[0][searchtype]=equals&criteria[0][value]={ticket_id}"
    endpoint = f"{settings.Glpi_Url}/{settings.Custom_Fields}?sort=id&order=DESC&range=0-100"

    response = requests.get(endpoint, headers=header(session_token))
    
    if response.status_code == 200 or response.status_code == 206:
        datas = response.json()
        entitlement = 0
        id = 0
        if datas:
            #wydatek = None
            #dodatek = None
            for data in datas:
                if data.get('items_id') == ticket_id:
                    entitlement = data.get("plugin_fields_teamfielddropdowns_id")
                    #wydatek = data.get("plugin_fields_kategoriawydatkufielddropdowns_id", None)
                    #dodatek = data.get("czydodatkowefield", None)
                    id = data.get("id", 0)
                    break
            
            if entitlement == 0 and id == 0:
                endpoint = f"{settings.Glpi_Url}/{settings.Custom_Fields}?sort=id&order=DESC&range=0-750"

                response = requests.get(endpoint, headers=header(session_token))
                
                if response.status_code == 200 or response.status_code == 206:
                    datas = response.json()
                    if datas:
                        for data in datas:
                            if data.get('items_id') == ticket_id:
                                entitlement = data.get("plugin_fields_teamfielddropdowns_id")
                                #wydatek = data.get("plugin_fields_kategoriawydatkufielddropdowns_id", None)
                                #dodatek = data.get("czydodatkowefield", None)
                                id = data.get("id", 0)
                                break 
                    else:
                        return 0, "Blue"
                else:
                    return 0, "Blue"
        else:
            return 0, "Blue"
    else:
        return 0, "Blue"
    #print(entitlement)
    if entitlement == 4:
        entitlement = "Hide"
    elif entitlement == 3:
        entitlement = "Grey"
    elif entitlement == 2:
        entitlement = "Red"
    else:
        entitlement = "Blue"

    return id, entitlement
    
def glpi_write_custom_fields(session_token, ticket_id, entitlement=0, cost_category=0, additional=0, team=1):

    endpoint = f"{settings.Glpi_Url}/{settings.Custom_Fields}"

    custom_fields = {
        "items_id": ticket_id,  
        "plugin_fields_uprawnieniefielddropdowns_id": entitlement,
        "plugin_fields_kategoriawydatkufielddropdowns_id":cost_category,
        "czydodatkowefield": additional,
        "plugin_fields_teamfielddropdowns_id": team
    }

    data = {
        "input": custom_fields
    }

    response = requests.post(endpoint, headers=header(session_token), json=data)

    if response.status_code in [200, 201]:
        return response.json()
    else:
        custom_field_id, entitlement_fa = get_customfield_id(session_token, ticket_id)

        endpoint = f"{settings.Glpi_Url}/{settings.Custom_Fields}/{custom_field_id}"

        custom_fields = {}
        if entitlement is not None:
            custom_fields["plugin_fields_uprawnieniefielddropdowns_id"] = entitlement
        if cost_category is not None:
            custom_fields["plugin_fields_kategoriawydatkufielddropdowns_id"] = cost_category
        if additional is not None:
            custom_fields["czydodatkowefield"] = additional
        if team is not None:
            custom_fields["plugin_fields_teamfielddropdowns_id"] = team

        data = {
            "input": custom_fields
        }

        response = requests.put(endpoint, headers=header(session_token), json=data)

        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error updating custom fields with ID {custom_field_id} in {settings.Custom_Fields}: {response.status_code} - {response.text}")
            return None

def save_document(file_name,encoded_file):

    binary_file = base64.b64decode(encoded_file)
    folder_path='temp_files'

    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    file_path = os.path.join(folder_path, file_name)
    print(file_path)

    with open(file_path, "wb") as file:
        file.write(binary_file)
    
    return file_path

def upload_document_to_ticket(session_token, ticket_id, name, file_content):

    filepath = save_document(name, file_content)

    url = f"{settings.Glpi_Url}/Document/"
    print(url)

    json_payload = json.dumps({"input": {"name": name, "_filename": [os.path.basename(filepath)]}})
    print(f" Przesyłanie pliku: {filepath}")
    print(f" JSON wysyłany w `uploadManifest`: {json_payload}")

    mime_type, _ = mimetypes.guess_type(filepath)
    if mime_type is None:
        mime_type = "application/octet-stream" 

    with open(filepath, 'rb') as file:
        files = {
            'uploadManifest': (None, json_payload, 'application/json'),
            'filename[0]': (os.path.basename(filepath), file, mime_type)
        }

        response = requests.post(url, headers=header(session_token), files=files)

    #if os.path.exists(filepath):
        #os.remove(filepath)

    if response.status_code == 201:
        document_id = response.json().get('id')
        print(f"Send succesfully! ID document: {document_id}")
    else:
        raise Exception(f"Error while sending. Status: {response.status_code}, Respa: {response.text}")

    link_url = f"{settings.Glpi_Url}/Ticket/{ticket_id}/Document_Item"
    link_data = {
        "input": {
            "items_id": ticket_id,
            "itemtype": "Ticket",
            "documents_id": document_id
        }
    }

    response = requests.post(link_url, headers=header(session_token), json=link_data)

    if response.status_code == 201:
        print(f"Document ID {document_id} assigned to ticket {ticket_id}.")
        return document_id
    else:
        raise Exception(f"Error assigning to ticket. Status: {response.status_code}, Respa: {response.text}")

