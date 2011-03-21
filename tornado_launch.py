from __future__ import absolute_import
import tornado.ioloop
import tornado.web
from .utils import curlpatch

def launch(application, port):
    application.listen(port)
    tornado.ioloop.IOLoop.instance().start()