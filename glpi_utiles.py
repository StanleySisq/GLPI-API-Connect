import settings

def header(session_token):
    headers = {
        'Content-Type': 'application/json',
        'Session-Token': session_token,
        'App-Token': settings.App_Token
    }
    return headers