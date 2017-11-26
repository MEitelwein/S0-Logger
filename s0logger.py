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

import os
import time
import datetime
import sys
import syslog
import ConfigParser
import json
import atexit
from bottle import Bottle, route, run, template, request
import CHIP_IO.GPIO as GPIO

### Reset GPIO when exiting
### ------------------------------------------------
def cleanup():
    logMsg("Cleaning up S0-Logger on " + settings['s0Pin'])

    if not settings['SIMULATE']:
        GPIO.remove_event_detect(settings['s0Pin'])
        GPIO.cleanup(settings['s0Pin'])
    
    saveConfig(settings['configFileName'])


### Log msg to syslog or console
### ------------------------------------------------
def logMsg (msg):
    if settings['SIMULATE']:
        msg = 'Simulating: ' + msg

    if settings['DEBUG']:
        print >> sys.stderr, msg
    else:
        syslog.syslog(syslog.LOG_INFO, msg)

 
### Return string with date and time
### ------------------------------------------------
def strDateTime():
    now = datetime.datetime.now()
    return now.strftime("%d.%m.%Y %H:%M:%S")


### Set bottle app up
### ------------------------------------------------
app = Bottle()
url = '/s0'

# In dev/debug mode add 's0' to URL
if __name__ == '__main__':
    settings['urlPath'] = url
else:
    settings['urlPath'] = ''


### REST API /electricity to get S0 log
### ------------------------------------------------
@app.route(settings['urlPath']+'/electricity', method='GET')
def apiElectricity():
    return s0Log


### REST API /trigger to trigger S0 when simulating
### ------------------------------------------------
@app.route(settings['urlPath']+'/trigger', method='GET')
def apiTrigger():
    if settings['SIMULATE']:
        S0Trigger(settings['s0Pin'])
        return 'Triggered!'
    else:
        return 'Not in simulation mode!'


### REST API /version to get version info
### ------------------------------------------------
@app.route(settings['urlPath']+'/version', method='GET')
def apiVersion():
    msg = {}
    msg['application'] = 'S0-Logger'
    msg['version']     = s0Log['data']['version']
    return msg


### REST API /config to adjust configuration
### ------------------------------------------------
@app.route(settings['urlPath']+'/config', method='GET')
def apiSetConfig():
    old = s0Log['data']['energy']

    if request.GET.save:
        # Will need to add checks here that API is used correctly
        new = request.GET.energy.strip()
        new = new.replace(',', '.')
        s0Log['data']['energy'] = float(new)
        settings['DEBUG']    = request.GET.debug.strip().lower()    == 'true'
        settings['SIMULATE'] = request.GET.simulate.strip().lower() == 'true'
        settings['s0Blink']  = request.GET.blink.strip().lower()    == 'true'

        msg  = '<h3>Configuration was updated</h3>'
        msg += '<ul>'
        if old == s0Log['data']['energy']:
            msg += '<li>Energy: unchanged</li>'
        else:
            msg += '<li>Energy changed from '
            msg += '%s Wh to %s Wh</li>' % (old, s0Log['data']['energy'])
        msg += '<li>Debug: '      + str(settings['DEBUG'])    + '</li>'
        msg += '<li>Simulation: ' + str(settings['SIMULATE']) + '</li>'
        msg += '<li>s0Blink: '    + str(settings['s0Blink'])  + '</li>'
        msg += '</ul>'
        saveConfig(settings['configFileName'])
        return msg       
    else:
        return template('config.tpl', energy=old, path=url, debug=settings['DEBUG'], simulate=settings['SIMULATE'], blink=settings['s0Blink'])


### Start built-in server for dev/debug
### ------------------------------------------------
def apiServer(ip, p, dbg):
    run(app, host=ip, port=p, debug=dbg, quiet=dbg)


### Control C.H.I.P. status LED
### mode=1 will switch on, 0 will switch off
### ------------------------------------------------
def statusLED(mode):
    if settings['s0Blink']:
        if ( mode == 1 ):
            # Switch C.H.I.P. status LED on
            if not settings['SIMULATE']:
                os.system('/usr/sbin/i2cset -f -y 0 0x34 0x93 0x1')
        else:
            # Switch C.H.I.P. status LED off
            if not settings['SIMULATE']:
                os.system('/usr/sbin/i2cset -f -y 0 0x34 0x93 0x0')


### Function being called by GPIO edge detection
### edge_handler is sending GPIO port as argument
### ------------------------------------------------
def S0Trigger(channel):
    statusLED(1)
    triggerTime = time.time()
    s0Log['data']['time']      = strDateTime()
    s0Log['data']['S0-ticks'] += 1
    # dEnergy in [Wh]
    # dTime in [s]
    dEnergy  = 1000 / settings['ticksKWH'];
    s0Log['data']['dtime']    = triggerTime - settings['lastTrigger']
    s0Log['data']['energy']  += dEnergy
    s0Log['data']['power']    = dEnergy * 3600 / s0Log['data']['dtime']
    if settings['DEBUG']:
        msg  = 'Trigger at ' + s0Log['data']['time']
        msg += ' after '     + str(s0Log['data']['dtime'])       + ' seconds,'
        msg += ' at '        + str(s0Log['data']['energy']/1000) + ' kWh, '
        msg += ' consuming ' + str(s0Log['data']['power'])       + ' W'
        logMsg(msg)
    settings['lastTrigger'] = triggerTime
    # write cache info to config file every 1 kWh
    # to still have energy reading in case of power loss
    if (s0Log['data']['energy'] % 1000) == 0:
        updateConfig(settings['configFileName'])
    statusLED(0)


### Initialize GPIO system
### ------------------------------------------------
def configGPIO(pin):
    if not settings['triggerActive']:
        if not settings['SIMULATE']:
            # Config GPIO pin for pull down
            # and detection of rising edge
            GPIO.cleanup(pin)
            GPIO.setup(pin, GPIO.IN, GPIO.PUD_DOWN)
            GPIO.add_event_detect(pin, GPIO.RISING)
            GPIO.add_event_callback(pin, S0Trigger)
        settings['triggerActive'] = True
        logMsg("Setting up S0-Logger on " + pin)
    else:
        logMsg("Trigger already active on " + pin)


### Create config file if not existing
### ------------------------------------------------
def createConfig(configFileName):
    if not config.has_section('Config'):
        config.add_section('Config')
    if not config.has_section('Cache'):
        config.add_section('Cache')
    with open(configFileName, 'w') as configFile:
        config.write(configFile)


### Load config file and create if not existing
### ------------------------------------------------
def loadConfig(configFileName):
    # Create configFile if not exisiting
    if not os.path.isfile(configFileName):
        createConfig(configFileName)

    # Try to read in config
    config.read(configFileName)
    # Check for sections in config
    if not (config.has_section('Config') and config.has_section('Cache')):
        logMsg('Config file misses section "Config" or "Cache" - will create new configuration')
        createConfig(configFileName)

    if config.has_option('Config', 'DEBUG'):
        settings['DEBUG']    = config.get('Config', 'DEBUG').lower() == 'true'

    if config.has_option('Config', 'SIMULATE'):
        settings['SIMULATE'] = config.get('Config', 'SIMULATE').lower() == 'true'

    if config.has_option('Config', 'port'):
        settings['port']     = int(config.get('Config', 'port'))

    if config.has_option('Config', 'ip'):
        settings['ip']       = config.get('Config', 'ip')

    if config.has_option('Cache', 'energy'):
        s0Log['data']['energy'] = float(config.get('Cache', 'energy'))

    if config.has_option('Config', 'ticksPerkWh'):
        settings['ticksKWH'] = int(config.get('Config', 'ticksPerkWh'))

    if config.has_option('Config', 'S0Pin'):
        settings['s0Pin']    = config.get('Config', 's0Pin')

    if config.has_option('Config', 's0Blink'):
        settings['s0Blink']  = config.get('Config', 's0Blink').lower() == 'true'

    if DEBUG:
        logMsg('Config loaded')


### Save config file
### ------------------------------------------------
def saveConfig(configFileName):
    # re-read in case it had been manually edited
    config.read(configFileName)

    if not config.has_section('Config'):
        config.add_section('Config')

    if not config.has_section('Cache'):
        config.add_section('Cache')

    config.set('Config', 'DEBUG',       str(settings['DEBUG']))
    config.set('Config', 'SIMULATE',    str(settings['SIMULATE']))
    config.set('Config', 's0Blink',     str(settings['s0Blink']))
    config.set('Config', 'port',        str(settings['port']))
    config.set('Config', 'ticksPerkWh', str(settings['ticksKWH']))
    config.set('Config', 'ip',              settings['ip'])
    config.set('Config', 's0Pin',           settings['s0Pin'])
    config.set('Cache',  'energy',      s0Log['data']['energy'])

    with open(configFileName, 'w') as configFile:
        config.write(configFile)

    if DEBUG:
        logMsg('Config saved')


### Update Cache section in config file before exiting
### --------------------------------------------------
def updateConfig(configFileName):
    # re-read in case it had been manually edited
    config.read(configFileName)

    if not config.has_section('Cache'):
        config.add_section('Cache')

    config.set('Cache', 'energy', s0Log['data']['energy'])

    with open(configFileName, 'w') as configFile:
        config.write(configFile)

    if DEBUG:
        logMsg('Config updated')



### ===============================================
### MAIN
### ===============================================
# Data structure for S0 log
s0Log    = {
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

# Define default settings
settings = {
    'DEBUG'          = False,
    'SIMULATE'       = True,
    'configFileName' = 'config/s0logger.conf',
    'ticksKWH'       = 1000,
    'port'           = 8080,
    'ip'             = '0.0.0.0',
    's0Pin'          = 'XIO-P1',
    's0Blink'        = False,
    'triggerActive'  = False
    }
setttings['lastTrigger'] = time.time()

# Open syslog
syslog.openlog(ident="S0-Logger",logoption=syslog.LOG_PID, facility=syslog.LOG_LOCAL0)

# Read config in ConfigFileName
config = ConfigParser.ConfigParser()
loadConfig(settings['configFileName'])
saveConfig(settings['configFileName'])

if settings['DEBUG']:
    logMsg('S0-Logger starting')

# Switch status LED off
statusLED(0)

# Config GPIO
configGPIO(settings['s0Pin'])

# Register handle at process exit
atexit.register(cleanup)

# Start HTTP server for REST API
# start only if not called by apache-wsgi
if __name__ == '__main__':
    apiServer(settings['ip'], settings['port'], DEBUG)


