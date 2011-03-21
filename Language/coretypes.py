from corelanguage import TypeStatement, PropertyStatement, PropertyDefinition, KINDS, LiteralStatement, ValidatorStatement, FlagStatement
import re
import datetime
from Utils.html_sanitizer import clean_html

#validators
def v_str(v):
    return isinstance(v, unicode) or isinstance(v, str), 'was expecting string but got ' + repr(type(v))

def v_int(v):
    try:
        return isinstance(int(v), int) and int(v) == v, 'was expecting int but got ' + repr(type(v))
    except:
        return False, 'was expecting int but got ' + repr(type(v))

def v_bool(v):
    return isinstance(v, bool), 'was expecting bool but got ' + repr(type(v))
    
def v_float(v):
    return isinstance(v, float), 'was expecting float but got ' + repr(type(v))
    
def v_html(v):
    if clean_html(v) != v:
        return False, 'please use html_sanitizer.clean_html prior to storing this data'
    return True, ''
    
def v_timestamp(v):
    try:
        datetime.datetime.fromtimestamp(v)
        return True, ''
    except Exception, e:
        return False, 'was expecting timestamp but got ' + repr(v) + ' which fails: ' + e.message

def v_date(v):
    if isinstance(v, datetime.datetime):
        return True, ''
    return False, 'was expecting date but got ' + repr(type(v))

re_name = re.compile(r'^[-a-zA-Z0-9 /.:_]+$')
   
def v_name(v):
    msg = 'names must be 255 bytes or less and can only consist of letters, numbers, spaces and the following characters: -/.:_]'
    return re_name.match(v) is not None and len(v.encode('utf-8')) <= 255, msg





core_types = []
a = core_types.append

a(TypeStatement('integer',()))
a(TypeStatement('boolean',()))
a(TypeStatement('string',()))
a(TypeStatement('name',('string',)))
a(TypeStatement('guid', ('string',)))
a(TypeStatement('toplevel',('name',)))
a(FlagStatement('toplevel', 'abstract', True))
a(TypeStatement('SafeHTML',('string',)))
a(TypeStatement('url',('string',)))
a(TypeStatement('address',('string',)))
a(TypeStatement('picture',('string',)))
a(TypeStatement('float',()))
a(TypeStatement('date',())) #datetime
a(TypeStatement('timestamp',('float',))) #stored as a floating point


a(ValidatorStatement('integer', v_int))
a(ValidatorStatement('boolean', v_bool))
a(ValidatorStatement('string', v_str))
a(ValidatorStatement('name', v_name))
a(ValidatorStatement('SafeHTML', v_html))
a(ValidatorStatement('date', v_date))
a(ValidatorStatement('timestamp', v_timestamp))
a(ValidatorStatement('float', v_float))