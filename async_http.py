import boto.sdb.connection
import boto.s3.connection
import tornado.httpclient
import tornado.ioloop
import urlparse
import functools
import hashlib
import remote_method

import greenlet

class AsyncHttpResponse(object):
    def __init__(self, status, reason, body, headers):
        self.status = status
        self.reason = reason
        self.body = body
        self.headers = headers
    def read(self):
        return self.body
    def getheader(self, name):
        return self.headers.get(name,None)

class AsyncHttpConnection(object):
    def __init__(self):      
        self.host = None
        self.is_secure = None
        
    def request(self, method, path, data, headers):
        self.method = method
        self.path = path
        self.data = data
        self.headers = headers      

    def _callback(self, cb, tornado_response):
        response = AsyncHttpResponse(tornado_response.code, "???", tornado_response.body, tornado_response.headers)
        cb(response)
        
    def getresponse(self):
        http_client = tornado.httpclient.AsyncHTTPClient()
        if self.is_secure:
            schema = "https"
        else:
            schema = "http"
        url = "%s://%s%s" % (schema, self.host, self.path)
        request = tornado.httpclient.HTTPRequest(url,self.method, self.headers, self.data or None)
        
        cb = remote_method.get_resume_cb()
        http_client.fetch(request, functools.partial(self._callback, cb))
        response = remote_method.yield_til_resume():
        return response

def call_async(fn, callback):
    def go():
        ret = fn()
        tornado.ioloop.IOLoop.instance().add_callback(lambda : callback(ret))
    greenlet.greenlet(go).switch()
        
class AsyncConnectionMixin(object):
    """
    Mixin to replace get_http_connection and put_http_connection in a
    subclass of AWSAuthConnection from Boto to create an Async version
    of a connection class.

    All calls to methods in the new Async version must be wrapped in
    call_async calls to make then operate asynchronously.
    """

    def get_http_connection(self, host, is_secure):
        """
        This is called to get an HTTP connection from the pool. This
        is the point at which we inject our replacement http connection
        """
        if not hasattr(self, "_async_http_connection"):
            self._async_http_connection = AsyncHttpConnection()
        self._async_http_connection.host = host
        self._async_http_connection.is_secure = is_secure
        return self._async_http_connection

    def put_http_connection(self, *args, **kwargs):
        if not hasattr(self, "_async_http_connection"):
            super(AsyncConnectionMixin, self).put_http_connection(*args, **kwargs)
            
class AsyncSDBConnection(boto.sdb.connection.SDBConnection,AsyncConnectionMixin):
    pass
    
class AsyncS3Connection(boto.s3.connection.S3Connection, AsyncConnectionMixin):
    pass