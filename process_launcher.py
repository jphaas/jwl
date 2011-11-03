#launches a child process.  When it gets a termination signal, passes that on to the child process.  Ends when the child process ends
#python /home/ec2-user/keyword/code/launch_server.py

import sys
import subprocess
import time
import logging

baselogger = logging.getLogger()
std_out = logging.StreamHandler()
baselogger.addHandler(std_out)
baselogger.setLevel(level=logging.DEBUG)

child_command = sys.argv[1]

baselogger.info('starting subprocess....')

p = subprocess.Popen(child_command.split(' '), stdin=None, stdout=None, stderr=None)

class EscapeException(Exception):
    pass

import signal
def on_term(s, trace):
    baselogger.info('got termination signal, terminating child')
    p.send_signal(signal.SIGTERM)
    baselogger.info('terminated child')
    raise EscapeException()
signal.signal(signal.SIGTERM, on_term)

try:
    while True:
        s = p.poll()
        if s:
            raise Exception('CHILD PROCESS TERMINATED ON ITS OWN')
        time.sleep(0.01)
except EscapeException:
    pass
    
baselogger.info('and we are done')