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
import email.utils
import cProfile
from os.path import exists, join
from os import mkdir, makedirs


#disable tornado logging requests, since this seems to cause weirdness with the profiler
import tornado.web
tornado.web.Application.log_request = lambda self, handler: True

bug = None
def set_bug(bugfunc):
    global bug
    bug = bugfunc

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
buglogger = logging.getLogger('keyword.bugs')

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
    
class CannotResumeException(Exception):
    """
    For sending an exception to a greenlet thread to notify it that it will never get the value that it is waiting on
    """
    pass
    
class GRWrapperException(Exception):
    pass
       
def no_serialize(func):
    func.do_not_serialize = True
    return func
    
def http_method(method):
    def modifier(func):
        func._http_type = method
        return func
    return modifier
    
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
            raise Exception('uncrecognized datatype: ' + unicode(dt))
    return d
    
  
def make_dummy_handler(subclass):
    class Handle(subclass):
        def __init__(self):
            pass
    return Handle()
    

       
def get_resume_cb():
    if not on_greenlet():
        raise Exception('not on greenlet so cannot get resume callback')
    gr = greenlet.getcurrent()
    def cb(value, success=True):
        if greenlet.getcurrent().parent != None:
            raise Exception('Calling callback from within sub-greenlet!')
        if success:
            gr.switch(value)
        else:
            gr.throw(CannotResumeException, value)
    return cb
       
def yield_til_resume():
    return greenlet.getcurrent().parent.switch()
    
def on_greenlet():
    return greenlet.getcurrent().parent != None
    
def run_on_gr(func):
    def do_it(_):
        return func()
    return greenlet.greenlet(do_it).switch(None)
       
       
###
# CACHE MANAGEMENT
###     

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
    modified_cache[unicode(name) + '_' + unicode(version) + '_modified'] = time.time()
    if delete_old:
        for key in name_cache.keys():
            if key < version: del name_cache[key] 

def _modified(last_modified, handler):
    ims_value = handler.request.headers.get("If-Modified-Since")
    if ims_value is not None:
        date_tuple = email.utils.parsedate(ims_value)
        if_since = datetime.fromtimestamp(time.mktime(date_tuple))
        # print 'about to compare', if_since, datetime.fromtimestamp(last_modified)
        if if_since >= datetime.fromtimestamp(last_modified):
            raise Send304Exception()
    handler.set_header("Date", formatdate(timeval = time.time(), localtime = False, usegmt = True))
    handler.set_header('Last-Modified', formatdate(timeval = last_modified, localtime = False, usegmt = True))

#if handler is set, sets the last-modified header on handler and raises a 304 exception if appropriate
def fetch_cache_resource(fetcher, name, version, return_old_okay = True, delete_old = True, handler=None):
    def do_fetch_once():
        if gwaiting_on.has_key((name, version)):
            grc = get_resume_cb()
            gwaiting_on[(name, version)].append(grc)
            ret = yield_til_resume()
            if handler: _modified(modified_cache[unicode(name) + '_' + unicode(version) + '_modified'], handler)
            return ret
        else:
            gwaiting_on[(name, version)] = []
            result = fetcher(version)
            save_resource(name, version, result, delete_old)
            for cb in gwaiting_on[(name, version)]:
                do_later_event_loop(functools.partial(cb, result))
            del gwaiting_on[(name, version)]
            if handler: _modified(modified_cache[unicode(name) + '_' + unicode(version) + '_modified'], handler)
            return result
    if gresource_cache.has_key(name):
        name_cache = gresource_cache[name]
        if name_cache.has_key(version):
            if handler: _modified(modified_cache[unicode(name) + '_' + unicode(version) + '_modified'], handler)
            return name_cache[version]
        elif return_old_okay:
            old_ver = max(name_cache.keys())
            do_later_event_loop(lambda: run_on_gr(do_fetch_once))
            if handler: _modified(modified_cache[unicode(name) + '_' + unicode(old_ver) + '_modified'], handler)
            return name_cache[old_ver]        
    return do_fetch_once()
        

###
# Thread queues and doing things later
###

queues = {}
queues['task'] = Queue.Queue()
queues['callback'] = Queue.Queue()
threads = {}


#CONSIDER USING THIS INSTEAD:
#http://docs.python.org/library/multiprocessing.html

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
    def do_it():
        try:
            ret = func()
            tornado.ioloop.IOLoop.instance().add_callback(lambda: cb(ret))
        except Exception, e:
            bug(e)
            tornado.ioloop.IOLoop.instance().add_callback(lambda: cb('execute_async function raised an exception', False))
    do_later(do_it, t=t)
    return yield_til_resume()
 
#executes function on the main event loop, but at a seperate time.  YOU ARE RESPONSIBLE FOR WRAPPING IT IN A GREENLET IF NECESSARY
def do_later_event_loop(func):
    _dl_helper(func, tornado.ioloop.IOLoop.instance().add_callback)
    
#like do_later_event_loop except inserts a delay in seconds before executing    
def do_later_timeout(self, delay, func):
    _dl_helper(func, lambda cb: tornado.ioloop.IOLoop.instance().add_timeout(time.time() + delay, cb))
    
def _dl_helper(func, adder):
    def do_it():
        try:
            func()
        except Exception, e:
            bug(e)
    adder(do_it)

           
class HTTPHandler(tornado.web.RequestHandler, AuthMixin):
    """  
    Override GetFunctionList() to provide the list of method to convert.
    """
    profiling_path = 'profiling'
    @tornado.web.asynchronous
    def get(self):
        self._handle()
    @tornado.web.asynchronous
    def post(self):
        self._handle()
                
    def on_connection_close(self):
        self._dead = True
        
    def async_wait(self):
        self.async_set()
        return yield_til_resume()
        
    def async_set(self):
        self._gr_cb = get_resume_cb()
        
    def async_finish(self, result):
        if hasattr(self, '_gr_cb') and self._gr_cb:
            do_later_event_loop(functools.partial(self._gr_cb, result))
            self._gr_cb = None    
        
    def set_timeout(self, delay, returnValue):  #return value can either be a value to be sent back, 
                                                #or a function that should call async finish
        def callback():
            if callback in self._my_application.all_pending_timeouts:
                self._my_application.all_pending_timeouts.remove(callback)
            if hasattr(self, '_gr_cb') and self._gr_cb:
                if hasattr(returnValue, '__call__'):
                    returnValue()
                else:    
                    self.async_finish(returnValue)
        if not hasattr(self._my_application, 'all_pending_timeouts'):
            self._my_application.all_pending_timeouts = set()
        self._my_application.all_pending_timeouts.add(callback)
        return tornado.ioloop.IOLoop.instance().add_timeout(time.time() + delay, callback)
        
    #timeout_pointer should be the return value of set_timeout
    def cancel_timeout(self, timeout_pointer):
        tornado.ioloop.IOLoop.instance().remove_timeout(timeout_pointer)
        
    def safe_finish(self):
        try:
            if not self._finished and not hasattr(self, '_dead'):
                self.finish()
        except Exception, e:
            if unicode(e).find('write() on closed GzipFile object') != -1:
                return
            if unicode(e).find('I/O operation on closed file') != -1:
                return
            if unicode(e).find('Request closed') != -1:
                return
            raise
            
    def _handle(self):
        method = None
        methodname = "could not load method"
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
                self.methodname = methodname
            try:
                method = filter(lambda m: m.__name__ == methodname, self.get_method_list())[0]
            except IndexError:
                raise Exception('invalid method name: ' + methodname)
            
            arglist = self.get_arglist(method)
                          
            args = dict((argname, deserialize(self.get_argument(argname), argname) if i.has_key(argname) else None) for argname in arglist)
            args1 = dict((k, v if k not in ('pw', 'password', 'pw2') else '****') for k, v in args.iteritems()) 
            logger.debug(method.__name__ + ' ' + repr(args1))
            
            def do_it(): 
                try:
                    x = method(**args)
                    self.postprocess()
                    
                    if not hasattr(method, 'do_not_serialize'):
                        x = self.serialize(x)
                    self.write(x)
                    self.safe_finish()

                except Send304Exception:
                    self.set_status(304)
                    self.safe_finish()
                except Exception, e:
                    r = self.handle_exception(e, methodname)
                    self.write(self.serialize(r))
                    self.safe_finish()
                      
            if deployconfig.get('debug'):      
                if not exists(self.profiling_path):
                    makedirs(self.profiling_path)
                cProfile.runctx('run_on_gr(do_it)', globals(), locals(), join(self.profiling_path, methodname))
            else:
                run_on_gr(do_it)   
                   
        except Exception, e:
            r = self.handle_exception(e, methodname)
            self.write(self.serialize(r))
            self.safe_finish()  
        
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
            if hasattr(method, '_http_type'):
                type = method._http_type
            else:
                type = 'POST'
            output.append('function %s(%s)'%(method.__name__, ', '.join(self.get_arglist(method) + ['callback', 'errorback'])))
            output.append('{')
            output.append("var type = '%s';"%type)
            output.append("method_call('%s', {%s}, callback, errorback, type);"%(method.__name__, ', '.join("'%s': %s"%(a, a) for a in self.get_arglist(method))))
            output.append('}')
            output.append("allfuncs['%s'] = %s;"%(method.__name__, method.__name__))
            output.append('')
        return '\n'.join(output)
    
    def handle_exception(self, e, name):
        raise Exception('no exception handler defined -- overwrite handle_exception')
            
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
        self.postprocess()