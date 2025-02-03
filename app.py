import json
from flask import Flask, jsonify, request, make_response
import requests, threading, time
from glpi_download import glpi_main, check_ticket_state_and_technic
from glpi_upload import glpi_add_solution, glpi_add_followup, glpi_add_task_to_ticket, glpi_create_ticket, glpi_close_ticket, glpi_write_custom_fields,glpi_create_ticket_instant, upload_document_to_ticket
import settings
from data import add_local_viewer_id_ticket, perform_deletions, remove_ticket

app = Flask(__name__)

session_token = None

def init_session():

    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'user_token ' + settings.Api_Token,
        'App-Token': settings.App_Token
    }
    
    response = requests.get(f"{settings.Glpi_Url}/initSession", headers=headers)
    
    if response.status_code == 200:
        session_toke = response.json()['session_token']
        return session_toke
    else:
        print(f"Cannot initialize sesion: {response.status_code}")
        print(response.text)
        return None

def refresh_sesion():
    global session_token
    while True:
        try:
            session_token = init_session()
            perform_deletions()
        except:
            print("Error sesion refresh")
        time.sleep(180000)

def continuous_download():
    while True:
        try:
            with open(settings.Id_File, "r") as file:
                ticked_id = file.read().strip()
        except FileNotFoundError:
            print(f"No file {settings.Id_File} found, starting with id 1")
            ticked_id = "1"
            with open(settings.Id_File, "w") as file:
                file.write(ticked_id)

        try:
            download_result, hide_ticket, latest_ticket_id = glpi_main(ticked_id, session_token)  
        except Exception as e:
            print("Error while while downloading ticket (GLPI_download):")
            print(f"Error: {str(e)}")
        try:
            if download_result:  
                print(f"Ticket download result: {download_result.get('title')}")
                
                response = requests.post(settings.Ticket_Local_Viewer_Link, json=download_result)
                response.raise_for_status()
                
                data_respa = response.json()
                local_viewer_id = data_respa.get('ticket_id')
                print("New ticket sent successfully.")

                #latest_ticket_id = download_result.get('id')
                add_local_viewer_id_ticket(latest_ticket_id, local_viewer_id)
                print(local_viewer_id)

                if latest_ticket_id:
                    with open(settings.Id_File, "w") as file:
                        file.write(str(latest_ticket_id))
                    print(f"Updated latest ticket ID to {latest_ticket_id}")
                if hide_ticket:
                    updata_link = settings.Ticket_Local_Viewer_Link + f"/{local_viewer_id}"
                    update_data = {
                                    'title':'',
                                    'contact':'',
                                    'client':'',
                                    'gid':'',
                                    'visible': 'False',
                                    'migacz':'False'
                                }
                    response = requests.put(updata_link, json=update_data)
                    remove_ticket(latest_ticket_id, 168)
                    if response.status_code != 200:
                        remove_ticket(latest_ticket_id, 0)
                        perform_deletions()

        except Exception as e:
            print(f"Error while downloading or sending the ticket (app): {download_result} || ")
            print(f"Error: {str(e)}")
       
        time.sleep(5) 

@app.route('/trigger', methods=['POST'])
def trigger_event():
    return jsonify({"message": "Continuous download is running"}), 200

@app.route('/add_solution', methods=['POST'])
def add_solution():
    data = request.json 

    ticket_id = data.get('ticket_id')
    solution_content = data.get('solution')
    technic_id = data.get('technic_id')

    if not ticket_id or not solution_content:
        return jsonify({"error": "ticket_id and solution are required"}), 400

    try:
        glpi_response = glpi_add_solution(ticket_id, solution_content, session_token, technic_id)
        return jsonify(glpi_response), 200
    except Exception as e:
        print(jsonify({"error": str(e)}))
        return jsonify({"error": str(e)}), 500

@app.route('/add_followup', methods=['POST'])
def add_followup():
    data = request.json 

    ticket_id = data.get('ticket_id')
    followup_content = data.get('solution')

    if not ticket_id or not followup_content:
        return jsonify({"error": "ticket_id and followup are required"}), 400

    try:
        glpi_response = glpi_add_followup(ticket_id, followup_content, session_token)
        return jsonify(glpi_response), 200
    except Exception as e:
        print(jsonify({"error": str(e)}))
        return jsonify({"error": str(e)}), 500

@app.route('/add_task', methods=['POST'])
def add_task():
    data = request.json 

    ticket_id = data.get('ticket_id')
    task_content = data.get('task_content')
    duration = data.get('duration')

    if not ticket_id or not task_content or not duration :
        return jsonify({"error": "ticket_id, duration, task_content are required"}), 400

    try:
        glpi_response = glpi_add_task_to_ticket(ticket_id, task_content, duration, session_token)
        return jsonify(glpi_response), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/add_ticket', methods=['POST'])
def add_ticket():
    data = request.json

    tick_type = data.get('tick_type', "Incydent")
    title = data.get('title')
    description = data.get('description')
    assigned_user_id = str(data.get('assigned_user_id'))
    assigned_technic_id = data.get('assigned_technic_id')
    unit_id = data.get('unit_id')
    close_after = data.get('close_after', "No")

    if not title or not description or not assigned_user_id or not assigned_technic_id or not unit_id:
        return jsonify({"error": "title, description, assigned technic and assigned_user_id are required"}), 400

    try:
        glpi_response = glpi_create_ticket(session_token, title, description, assigned_user_id, assigned_technic_id, unit_id, close_after, tick_type)

        return jsonify(glpi_response), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/add_ticket_instant', methods=['POST'])
def add_ticket_instant():
    data = request.json

    tick_type = data.get('tick_type', "Incydent")
    title = data.get('title')
    description = data.get('description')
    assigned_user_id = str(data.get('assigned_user_gid'))
    unit_id = data.get('unit_id')

    if not title or not description or not assigned_user_id:
        return jsonify({"error": "title, description, assigned user and unit_id are required"}), 400

    try:
        glpi_response = glpi_create_ticket_instant(session_token, title, description, assigned_user_id, unit_id,  tick_type)

        return jsonify(glpi_response), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/check_state', methods=['POST'])
def check_state():
    data = request.json

    ticket_id = data.get('ticket_id')
    if not ticket_id:
        return jsonify({"error": "ticket id are required"}), 400

    try:
        state, assigned_to = check_ticket_state_and_technic(session_token, ticket_id)
        response = {
        "message": "Operation successful",
        "data": {
            "state": str(state),
            "assigned_to": str(assigned_to),
        }
        }
    
        return make_response(jsonify(response), 200, {"Content-Type": "application/json"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route('/add_exe', methods=['POST'])
def add_exe():
    data = request.json

    title = data.get('title')
    timesum = data.get('time')
    company = data.get('company')
    if not title or not timesum or not company:
        return jsonify({"error": "title, time and company are required"}), 400
    
    description = title
    
    if company == "SAR":
        assigned_user_id = "LQ5789-NN"
        unit_id = 2
    elif company == "Services":
        assigned_user_id = "RF5150-NN"
        unit_id = 1
    elif company == "EZE":
        assigned_user_id = "AHI293"
        unit_id = 3
    elif company == "EC Słupsk":
        assigned_user_id = "ZS5445"
        unit_id = 5
    
    assigned_technic_id = 8
    close_after = "No"

    if not title or not description or not assigned_user_id or not assigned_technic_id or not unit_id:
        return jsonify({"error": "title, description, assigned technic and assigned_user_id are required"}), 400

    try:
        glpi_response = glpi_create_ticket(session_token, title, description, assigned_user_id, assigned_technic_id, unit_id, close_after, "Incydent")
        respa = glpi_add_task_to_ticket(glpi_response.get("id"), "Rozwiązanie problemu",timesum*60 ,session_token)
        respa = glpi_write_custom_fields(session_token, glpi_response.get("id"), 1, 1, 1 , 2)
        respa = glpi_close_ticket(session_token, glpi_response.get("id"), "Rozwiązanie problemu")

        return jsonify(glpi_response), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/update_customs', methods=['POST'])
def update_customs():
    data = request.json  

    ticket_id = data.get('ticket_id')
    entitlement =  data.get('entitlement', 0)
    cost_category = data.get('cost_category', 0)
    additional = data.get('additional', 0)
    team = data.get('team')
    if not ticket_id:
        return jsonify({"error": "ticket_id, entitlement,cost category and if additional are required"}), 400
    
    if entitlement =="Administracyjne": 
        entitlement = 2
    elif entitlement =="Helpdesk": 
        entitlement = 1
    if cost_category =="Korporacyjne": 
        cost_category = 2
    elif cost_category =="Własne": 
        cost_category = 1
    if additional =="Tak": 
        additional = 1
    elif additional =="Nie": 
        additional = 0
    if team =="Blue":
        team == 1
    elif team =="Red":
        team == 2
    elif team =="Grey":
        team == 3
    elif team =="Hide":
        team == 4

    try:
        response = glpi_write_custom_fields(session_token, ticket_id, entitlement, cost_category, additional , team)
        print(f"Ticket: {ticket_id} - Custom fields updated succesfully")
        return jsonify(response), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/upload_document', methods=['POST'])
def upload_document():
    data = request.json 

    file = data.get('file')
    file_name = data.get('file_name', "plik")
    ticket_id = data.get('ticket_id')
    print(file_name)

    try:
        document_id = upload_document_to_ticket(session_token, ticket_id, file_name, file)

        return jsonify({
            'message': 'File uploaded and linked to ticket successfully.',
            'document_id': document_id,
            'ticket_id': ticket_id
        }), 200
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    session_fresher = threading.Thread(target=refresh_sesion)
    session_fresher.daemon = True
    session_fresher.start()
    download_thread = threading.Thread(target=continuous_download)
    download_thread.daemon = True 
    download_thread.start()
    
    # run Flask
    app.run(host=settings.host, port=settings.port)