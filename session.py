import tempfile
from os.path import join, exists
import pickle
import time
import remote_method

_backup = join(tempfile.gettempdir(), 'session_backup_file')
if exists(_backup):
    with open(_backup, 'r') as file:
        try:
            session, expires = pickle.loads(file.read())
        except:
            print 'WARNING: session file corrupted'
            session = {}
            expires = {}
else:
    session = {}
    expires = {}

# set_backup = False
    
def back_up():
    global set_backup
    # if not set_backup:
        # set_backup = True
    session_clone = (dict(session), dict(expires))
    def do_it():
        with open(_backup, 'w') as file:
            file.write(pickle.dumps(session_clone))
        # set_backup = False
    remote_method.do_later(do_it)    
        
def get_data(key):
    if expires.has_key(key) and expires[key] is not None and expires[key] < time.time(): return None
    return session[key] if session.has_key(key) else None

def set_data(key, value, expire_seconds = None):
    session[key] = value
    expires[key] = time.time() + expire_seconds if expire_seconds is not None else None
    back_up()
 
def clear_data(key):
    if session.has_key(key):
        del session[key]
    back_up()