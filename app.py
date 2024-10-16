from flask import Flask, jsonify, request
import requests, threading, time
from glpi_download import glpi_main
from glpi_upload import glpi_add_solution, glpi_add_followup, glpi_add_task_to_ticket, glpi_create_ticket, glpi_close_ticket
import settings

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
            download_result = glpi_main(ticked_id, session_token)  
            if download_result:  
                print(f"Ticket download result: {download_result}")
                
                response = requests.post(settings.Ticket_Post_Link, json=download_result)
                response.raise_for_status()
                print("New ticket sent successfully.")

                latest_ticket_id = download_result.get('id')
                if latest_ticket_id:
                    with open(settings.Id_File, "w") as file:
                        file.write(str(latest_ticket_id))
                    print(f"Updated latest ticket ID to {latest_ticket_id}")
        except Exception as e:
            print("Error while downloading or sending the ticket:")
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

    if not ticket_id or not solution_content:
        return jsonify({"error": "ticket_id and solution are required"}), 400

    try:
        glpi_response = glpi_add_solution(ticket_id, solution_content, session_token)
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

    title = data.get('title')
    description = data.get('description')
    assigned_user_id = str(data.get('assigned_user_id'))
    assigned_technic_id = data.get('assigned_technic_id')
    unit_id = data.get('unit_id')
    close_after = data.get('close_after')

    if not title or not description or not assigned_user_id or not assigned_technic_id or not unit_id:
        return jsonify({"error": "title, description, assigned technic and assigned_user_id are required"}), 400

    try:
        glpi_response = glpi_create_ticket(session_token, title, description, assigned_user_id, assigned_technic_id, unit_id, close_after)

        return jsonify(glpi_response), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    session_fresher = threading.Thread(target=refresh_sesion)
    session_fresher.daemon = True
    session_fresher.start()
    download_thread = threading.Thread(target=continuous_download)
    download_thread.daemon = True 
    download_thread.start()
    
    # run Flask
    app.run(host=settings.host, port=settings.port)