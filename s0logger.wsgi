import sys, os, bottle

os.chdir(os.path.dirname(__file__))
os.environ['PYTHON_EGG_CACHE'] = '/var/www/s0logger/config/.python-egg'
sys.path = ['/var/www/s0logger/'] + sys.path

import s0logger

application = s0logger.app
