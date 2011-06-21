import boto.sdb.connection
import boto.s3.connection
import tornado.httpclient
import tornado.ioloop
import urlparse
import functools
import hashlib
import remote_method
import mimetools

import greenlet

class AsyncHttpResponse(object):
    def __init__(self, status, reason, body, buffer, headers):
        self.status = status
        self.reason = reason
        self.body = body
        self.buffer = buffer
        self.headers = headers
        self.msg = mimetools.Message(buffer)
    def read(self, bytes = -1):
        return self.buffer.read(bytes)
    def getheader(self, name, default=None):
        return self.headers.get(name,default)

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
        response = AsyncHttpResponse(tornado_response.code, "???", tornado_response.body, tornado_response.buffer, tornado_response.headers)
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
        response = remote_method.yield_til_resume()
        return response
        
class AsyncConnectionMixin(object):
    def get_http_connection(self, host, is_secure):
        if not hasattr(self, "_async_http_connection"):
            self._async_http_connection = AsyncHttpConnection()
        self._async_http_connection.host = host
        self._async_http_connection.is_secure = is_secure
        return self._async_http_connection

    def put_http_connection(self, *args, **kwargs):
        if not hasattr(self, "_async_http_connection"):
            super(AsyncConnectionMixin, self).put_http_connection(*args, **kwargs)
            
class AsyncSDBConnection(AsyncConnectionMixin,boto.sdb.connection.SDBConnection):
    pass
    
class AsyncS3Connection(AsyncConnectionMixin, boto.s3.connection.S3Connection):
    pass
    