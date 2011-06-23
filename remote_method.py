from __future__ import absolute_import
import tornado.web
import inspect
import traceback
import logging
import types
import functools
import time
import greenlet
import weakref
import Queue
import threading

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
    
log = None
def set_logger(logfunc):
    global log
    log = logfunc
    
GreenletMapping = weakref.WeakKeyDictionary()
GreenletNames = weakref.WeakKeyDictionary()
    
def get_resume_cb():
    gr = greenlet.getcurrent()
    handler = GreenletMapping[gr]
    def cb(value):
        handler.timecall(gr, value)
    return cb
    
def get_current_name():
    return GreenletNames[greenlet.getcurrent()]
    
def yield_til_resume():
    return greenlet.getcurrent().parent.switch()
            
gresource_cache = {}

gwaiting_on = {}

def save_resource(name, version, value, delete_old = True):
    if gresource_cache.has_key(name):
        name_cache = gresource_cache[name]
    else:
        name_cache = {}
        gresource_cache[name] = name_cache
    name_cache[version] = value
    if delete_old:
        for key in name_cache.keys():
            if key < version: del name_cache[key] 

def fetch_cache_resource(fetcher, name, version, return_old_okay = True, delete_old = True):
    # print 'in fetch_cache_resource for ' + name + ' ' + str(version)
    def do_fetch_once():
        # print 'in do_fetch_once'
        if gwaiting_on.has_key((name, version)):
            # print 'already fetching, waiting'
            gwaiting_on[(name, version)].append((get_resume_cb(), get_current_name()))
            return yield_til_resume()
        else:
            # print 'calling the function'
            gwaiting_on[(name, version)] = []
            result = fetcher(version)
            save_resource(name, version, result, delete_old)
            for cb, nm in gwaiting_on[(name, version)]:
                do_later_event_loop(functools.partial(cb, result), nm)
            del gwaiting_on[(name, version)]
            return result
    if gresource_cache.has_key(name):
        name_cache = gresource_cache[name]
        if name_cache.has_key(version):
            # print 'found, returning'
            return name_cache[version]
        elif return_old_okay:
            # print 'going with old, returning'
            old_ver = max(name_cache.keys())
            do_later_event_loop(do_fetch_once, 'fetch ' + name + ' ' + str(version))
            return name_cache[old_ver]        
    return do_fetch_once()
        
queues = {}
queues['task'] = Queue.Queue()
queues['callback'] = Queue.Queue()
threads = {}

def workerThread(thread_name):
    while True:
        try:
            func = queues[thread_name].get(True, 2)
            func()
        except Queue.Empty:
            del threads[thread_name]
            break
        except Exception, e:
            log(1, 'EXCEPTION IN workerThread: '  + str(e.message) + '\n\n' + traceback.format_exc(), {})
        
def ensureThread(thread_name):
    if threads.has_key(thread_name): return
    threads[thread_name] = threading.Thread(target=functools.partial(workerThread, thread_name))
    threads[thread_name].start()
    
#executes function on a seperate thread
def do_later(func, t = 'task'):
    queues[t].put(func)
    ensureThread(t)
    
#executes function on a seperate thread, pausing the current operation until it returns
def execute_async(func):
    cb = get_resume_cb()
    def do_it():
        ret = func()
        tornado.ioloop.IOLoop.instance().add_callback(lambda: cb(ret))
    do_later(do_it, t = 'callback')
    return yield_til_resume()
 
#executes function on the main event loop, but at a seperate time.
def do_later_event_loop(func, name = None):
    if name is None: name = func.__name__
    tornado.ioloop.IOLoop.instance().add_callback(functools.partial(launch_on_greenlet, func, name = name))
    
    
class NonRequest:
    def timecall(self, gr, value):
        nm = GreenletNames[gr] if GreenletNames.has_key(gr) else 'name missing'
        print 'event loop - entering - ' + nm
        try:
            start = time.time()
            gr.switch(value)
            end = time.time()
            dif = end - start
            # if dif > .01:
                # log(1, 'Taking too long: ' + nm + ': ' + str(dif), {})
            #DISABLING THIS, BECAUSE COULD GET CIRCULAR WITH LOG FUNCTION
        except Exception, e:
            log(1, 'EXCEPTION in ' + nm + ': ' + str(e.message) + '\n\n' + traceback.format_exc(), {})
        finally:
            print 'event loop - exiting - ' + nm
        
nonrequest = NonRequest()
    
def launch_on_greenlet(func, name = None):
    if name is None: name = func.__name__
    gr = greenlet.greenlet(lambda _: func())
    GreenletMapping[gr] = nonrequest
    GreenletNames[gr] = name
    nonrequest.timecall(gr, None)
    
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
            
    def timecall(self, gr, value):
        nm = GreenletNames[gr] if GreenletNames.has_key(gr) else 'name missing'
        print 'event loop - entering - ' + nm
        try:
            start = time.time()
            gr.switch(value)
            end = time.time()
            dif = end - start
            print 'event loop - time - ' + str(dif)
            self.log_time(nm, dif)
        except Exception, e:
            r = self.handle_exception(e, nm)
            self.write(self.serialize(r))
            self.finish()
        finally:
            print 'event loop - exiting - ' + nm
    
    def _handle(self):
        method = None
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
            
            def do_it(_):
                x = method(**args)
                if not self._finished and not hasattr(method, 'remote_method_async'): 
                    self.write(self.serialize(x))
                    self.finish()
                elif x is not None:
                    raise Exception('cannot both call self.ret and return non-None from the same method / cannot return non-None from an asynchronous method')  
            
            gr = greenlet.greenlet(do_it)
            GreenletMapping[gr] = self
            GreenletNames[gr] = method.__name__
            self.timecall(gr, None)           

        except Exception, e:
            r = self.handle_exception(e, method.__name__)
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
    
    def handle_exception(self):
        raise Exception('no exception handler defined -- overwrite handle_exception')
        
    def log_time(self):
        raise Exception('no time logger defined -- overwite log_time')
    
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
    