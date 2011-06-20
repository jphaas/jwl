import tempfile
from os.path import join, exists
import pickle
import time
import remote_method

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

# set_backup = False
    
def back_up():
    global set_backup
    # if not set_backup:
        # set_backup = True
    session_clone = dict(session)
    def do_it():
        with open(_backup, 'w') as file:
            file.write(pickle.dumps(session_clone))
        # set_backup = False
    remote_method.do_later(do_it)    
        
def get_data(key):
    return session[key] if session.has_key(key) else None

def set_data(key, value):
    start = time.time()
    session[key] = value
    back_up()
 
def clear_data(key):
    if session.has_key(key):
        del session[key]
    back_up()