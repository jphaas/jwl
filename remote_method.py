from __future__ import absolute_import
import tornado.web
import tornado.ioloop
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
from jwl.globaltimer import start, check, show_output
from email.utils import formatdate
from datetime import datetime, date
from time import mktime
import decimal
import sys
from tornado.web import HTTPError



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

logger = logging.getLogger('jwl.remote_method')

class ExpectedException(Exception):
    """
    Represents an exception that is meant to go to the end-user;
    the idea is that the contained error message should get displayed
    to the client, as opposed to unexpected exceptions where we'll
    display a vague "Unexpected server error" message
    """
    pass
    
class SpecialException(Exception):
    """
    Represents an exception that should interrupt normal client error-handling;
    it's a way of sending messages to the client that break out of the standard
    call stack.
    """
    pass
    
class Send304Exception(Exception):
    """
    Send a not-modified response to the client
    """
    pass

    
def asynchronous(func):
    func.remote_method_async = True
    return func
    
def no_serialize(func):
    func.do_not_serialize = True
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
    
bug = None
def set_bug(bugfunc):
    global bug
    bug = bugfunc
    
def handle_callback_exception(self, callback):
    bug(sys.exc_info()[1])
tornado.ioloop.IOLoop.handle_callback_exception = handle_callback_exception
    
GreenletMapping = weakref.WeakKeyDictionary()
GreenletNames = weakref.WeakKeyDictionary()
    
def get_resume_cb():
    gr = greenlet.getcurrent()
    if not GreenletMapping.has_key(gr):
        return None
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
modified_cache = {}

def save_resource(name, version, value, delete_old = True):
    if gresource_cache.has_key(name):
        name_cache = gresource_cache[name]
    else:
        name_cache = {}
        gresource_cache[name] = name_cache
    name_cache[version] = value
    modified_cache[str(name) + '_' + str(version) + '_modified'] = time.time()
    if delete_old:
        for key in name_cache.keys():
            if key < version: del name_cache[key] 

def _modified(last_modified, handler):
    ims_value = handler.request.headers.get("If-Modified-Since")
    if ims_value is not None:
        date_tuple = email.utils.parsedate(ims_value)
        if_since = datetime.datetime.fromtimestamp(time.mktime(date_tuple))
        if if_since >= datetime.fromtimestamp(last_modified):
            raise Send304Exception()
    handler.set_header("Date", formatdate(timeval = stamp, localtime = False, usegmt = True))
    handler.set_header('Last-Modified', formatdate(timeval = last_modified, localtime = False, usegmt = True))

#if handler is set, sets the last-modified header on handler and raises a 304 exception if appropriate
def fetch_cache_resource(fetcher, name, version, return_old_okay = True, delete_old = True, handler=None):
    def do_fetch_once():
        if gwaiting_on.has_key((name, version)):
            grc = get_resume_cb()
            if not grc: raise Exception('could not generate callback; probably means not on child greenlet')
            gwaiting_on[(name, version)].append((grc, get_current_name()))
            ret = yield_til_resume()
            if handler: _modified(modified_cache[str(name) + '_' + str(version) + '_modified'], handler)
            return ret
        else:
            gwaiting_on[(name, version)] = []
            result = fetcher(version)
            save_resource(name, version, result, delete_old)
            for cb, nm in gwaiting_on[(name, version)]:
                do_later_event_loop(functools.partial(cb, result), nm)
            del gwaiting_on[(name, version)]
            if handler: _modified(modified_cache[str(name) + '_' + str(version) + '_modified'], handler)
            return result
    if gresource_cache.has_key(name):
        name_cache = gresource_cache[name]
        if name_cache.has_key(version):
            if handler: _modified(modified_cache[str(name) + '_' + str(version) + '_modified'], handler)
            return name_cache[version]
        elif return_old_okay:
            old_ver = max(name_cache.keys())
            do_later_event_loop(do_fetch_once, 'fetch ' + name + ' ' + str(version))
            if handler: _modified(modified_cache[str(name) + '_' + str(old_ver) + '_modified'], handler)
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
            bug(e, dict(thread=thread_name))
        
def ensureThread(thread_name):
    if threads.has_key(thread_name): return
    threads[thread_name] = threading.Thread(target=functools.partial(workerThread, thread_name))
    threads[thread_name].start()
    
#executes function on a seperate thread
def do_later(func, t = 'task'):
    queues[t].put(func)
    ensureThread(t)
    
#executes function on a seperate thread, pausing the current operation until it returns
def execute_async(func, t = 'callback'):
    cb = get_resume_cb()
    if not cb: raise Exception('no callback found; probably means not inside a child greenlet')
    def do_it():
        ret = func()
        tornado.ioloop.IOLoop.instance().add_callback(lambda: cb(ret))
    do_later(do_it, t=t)
    return yield_til_resume()
 
#executes function on the main event loop, but at a seperate time.
def do_later_event_loop(func, name = None):
    if name is None: name = func.__name__
    tornado.ioloop.IOLoop.instance().add_callback(functools.partial(launch_on_greenlet, func, name = name))
    
def insist_top():
    if greenlet.getcurrent().parent is not None:
        p = greenlet.getcurrent().parent
        s= ''
        if p.gr_frame:
            s = ''.join(traceback.format_stack(p.gr_frame))
        p.throw(Exception, 'this function should only be called from the top-most-greenlet.  Stack trace of parent: ' + s)
    
class NonRequest:
    def timecall(self, gr, value):
        insist_top()
        nm = GreenletNames[gr] if GreenletNames.has_key(gr) else 'name missing'
        logger.debug('event loop - entering - ' + nm)
        try:
            start = time.time()
            gr.parent = greenlet.getcurrent()
            gr.switch(value)
            end = time.time()
            dif = end - start
            if dif > .01:
                logger.warn('Taking too long: ' + nm + ': ' + str(dif))
        except Exception, e:
            bug(e, dict(method=nm))
        finally:
            logger.debug('event loop - exiting - ' + nm)
            pass
        
nonrequest = NonRequest()
    
def launch_on_greenlet(func, name = None):
    insist_top()
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
        
    def _handle_request_exception(self, e):
        if isinstance(e, HTTPError):
            tornado.web.RequestHandler._handle_request_exception(self, e)
        else:
            bug(e)
            self.send_error(500, exception=e)
            
    def timecall(self, gr, value):
        insist_top()
        nm = GreenletNames[gr] if GreenletNames.has_key(gr) else 'name missing'
        try:
            starttime = time.time()
            start()
            check('event loop - entering - ' + nm)
            gr.parent = greenlet.getcurrent()
            gr.switch(value)
            end = time.time()
            dif = end - starttime
            check('event loop - exiting - ' + nm)
            show_output()
            self.log_time(nm, dif, gr)
        except Exception, e:
            self._exception_handler(e, nm)
        finally:
            pass
            
    def set_timeout(self, delay, returnValue): #if the call hasn't returned by the time the delay expires, ends function and returns the return value
        def callback():
            if not self._finished:
                self.async_finish(returnValue)
        tornado.ioloop.IOLoop.instance().add_timeout(time.time() + delay, callback)
            
    def _exception_handler(self, e, name):
        if str(e) == 'Stream is closed': #I have an open stackoverflow question to see if this is an appropriate way of handling it
            return
        r = self.handle_exception(e, name)
        if not self._finished:
            self.write(self.serialize(r))
            self.finish()
    
    def _handle(self):
        method = None
        try:
            i = self.request.arguments
            if not i.has_key('method'):
                sp = self.request.uri.split('api/')
                if len(sp) > 1:
                    methodname = sp[1].split('?')[0]
                else:
                    raise Exception('"method" not found in get / post data')
            else:
                methodname = self.get_argument('method')
            try:
                method = filter(lambda m: m.__name__ == methodname, self.get_method_list())[0]
            except IndexError:
                raise Exception('invalid method name: ' + methodname)
            
            arglist = self.get_arglist(method)
                          
            args = dict((argname, deserialize(self.get_argument(argname), argname) if i.has_key(argname) else None) for argname in arglist)
            args1 = dict((k, v if k not in ('pw', 'password') else '****') for k, v in args.iteritems()) 
            logger.debug(method.__name__ + ' ' + repr(args1))
            
            def do_it(_):
#                 x = method(**args)
#                 if not self._finished and not hasattr(method, 'remote_method_async'): 
#                     if not hasattr(method, 'do_not_serialize'):
#                         x = self.serialize(x)
#                     self.write(x)
#                     self.finish()
#                 elif x is not None:
#                     raise Exception('cannot both call self.ret and return non-None from the same method / cannot return non-None from an asynchronous method')  
                try:
                    x = method(**args)
                except Send304Exception:
                    self.set_status(304)
                    self.finish()
                    
                if not hasattr(method, 'remote_method_async'): 
                    if not hasattr(method, 'do_not_serialize'):
                        x = self.serialize(x)
                    self.write(x)
                    self.finish()
                elif x is not None:
                    raise Exception('cannot return non-None from an asynchronous method')  
            
            gr = greenlet.greenlet(do_it)
            GreenletMapping[gr] = self
            GreenletNames[gr] = method.__name__
            self.timecall(gr, None)           

        except Exception, e:
            nm = method.__name__ if method and hasattr(method, '__name__') else 'no name detected'
            self._exception_handler(e, nm)      
        
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
            output.append('function %s(%s)'%(method.__name__, ', '.join(self.get_arglist(method) + ['callback', 'errorback'])))
            output.append('{')
            output.append("method_call('%s', {%s}, callback, errorback);"%(method.__name__, ', '.join("'%s': %s"%(a, a) for a in self.get_arglist(method))))
            output.append('}')
            output.append("allfuncs['%s'] = %s;"%(method.__name__, method.__name__))
            output.append('')
        return '\n'.join(output)
    
    def handle_exception(self, e, name):
        raise Exception('no exception handler defined -- overwrite handle_exception')
        
    def log_time(self, nm, dif, gr):
        raise Exception('no time logger defined -- overwite log_time')
    
    @staticmethod
    def serialize(obj):
        nonamed = convert_types(obj)
        return json.dumps(nonamed)

def convert_types(obj): #cleans up namedtuples, decimals, dates into serializable things
    if hasattr(obj, '_asdict'): return convert_types(obj._asdict())
    if isinstance(obj, dict):
        return dict((key, convert_types(value)) for key, value in obj.iteritems())
    if isinstance(obj, list) or isinstance(obj, tuple):
        return [convert_types(v) for v in obj]
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    if isinstance(obj, (date, datetime)):
        return str(obj)
    return obj        
       
def build_method_list(object):
    """utility function, introspects a given object to automatically build a method list for it containing all non-underscore method names"""
    return [getattr(object, name) for name in dir(object) if name[0] != '_' and name not in dir(HTTPHandler) and type(getattr(object, name)) is types.MethodType]
    
class NoCacheStaticHandler(tornado.web.StaticFileHandler):
    def set_extra_headers(self, path):
        now = datetime.now()
        stamp = mktime(now.timetuple())
        self.set_header("Date", formatdate(timeval = stamp, localtime = False, usegmt = True))
        if "v" not in self.request.arguments:
            self.set_header("Cache-Control", "no-cache")
