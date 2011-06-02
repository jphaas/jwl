import tempfile
from os.path import join, exists
import pickle

_backup = join(tempfile.gettempdir(), 'session_backup_file')
if exists(_backup):
    with open(_backup, 'r') as file:
        try:
            session = pickle.loads(file.read())
        except EOFError:
            print 'WARNING: session file corrupted'
            session = {}
else:
    session = {}

def back_up():
    with open(_backup, 'w') as file:
        file.write(pickle.dumps(session))

def get_data(key):
    return session[key] if session.has_key(key) else None

def set_data(key, value):
    session[key] = value
    back_up()
 
def clear_data(key):
    if session.has_key(key):
        del session[key]
    back_up()