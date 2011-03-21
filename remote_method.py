from __future__ import absolute_import
import tornado.web
import inspect
import traceback
import logging
import deployconfig
import types

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
        def get_method_list(self):
            return build_method_list(app)
        def __init__(self):
            pass
    return Handle()
    
class HTTPHandler(tornado.web.RequestHandler, AuthMixin):
    """  
    Override GetFunctionList() to provide the list of method to convert.
    """
    def get(self):
        self._handle()
    def post(self):
        self._handle()
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
                
            self.write(self.serialize(method(**args)))
                
            
        except ExpectedException, e:
            self.write(self.server_error(e.message, deployconfig.get('debug')))
            logger.error(repr(e.message) + ' ' + traceback.format_exc())
        except Exception, e:
            logger.critical(repr(e.message) + ' ' + traceback.format_exc())
            if deployconfig.get('debug'):
                self.write(self.server_error(repr(e.message), True))
            else:
                self.write(self.server_error('Unexpected server error -- please try again later', False))
            
    def server_error(self, msg, stacktrace):
        r = {'server_error': True, 'message': msg}
        if stacktrace:
            r['stacktrace'] = traceback.format_exc()
        return self.serialize(r)
        
    @staticmethod
    def get_arglist(method):
        return [arg for arg in inspect.getargspec(method)[0] if arg != 'self']
        
    def get_method_list(self):
        raise NotImplementedException()
        
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
        return json.dumps(obj)
        
def build_method_list(object):
    """utility function, introspects a given object to automatically build a method list for it containing all non-underscore method names"""
    return [getattr(object, name) for name in dir(object) if name[0] != '_' and type(getattr(object, name)) is types.MethodType]
    