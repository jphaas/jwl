from __future__ import absolute_import
import tornado.ioloop
import tornado.web
import tornado.httpclient
from .utils import curlpatch
from tornado.httpserver import HTTPServer
import time

tornado.httpclient.AsyncHTTPClient.configure("tornado.curl_httpclient.CurlAsyncHTTPClient")

def launch(application, port):
    server = HTTPServer(application)
    application._my_server = server
    retries = 0
    while True:
        try:
            server.listen(port, "")
            break
        except:
            if retries < 40 / 0.01:
                time.sleep(0.01)
                retries += 1
            else:
                raise
    print 'server started succesfully, starting ioloop'
    tornado.ioloop.IOLoop.instance().start()