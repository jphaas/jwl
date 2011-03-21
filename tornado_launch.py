from __future__ import absolute_import
import tornado.ioloop
import tornado.web      
from .remote_method import make_handler

def launch(remote_methods, remote_methods_prefix, port):
    application = tornado.web.Application([
        (r"/" + remote_methods_prefix, make_handler(remote_methods)),
    ])
    application.listen(port)
    tornado.ioloop.IOLoop.instance().start()