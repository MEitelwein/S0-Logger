#!/bin/bash

if [ -e /var/www/s0logger ]; then
    sudo rm -rf /var/www/s0logger
fi

sudo mkdir /var/www/s0logger /var/www/s0logger/config
sudo chgrp www-data /var/www/s0logger/config
sudo chmod g=rwx /var/www/s0logger/config
#sudo a2dismod mpm_event
#sudo a2enmod  mpm_worker 
sudo a2enmod wsgi
sudo a2dissite 000-default.conf

a=$(pwd); sudo ln -s ${a}/s0logger.py /var/www/s0logger
a=$(pwd); sudo ln -s ${a}/s0logger.wsgi /var/www/s0logger
a=$(pwd); sudo ln -s ${a}/request.wsgi /var/www/s0logger
a=$(pwd); sudo ln -s ${a}/config.tpl /var/www/s0logger

if [ -e /etc/apache2/conf-enabled/s0logger.conf ]; then
    sudo rm /etc/apache2/conf-enabled/s0logger.conf
fi
a=$(pwd); sudo ln -s ${a}/apache2-conf-s0logger.conf /etc/apache2/conf-enabled/s0logger.conf

if [ -e /etc/apache2/sites-enabled/s0logger.conf ]; then
    sudo rm /etc/apache2/sites-enabled/s0logger.conf
fi
a=$(pwd); sudo ln -s ${a}/apache2-sites-s0logger.conf /etc/apache2/sites-enabled/s0logger.conf
