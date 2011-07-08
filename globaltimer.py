import time
from jwl import deployconfig
import logging

logger = logging.getLogger('ajaxdisplay.GlobalTimer')


starttime = None
buffer = None

def start():
    if not deployconfig.get('debug'): return
    global starttime, buffer
    starttime = time.time()
    buffer = []

def check(msg):
    if not deployconfig.get('debug'): return
    if starttime is not None:
        buffer.append(msg + ': ' + str(time.time() - starttime))
        
def show_output():
    if buffer:
        for l in buffer: logger.debug(l)