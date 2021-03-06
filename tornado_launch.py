from __future__ import absolute_import
import tornado.ioloop
import tornado.web
import tornado.httpclient
from .utils import curlpatch
from tornado.httpserver import HTTPServer
import time
import logging
import sys
import traceback
import os

tornado.httpclient.AsyncHTTPClient.configure("tornado.curl_httpclient.CurlAsyncHTTPClient")

logger = logging.getLogger('jwl.tornado_launch')

def launch(application, port):
    server = HTTPServer(application)
    application._my_server = server
    retries = 0
    logger.info('about to try to connect')
    while True:
        try:
            server.listen(port, "")
            break
        except Exception, e:
            # if retries < 40 / 0.01:
            time.sleep(0.01)
            retries += 1
            if retries % 500 == 0:
                logger.info('still trying to gain access to port: ' + unicode(e))
            # else:
            #     raise
    try:
        i = tornado.ioloop.IOLoop.instance()
        logger.info('server started succesfully, starting ioloop')
        i.start()
    except:
        logger.info(traceback.format_exc())