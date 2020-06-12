#!/usr/bin/env python3

"""
Import and activate a SSL/TLS certificate into FreeNAS 11.1 or later
Uses the FreeNAS API to make the change, so everything's properly saved in the config
database and captured in a backup.

Requires paths to the cert (including the any intermediate CA certs) and private key,
and username, password, and FQDN of your FreeNAS system.

Your private key should only be readable by root, so this script must run with root
privileges.  And, since it contains your root password, this script itself should
only be readable by root.

Source: https://github.com/danb35/deploy-freenas
"""

import argparse
import os
import sys
import json
import requests
import subprocess
import time
import configparser
import socket
from datetime import datetime
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

parser = argparse.ArgumentParser(description='Import and activate a SSL/TLS certificate into FreeNAS.')
parser.add_argument('-c', '--config', default=(os.path.join(os.path.dirname(os.path.realpath(__file__)),
    'deploy_config')), help='Path to config file, defaults to deploy_config.')
args = parser.parse_args()

if os.path.isfile(args.config):
    config = configparser.ConfigParser()
    config.read(args.config)
    deploy = config['deploy']
else:
    print("Config file", args.config, "does not exist!")
    exit(1)

USER = "root"
PASSWORD = deploy.get('password')

DOMAIN_NAME = deploy.get('cert_fqdn',socket.gethostname())
FREENAS_ADDRESS = deploy.get('connect_host','localhost')
VERIFY = deploy.getboolean('verify',fallback=False)
PRIVATEKEY_PATH = deploy.get('privkey_path',"/root/.acme.sh/" + DOMAIN_NAME + "/" + DOMAIN_NAME + ".key")
FULLCHAIN_PATH = deploy.get('fullchain_path',"/root/.acme.sh/" + DOMAIN_NAME + "/fullchain.cer")
PROTOCOL = deploy.get('protocol','http://')
PORT = deploy.get('port','80')
FTP_ENABLED = deploy.getboolean('ftp_enabled',fallback=False)
now = datetime.now()
cert = "letsencrypt-%s-%s-%s-%s" %(now.year, now.strftime('%m'), now.strftime('%d'), ''.join(c for c in now.strftime('%X') if
c.isdigit()))

# Load cert/key
with open(PRIVATEKEY_PATH, 'r') as file:
  priv_key = file.read()
with open(FULLCHAIN_PATH, 'r') as file:
  full_chain = file.read()

# Update or create certificate
r = requests.post(
  PROTOCOL + FREENAS_ADDRESS + ':' + PORT + '/api/v2.0/certificate/',
  verify=VERIFY,
  auth=(USER, PASSWORD),
  headers={'Content-Type': 'application/json'},
  data=json.dumps({
  "create_type": "CERTIFICATE_CREATE_IMPORTED",
  "name": cert,
  "certificate": full_chain,
  "privatekey": priv_key,
  }),
)

if r.status_code == 200:
  print ("Certificate import successful")
else:
  print ("Error importing certificate!")
  print (r)
  sys.exit(1)

#sleep for a few seconds to let the cert propogate
time.sleep(5)

# Download certificate list
limit = {'limit': 0} # set limit to 0 to disable paging in the event of many certificates
r = requests.get(
  PROTOCOL + FREENAS_ADDRESS + ':' + PORT + '/api/v2.0/certificate/',
  verify=VERIFY,
  params=limit,
  auth=(USER, PASSWORD))

if r.status_code == 200:
  print ("Certificate list successful")
else:
  print ("Error listing certificates!")
  print (r)
  sys.exit(1)

# Parse certificate list to find the id that matches our cert name
cert_list = r.json()
cert_id = ""
for index in range(len(cert_list)):
  cert_data = cert_list[index]
  if cert_data['name'] == cert:
    cert_id = cert_data['id']
    break

if cert_id == "":
  print ("Certificate not found with name " + cert)
  sys.exit(1)

# Set our cert as active
r = requests.put(
  PROTOCOL + FREENAS_ADDRESS + ':' + PORT + '/api/v2.0/system/general/',
  verify=VERIFY,
  auth=(USER, PASSWORD),
  headers={'Content-Type': 'application/json'},
  data=json.dumps({
  "ui_certificate": cert_id,
  }),
)

if r.status_code == 200:
  print ("Setting active certificate successful")
else:
  print ("Error setting active certificate!")
  print (r)
  sys.exit(1)

if FTP_ENABLED:
  # Set our cert as active for FTP plugin
  r = requests.put(
    PROTOCOL + FREENAS_ADDRESS + ':' + PORT + '/api/v2.0/ftp/',
    verify=VERIFY,
    auth=(USER, PASSWORD),
    headers={'Content-Type': 'application/json'},
    data=json.dumps({
    "ssltls_certfile": cert,
    }),
  )

  if r.status_code == 200:
    print ("Setting active FTP certificate successful")
  else:
    print ("Error setting active FTP certificate!")
    print (r)
    sys.exit(1)

# Reload nginx with new cert
try:
  r = requests.post(
    PROTOCOL + FREENAS_ADDRESS + ':' + PORT + '/api/v2.0/system/general/ui_restart',
    verify=VERIFY,
    auth=(USER, PASSWORD),
  )
except requests.exceptions.ConnectionError:
  pass # This is expected when restarting the web server
