#!/usr/bin/python
# Using port of Adafruit GPIO librar 
# for CHIP board of The Next Thing Corp
# 
# (c) Michael Eitelwein, 2016
# email: michael@eitelwein.net
#
# S0 enabled electricity meters send a S0 signal every tickPerkWh
# The S0 tick is detected at the GPIO pin of the CHIP device
# as a rising edge on s0Pin
# The GPIO library triggers S0Triger() based on raising edge 
# and writes current values into htmlFile as a JSON structure
#
# energy is counted in [Wh]
# power is calculated in [W]
# ticksKWH contains S0 ticks per 1 kWh
#   (typically 1000 to 2000, check with your meter device)
# 

import CHIP_IO.GPIO as GPIO
import time
import os
from datetime import datetime, tzinfo, timedelta
import signal
import sys
import syslog
import ConfigParser


### Reset GPIO when exiting
### ------------------------------------------------
def cleanup():
    logMsg("Cleaning up S0-Logger")
    GPIO.remove_event_detect(s0Pin)
    GPIO.cleanup()    
    if os.path.isfile(pidFile):
        os.remove(pidFile)
    saveConfig()


### Log msg to syslog or console
### ------------------------------------------------
def logMsg (msg):
    if DEBUG:
        print msg
    else:
        syslog.syslog(syslog.LOG_INFO, msg)


### Catch os signals to exit cleanly
### ------------------------------------------------
def signal_term_handler(signal, frame):
    LogMsg("S0-Logger got SIGTERM")
    cleanup()
    sys.exit(0)

 
### Configure datetime formats
### ------------------------------------------------
class Zone(tzinfo):
    def __init__(self,offset,isdst,name):
        self.offset = offset
        self.isdst = isdst
        self.name = name
    def utcoffset(self, dt):
        return timedelta(hours=self.offset) + self.dst(dt)
    def dst(self, dt):
            return timedelta(hours=1) if self.isdst else timedelta(0)
    def tzname(self,dt):
         return self.name


### Write data to html file
### ------------------------------------------------
def writeHTML(energy, power, time, dTime):
    f = open(htmlFile, 'w')
    f.truncate()
    f.write('{')
    f.write('    \"data\": {')
    f.write('                \"energy\": \"' + energy + '\"')
    f.write('              , \"power\": \"'  + power  + '\"')
    f.write('              , \"time\": \"'   + time   + '\"')
    f.write('              , \"dtime\": \"'  + dTime  + '\"')
    f.write('               },')
    f.write('    \"units\": {')
    f.write('                \"energy\": \"Wh\"')
    f.write('              , \"power\": \"W\"')
    f.write('              , \"dtime\": \"s\"')
    f.write('               }')
    f.write('}')
    f.close()


### Function being called by GPIO edge detection
### edge_handler is sending GPIO port as argument
### ------------------------------------------------
def S0Trigger(channel):
    global counter
    global energy
    global lastTrigger
    triggerTime = time.time()
    tStr = datetime.now(CET).strftime('%m.%d.%Y %H:%M:%S %Z')
    counter += 1
    # dEnergy in [Wh]
    # dTime in [s]
    dEnergy  = 1000 / ticksKWH;
    dTime    = triggerTime - lastTrigger
    power    = dEnergy / (dTime / 3600)
    if DEBUG:
        logMsg("Trigger at " + tStr + " after " + str(dTime) + " seconds, at " + str(energy/1000) + "kWh, consuming " + str(power) + "W")
    writeHTML(str(energy), str(power), tStr, str(dTime))
    lastTrigger = triggerTime


### Create config file if not existing
### ------------------------------------------------
def createConfig():
    if not config.has_section('Config'):
        config.add_section('Config')
    if not config.has_section('Cache'):
        config.add_section('Cache')
    with open(configFile, 'w') as configfile:
        config.write(configfile)


### Save Cache section in config file before exiting
### ------------------------------------------------
def saveConfig():
    # re-read in case it had been manually edited
    config.read(configFile)

    # overwrite counter
    if not config.has_section('Cache'):
        config.add_section('Cache')

    config.set('Cache', 'energy', str(energy))
    with open(configFile, 'w') as configfile:
        config.write(configfile)


### ===============================================
### MAIN
### ===============================================

CET         = Zone(1,True,'CET')
counter     = 0
lastTrigger = time.time()
configFile  = "/etc/s0logger"

# Check for configs
config = ConfigParser.ConfigParser()
if not os.path.isfile(configFile):
    createConfig()    

config.read(configFile)
if config.has_option('Config', 'DEBUG'):
    DEBUG    = config.get('Config', 'DEBUG').lower() == 'true'
else:
    DEBUG    = False
    config.set('Config', 'DEBUG', str(DEBUG))

if config.has_option('Config', 'pidFile'):
    pidFile  = config.get('Config', 'pidFile')
else:
    pidFile  = '/var/run/s0logger.pid'
    config.set('Config', 'pidFile', pidFile)

if config.has_option('Config', 'htmlFile'):
    htmlFile = config.get('Config', 'htmlFile')
else:
    htmlFile = '/var/www/html/s0/electricity.html'
    config.set('Config', 'htmlFile', htmlFile)

if config.has_option('Cache', 'energy'):
    energy   = float(config.get('Cache', 'energy'))
else:
    energy   = float(0)
    config.set('Cache', 'energy', str(energy))

if config.has_option('Config', 'ticksPerkWh'):
    ticksKWH = int(config.get('Config', 'ticksPerkWh'))
else:
    ticksKWH = 1000
    config.set('Config', 'ticksPerkWh', str(ticksKWH))

if config.has_option('Config', 'S0Pin'):
    s0Pin    = config.get('Config', 'S0Pin')
else:
    s0Pin    = 'XIO-P1'
    config.set('Config', 'S0Pin', s0Pin)

# Write pid into pidFile
pf = open(pidFile, 'w')
pf.truncate()
pf.write(str(os.getpid()))
pf.close()

# Open syslog
syslog.openlog(ident="S0-Logger",logoption=syslog.LOG_PID, facility=syslog.LOG_LOCAL0)

# Create htmlFile already on startup
writeHTML(str(energy), '0', datetime.now(CET).strftime('%m.%d.%Y %H:%M:%S %Z'), '0')

logMsg("Setting up S0-Logger on " + s0Pin)
GPIO.setup(s0Pin, GPIO.IN, GPIO.PUD_DOWN)
GPIO.add_event_detect(s0Pin, GPIO.RISING, S0Trigger)

# Install signal handler for SIGTERM
signal.signal(signal.SIGTERM, signal_term_handler)

# endless loop while GPIO is waiting for triggers
try:
    while True:
        # WAIT FOR EDGE
        if DEBUG:
            logMsg("Waiting...")
        time.sleep(1)
except:
    pass
    
# Clean up and terminate
cleanup()
logMsg("S0-Logger exited")
