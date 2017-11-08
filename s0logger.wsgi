#!/usr/bin/python
# Using port of Adafruit GPIO library 
# for CHIP microcontroller
# 
# Author: Michael Eitelwein (michael@eitelwein.net)
#         https://github.com/MEitelwein/S0-Logger
#
# S0 enabled electricity meters send a S0 signal every tickPerkWh
# The S0 tick is detected at the GPIO pin of the CHIP device
# as a rising edge on s0Pin
# The GPIO library triggers S0Triger() based on raising edge 
# and exports values via REST API as a JSON structure
#
# energy is counted in [Wh]
# power is calculated in [W]
# ticksKWH contains S0 ticks per 1 kWh
#   (typically 1000 to 2000, check with your meter device)
# 
# Processing of the s0 signal is indicated by the C.H.I.P.
# status LED going on and off during GPIO processing
# 
# Configs in file /etc/s0logger (will be generated if not existing)
#   debug       = True | False      Print DEBUG output
#   simulate    = True | False      Do not use GPIO HW but simulate S0 signals
#   pidfile     = <path/pidfile>    Where to store pid
#   htmlfile    = <path/file>       HTML file to be generated
#   s0pin       = <GPIO_PIN>        Which PIN to poll for s0
#   ticksperkwh = <number of ticks> See manual of S0 signal source
#   s0blink     = True | False      Blink status LED with S0 signal
#   port        = <port-numer>      Port used by built-in http-server
#   ip          = <ip address>      IP to listen to, 0.0.0.0 means all interfaces

# -*- coding: UTF-8 -*-

import time
import os
import datetime
import signal
import sys
import syslog
import ConfigParser
import json
import thread
import atexit
import bottle
from bottle import route
#import CHIP_IO.GPIO as GPIO


### Reset GPIO when exiting
### ------------------------------------------------
def cleanup():
    logMsg("Cleaning up S0-Logger on " + s0Pin)

    if not SIMULATE:
        GPIO.remove_event_detect(s0Pin)
        GPIO.cleanup(s0Pin)
    
    saveConfig()


### Log msg to syslog or console
### ------------------------------------------------
def logMsg (msg):
    if SIMULATE:
        msg = 'Simulating: ' + msg

    if DEBUG:
        print msg
    else:
        syslog.syslog(syslog.LOG_INFO, msg)

 
### Return string with date and time
### ------------------------------------------------
def strDateTime():
    now = datetime.datetime.now()
    return now.strftime("%d.%m.%Y %H:%M:%S")


### Set up html server for REST API
### ------------------------------------------------
@route('/electricity', method='GET')
def apiElectricity():
    return s0Log

@route('/trigger', method='GET')
def trigger():
    if SIMULATE:
        S0Trigger(s0Pin)
        return 'Triggered!'
    else:
        return 'Not in simulation mode!'

def apiServer(ip, p, dbg):
    run(app, host=ip, port=p, debug=dbg, quiet=dbg)


### Control C.H.I.P. status LED
### mode=1 will switch on, 0 will switch off
### ------------------------------------------------
def statusLED(mode):
    if s0Blink:
        if ( mode == 1 ):
            # Switch C.H.I.P. status LED on
            if not SIMULATE:
                os.system("/usr/sbin/i2cset -f -y 0 0x34 0x93 0x1")
        else:
            # Switch C.H.I.P. status LED off
            if not SIMULATE:
                os.system("/usr/sbin/i2cset -f -y 0 0x34 0x93 0x0")


### Function being called by GPIO edge detection
### edge_handler is sending GPIO port as argument
### ------------------------------------------------
def S0Trigger(channel):
    global lastTrigger
    statusLED(1)
    triggerTime =  time.time()
    s0Log['data']['time']     = strDateTime()
    s0Log['data']['S0-ticks'] += 1
    # dEnergy in [Wh]
    # dTime in [s]
    dEnergy  = 1000 / ticksKWH;
    s0Log['data']['dtime']    = triggerTime - lastTrigger
    s0Log['data']['energy']  += dEnergy
    s0Log['data']['power']    = dEnergy * 3600 / s0Log['data']['dtime']
    if DEBUG:
        msg  = 'Trigger at ' + s0Log['data']['time']
        msg += ' after '     + str(s0Log['data']['dtime'])       + ' seconds,'
        msg += ' at '        + str(s0Log['data']['energy']/1000) + 'kWh, '
        msg += ' consuming ' + str(s0Log['data']['power'])       + 'W'
        logMsg(msg)
    lastTrigger = triggerTime
    # write cache info to config file every 1 kWh
    # to still have energy reading in case of power loss
    if (s0Log['data']['energy'] % 1000) == 0:
        saveConfig()
    statusLED(0)


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

    # save current energy reading
    if not config.has_section('Cache'):
        config.add_section('Cache')
    config.set('Cache', 'energy', s0Log['data']['energy'])

    with open(configFile, 'w') as configfile:
        config.write(configfile)


### ===============================================
### MAIN
### ===============================================
os.chdir(os.path.dirname(__file__))

s0Log = {
    'data': {
        'energy'  : 0.0,
        'power'   : 0,
        'time'    : 0,
        'dtime'   : 0,
        'S0-ticks': 0,
        'version' : 1.4
        },
    'units': {
        'energy'  : 'Wh',
        'power'   : 'W',
        'time'    : 'dd.mm.yyyy hh:mm:ss',
        'dtime'   : 's',
        'S0-ticks': '',
        'version' : ''
        }
    }
s0Log['data']['time'] = strDateTime()
lastTrigger           = time.time()

# default values for config
DEBUG                 = False
SIMULATE              = True
if SIMULATE:
    configFile            = 'config/s0logger.conf'
else:
    configFile            = '/etc/s0logger'
pidFile               = '/var/run/s0logger.pid'
ticksKWH              = 1000
port                  = 8080
ip                    = '0.0.0.0'
s0Pin                 = 'XIO-P1'
s0Blink               = True

# Check for configs
config = ConfigParser.ConfigParser()
if not os.path.isfile(configFile):
    createConfig()    

config.read(configFile)
if not config.has_section('Config'):
    logMsg('Config file misses section \'Config\' - will create new configuration')
    createConfig()

if config.has_option('Config', 'DEBUG'):
    DEBUG    = config.get('Config', 'DEBUG').lower() == 'true'
else:
    config.set('Config', 'DEBUG', str(DEBUG))

if config.has_option('Config', 'SIMULATE'):
    SIMULATE = config.get('Config', 'SIMULATE').lower() == 'true'
else:
    config.set('Config', 'SIMULATE', str(SIMULATE))

if config.has_option('Config', 'pidFile'):
    pidFile  = config.get('Config', 'pidFile')
else:
    config.set('Config', 'pidFile', pidFile)

if config.has_option('Config', 'port'):
    port = int(config.get('Config', 'port'))
else:
    config.set('Config', 'port', str(port))

if config.has_option('Config', 'ip'):
    ip = config.get('Config', 'ip')
else:
    config.set('Config', 'ip', ip)

if config.has_option('Cache', 'energy'):
    s0Log['data']['energy'] = float(config.get('Cache', 'energy'))
else:
    config.set('Cache', 'energy', str(s0Log['data']['energy']))

if config.has_option('Config', 'ticksPerkWh'):
    ticksKWH = int(config.get('Config', 'ticksPerkWh'))
else:
    config.set('Config', 'ticksPerkWh', str(ticksKWH))

if config.has_option('Config', 'S0Pin'):
    s0Pin    = config.get('Config', 'S0Pin')
else:
    config.set('Config', 'S0Pin', s0Pin)

if config.has_option('Config', 's0Blink'):
    s0Blink  = config.get('Config', 's0Blink').lower() == 'true'
else:
    config.set('Config', 's0Blink', str(s0Blink))

saveConfig()

# Switch status LED off
statusLED(0)

# Open syslog
syslog.openlog(ident="S0-Logger",logoption=syslog.LOG_PID, facility=syslog.LOG_LOCAL0)

# Config GPIO pin for pull down and detection of rising edge
logMsg("Setting up S0-Logger on " + s0Pin)
if not SIMULATE:
    GPIO.cleanup(s0Pin)
    GPIO.setup(s0Pin, GPIO.IN, GPIO.PUD_DOWN)
    GPIO.add_event_detect(s0Pin, GPIO.RISING)
    GPIO.add_event_callback(s0Pin, S0Trigger)

atexit.register(cleanup)


# Start HTTP server for REST API
# start only if not called by apache-wsgi
if __name__ == '__main__':
    thread.start_new_thread(apiServer, (ip, port, DEBUG))
else:
    application = bottle.default_app()
