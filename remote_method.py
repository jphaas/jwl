from __future__ import absolute_import
import tornado.web
import inspect
import traceback
import logging
import types

from . import deployconfig
from .authenticate import AuthMixin

# Find a JSON parser
try:
    import json
except ImportError:
    try:
        import simplejson as json
    except ImportError:
        # For Google AppEngine
        from django.utils import simplejson as json

logger = logging.getLogger('ajaxdisplay.HTTPHandler')

class ExpectedException(Exception):
    """
    Represents an exception that is meant to go to the end-user;
    the idea is that the contained error message should get displayed
    to the client, as opposed to unexpected exceptions where we'll
    display a vague "Unexpected server error" message
    """
    pass

    
#mark a function as asynchronous
def asynchronous(func):
    func.remote_method_async = True
    return func

#Takes a single json item or a list of json items
#deserializes from json
#then, if result is a dictionary with "datatype" set, does additional processing
def deserialize(str, argname):
    try:
        if type(str) is list:
            return [_deser(s) for s in str]
        return _deser(str)
    except Exception, e:
        raise Exception('malformed argument passed into parameter ' + argname + ': ' + str + ".  Exception: " + e.message)
    
#helper function for deserialize
def _deser(obj):
    d = json.loads(obj)
    if isinstance(d, dict) and d.has_key('datatype'):
        dt = d['datatype']
        if dt == 'timestamp':
            return float(d['value'])
        else:
            raise Exception('uncrecognized datatype: ' + str(dt))
    return d
    
  
def make_dummy_handler(subclass):
    class Handle(subclass):
        def __init__(self):
            pass
    return Handle()
    
class HTTPHandler(tornado.web.RequestHandler, AuthMixin):
    """  
    Override GetFunctionList() to provide the list of method to convert.
    """
    @tornado.web.asynchronous
    def get(self):
        self._handle()
    @tornado.web.asynchronous
    def post(self):
        self._handle()
    def async_finish(self, return_value):
        self.write(self.serialize(return_value))
        self.finish()
    def _handle(self):
        try:
            i = self.request.arguments
            if not i.has_key('method'):
                raise Exception('"method" not found in get / post data')
            try:
                method = filter(lambda m: m.__name__ == self.get_argument('method'), self.get_method_list())[0]
            except IndexError:
                raise Exception('invalid method name: ' + self.get_argument('method'))
            logging.info(method.__name__ + repr(inspect.getargspec(method)))
            arglist = self.get_arglist(method)
                          
            args = dict((argname, deserialize(self.get_argument(argname), argname) if i.has_key(argname) else None) for argname in arglist)
            
            if hasattr(method, 'remote_method_async'):
                x = method(**args)
                if x is not None: raise Exception('Return value from asynchronous method... do not do that, use self.async_finish')
            else:
                self.write(self.serialize(method(**args)))
                self.finish()
                
        except Exception, e:
            r = self.handle_exception(e)
            self.write(self.serialize(r))
            self.finish()          
        
    @staticmethod
    def get_arglist(method):
        return [arg for arg in inspect.getargspec(method)[0] if arg != 'self']
        
    def get_method_list(self):
        return build_method_list(self)
        
    def write_js_interface(self):
        """outputs the text for a javascript interface for hitting this server"""
        output = []
        output.append('var allfuncs = {};')
        output.append('')
        for method in self.get_method_list():
            output.append('function %s(%s)'%(method.__name__, ', '.join(self.get_arglist(method) + ['callback'])))
            output.append('{')
            output.append("method_call('%s', {%s}, callback);"%(method.__name__, ', '.join("'%s': %s"%(a, a) for a in self.get_arglist(method))))
            output.append('}')
            output.append("allfuncs['%s'] = %s;"%(method.__name__, method.__name__))
            output.append('')
        return '\n'.join(output)
    

    
    @staticmethod
    def serialize(obj):
        nonamed = convert_namedtuples(obj)
        return json.dumps(nonamed)

def convert_namedtuples(obj):
    if hasattr(obj, '_asdict'): return convert_namedtuples(obj._asdict())
    if isinstance(obj, dict):
        return dict((key, convert_namedtuples(value)) for key, value in obj.iteritems())
    if isinstance(obj, list) or isinstance(obj, tuple):
        return [convert_namedtuples(v) for v in obj]
    return obj        
       
def build_method_list(object):
    """utility function, introspects a given object to automatically build a method list for it containing all non-underscore method names"""
    return [getattr(object, name) for name in dir(object) if name[0] != '_' and name not in dir(HTTPHandler) and type(getattr(object, name)) is types.MethodType]
    