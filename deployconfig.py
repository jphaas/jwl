try:
    _config
except:
    _config = {}

def set(**args):
    for key in args:
        _config[key] = args[key]

def set2(key, value):
    _config[key] = value
    

def get(key):
    try:
        return _config[key]
    except KeyError:
        return None