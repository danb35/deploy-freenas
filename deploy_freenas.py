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
import configparser
import socket
from datetime import datetime, timedelta
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

for cert_data in cert_list:
  if cert_data['cert_name'] == cert:
    new_cert_data = cert_data
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

if FTP_ENABLED:
  # Set our cert as active for FTP plugin
  r = requests.put(
    PROTOCOL + FREENAS_ADDRESS + ':' + PORT + '/api/v1.0/services/ftp/',
    verify=VERIFY,
    auth=(USER, PASSWORD),
    headers={'Content-Type': 'application/json'},
    data=json.dumps({
    "ftp_ssltls_certfile": cert,
    }),
  )

  if r.status_code == 200:
    print ("Setting active FTP certificate successful")
  else:
    print ("Error setting active FTP certificate!")
    print (r)
    sys.exit(1)

# Get expired and old certs with same SAN
cert_ids_same_san = set()
cert_ids_expired = set()
for cert_data in cert_list:
  if set(cert_data['cert_san']) == set(new_cert_data['cert_san']):
      cert_ids_same_san.add(cert_data['id'])

  issued_date = datetime.strptime(cert_data['cert_from'], "%c")
  lifetime = timedelta(days=cert_data['cert_lifetime'])
  expiration_date = issued_date + lifetime
  if expiration_date < now:
      cert_ids_expired.add(cert_data['id'])

# Remove new cert_id from lists
if cert_id in cert_ids_expired:
  cert_ids_expired.remove(cert_id)

if cert_id in cert_ids_same_san:
  cert_ids_same_san.remove(cert_id)

# Delete expired and old certificates with same SAN from freenas
for cid in (cert_ids_same_san | cert_ids_expired):
  r = requests.delete(
    PROTOCOL + FREENAS_ADDRESS + ':' + PORT + '/api/v1.0/system/certificate/' + str(cid),
    verify=VERIFY,
    auth=(USER, PASSWORD),
    headers={'Content-Type': 'application/json'},
  )

  for c in cert_list:
    if c['id'] == cid:
      cert_name = c['cert_name']

  if r.status_code == 204:
    print ("Deleting certificate " + cert_name + " successful")
  else:
    print ("Error deleting certificate " + cert_name + "!")
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
