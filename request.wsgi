### Simple script to call version API once to launch s0logger at apache2 startup
### Need to start as seperate thread to not block loading of s0logger

import os, sys, thread

def request():
    os.system('/usr/bin/curl -s -o /dev/null http://localhost/s0/version')

thread.start_new_thread(request, ())
