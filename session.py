session = {}

def get_data(key):
    return session[key] if session.has_key(key) else None

def set_data(key, value):
    session[key] = value
 
def clear_data(key):
    if session.has_key(key):
        del session[key]