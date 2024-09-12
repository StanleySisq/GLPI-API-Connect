from flask import Flask, jsonify, request
import requests, threading, time
from glpi_download import glpi_main
from glpi_upload import glpi_add_solution, glpi_add_followup, glpi_add_task_to_ticket
import settings

app = Flask(__name__)

def continuous_download():
    while True:
        try:
            with open(settings.Id_File, "r") as file:
                ticked_id = file.read()            
        except FileNotFoundError:
            print(f"No file {settings.Id_File} found, starting with id 1")
            ticked_id="1"

        try:
            download_result = glpi_main(ticked_id)  # JSON return
            #print(download_result)
            response = requests.post(settings.Ticket_Post_Link, json=download_result)
            response.raise_for_status()
            print("New ticket sent successfully.")
        except Exception as e:
            print("Ticket does not send")
            print(f"Error: {str(e)}")
        
        time.sleep(1) 

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
        glpi_response = glpi_add_solution(ticket_id, solution_content)
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
        glpi_response = glpi_add_followup(ticket_id, followup_content)
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
        glpi_response = glpi_add_task_to_ticket(ticket_id, task_content, duration)
        return jsonify(glpi_response), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    download_thread = threading.Thread(target=continuous_download)
    download_thread.daemon = True 
    download_thread.start()
    
    # run Flask
    app.run(host=settings.host, port=settings.port)