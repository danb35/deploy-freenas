#!/usr/local/bin/python

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

import sys
import json
import requests
import subprocess
from datetime import datetime
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

DOMAIN_NAME = "your_fqdn"
PASSWORD = "ReallySecurePassword"

USER = "root"
FREENAS_ADDRESS = "localhost"
VERIFY = False # Or True (Caution! False disables certificate checking)
PRIVATEKEY_PATH = "/root/.acme.sh/" + DOMAIN_NAME + "/" + DOMAIN_NAME + ".key"
FULLCHAIN_PATH = "/root/.acme.sh/" + DOMAIN_NAME + "/fullchain.cer"
PROTOCOL = 'http://'
PORT = '80'
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
  PROTOCOL + FREENAS_ADDRESS + ':' + PORT + '/api/v1.0/system/certificate/import/',
  verify=VERIFY,
  auth=(USER, PASSWORD),
  headers={'Content-Type': 'application/json'},
  data=json.dumps({
  "cert_name": cert,
  "cert_certificate": full_chain,
  "cert_privatekey": priv_key,
  }),
)

if r.status_code == 201:
  print ("Certificate import successful")
else:
  print ("Error importing certificate!")
  print (r)
  sys.exit(1)

# Download certificate list
limit = {'limit': 0} # set limit to 0 to disable paging in the event of many certificates
r = requests.get(
  PROTOCOL + FREENAS_ADDRESS + ':' + PORT + '/api/v1.0/system/certificate/',
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

for index in range(100):
  cert_data = cert_list[index]
  if cert_data['cert_name'] == cert:
    cert_id = cert_data['id']
    break

# Set our cert as active
r = requests.put(
  PROTOCOL + FREENAS_ADDRESS + ':' + PORT + '/api/v1.0/system/settings/',
  verify=VERIFY,
  auth=(USER, PASSWORD),
  headers={'Content-Type': 'application/json'},
  data=json.dumps({
  "stg_guicertificate": cert_id,
  }),
)

if r.status_code == 200:
  print ("Setting active certificate successful")
else:
  print ("Error setting active certificate!")
  print (r)
  sys.exit(1)

# Reload nginx with new cert
try:
  r = requests.post(
    PROTOCOL + FREENAS_ADDRESS + ':' + PORT + '/api/v1.0/system/settings/restart-httpd-all/',
    verify=VERIFY,
    auth=(USER, PASSWORD),
  )
except requests.exceptions.ConnectionError:
  pass # This is expected when restarting the web server
