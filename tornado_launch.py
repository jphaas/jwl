from __future__ import absolute_import
import tornado.ioloop
import tornado.web
import tornado.httpclient
from .utils import curlpatch

tornado.httpclient.AsyncHTTPClient.configure("tornado.curl_httpclient.CurlAsyncHTTPClient")

def launch(application, port):
    application.listen(port)
    tornado.ioloop.IOLoop.instance().start()