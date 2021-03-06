import boto.sdb.connection
import boto.s3.connection
import boto.ses.connection
import tornado.httpclient
import tornado.ioloop
import urlparse
import functools
import hashlib
import remote_method
import mimetools
from jwl.globaltimer import check, show_output
from boto.connection import AWSAuthConnection


import greenlet

class AsyncHttpResponse(object):
    def __init__(self, status, reason, body, buffer, headers):
        self.status = status
        self.reason = reason
        self.body = body
        self.buffer = buffer
        self.headers = headers
        if buffer is None:
            raise Exception('Missing buffer:\nStatus:\n' + unicode(status) + '\nbody:\n' + unicode(body) + '\nheaders:\n' + unicode(headers))
        self.msg = mimetools.Message(buffer)
    def read(self, bytes = -1):
        if bytes == -1:
            self.buffer.seek(0)
        return self.buffer.read(bytes)
    def getheader(self, name, default=None):
        return self.headers.get(name,default)

class AsyncHttpConnection(object):
    def __init__(self, owner):      
        self.host = None
        self.is_secure = None
        self.headers = {}
        self.owner = owner
        
    def request(self, method, path, data, headers):
        self.method = method
        self.path = path
        self.data = data
        self.headers = headers  

    def close(self): #does nothing, exists for compatibility
        pass

    def putrequest(self, method, path):
        self.method = method
        self.path = path
        self.data = ''
    def putheader(self, key, header):
        self.headers[key] = header
    def endheaders(self):
        pass
    def set_debuglevel(self, level):
        pass
    def send(self, data):
        self.data += data

    def _callback(self, cb, tornado_response):
        cb(tornado_response)
        
    def getresponse(self):
        cb = remote_method.get_resume_cb()
        if cb is None:  #can't make an async call, so do it syncronously AWSAuthConnection
            con = AWSAuthConnection.get_http_connection(self.owner, self.host, self.is_secure)
            con.request(self.method, str(self.path), self.data, self.headers)
            return con.getresponse()
        http_client = tornado.httpclient.AsyncHTTPClient()
        if self.is_secure:
            schema = "https"
        else:
            schema = "http"
        url = str("%s://%s%s" % (schema, self.host, self.path))
        request = tornado.httpclient.HTTPRequest(url,self.method, self.headers, self.data or '', request_timeout=120)
        
        
        http_client.fetch(request, functools.partial(self._callback, cb))
        tornado_response = remote_method.yield_til_resume()
        # if tornado_response.error is not None:     #LET BOTO HANDLE ERRORS
            # tornado_response.rethrow()
        response = AsyncHttpResponse(tornado_response.code, "???", tornado_response.body, tornado_response.buffer, tornado_response.headers)
        return response
        
class AsyncConnectionMixin(object):
    def get_http_connection(self, host, is_secure):
        if not remote_method.on_greenlet():
            return super(AsyncConnectionMixin, self).get_http_connection(host, is_secure)
        if not hasattr(self, "_async_http_connection"):
            self._async_http_connection = AsyncHttpConnection(self)
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
    
class AsyncSESConnection(AsyncConnectionMixin, boto.ses.connection.SESConnection):
    pass
    
