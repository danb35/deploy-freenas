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
import time
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

# We'll use the API key if provided
API_KEY = deploy.get('api_key')
# Otherwise fallback to basic password authentication
USER = "root"
PASSWORD = deploy.get('password')

DOMAIN_NAME = deploy.get('cert_fqdn',socket.gethostname())
FREENAS_ADDRESS = deploy.get('connect_host','localhost')
VERIFY = deploy.getboolean('verify',fallback=False)
PRIVATEKEY_PATH = deploy.get('privkey_path',"/root/.acme.sh/" + DOMAIN_NAME + "/" + DOMAIN_NAME + ".key")
FULLCHAIN_PATH = deploy.get('fullchain_path',"/root/.acme.sh/" + DOMAIN_NAME + "/fullchain.cer")
PROTOCOL = deploy.get('protocol','http://')
PORT = deploy.get('port','80')
CERT_BASE_NAME = deploy.get('cert_base_name','letsencrypt')
UPDATE_UI = deploy.getboolean('update_ui',fallback=False)
UPDATE_FTP = deploy.getboolean('update_ftp',fallback=False)
UPDATE_WEBDAV = deploy.getboolean('update_webdav',fallback=False)
now = datetime.now()
cert = "%s-%s-%s-%s-%s" %(CERT_BASE_NAME, now.year, now.strftime('%m'), now.strftime('%d'), ''.join(c for c in now.strftime('%X') if
c.isdigit()))


# Set some general request params
session = requests.Session()
session.headers.update({
  'Content-Type': 'application/json'
})
if API_KEY:
  session.headers.update({
    'Authorization': f'Bearer {API_KEY}'
  })
elif PASSWORD:
  session.auth = (USER, PASSWORD)
else:
  print ("Unable to authenticate. Specify 'api_key' or 'password' in the config.")
  exit(1)

# Load cert/key
with open(PRIVATEKEY_PATH, 'r') as file:
  priv_key = file.read()
with open(FULLCHAIN_PATH, 'r') as file:
  full_chain = file.read()

# Construct BASE_URL
BASE_URL = PROTOCOL + FREENAS_ADDRESS + ':' + PORT

# Update or create certificate
r = session.post(
  BASE_URL + '/api/v2.0/certificate/',
  verify=VERIFY,
  data=json.dumps({
    "create_type": "CERTIFICATE_CREATE_IMPORTED",
    "name": cert,
    "certificate": full_chain,
    "privatekey": priv_key,
  })
)

if r.status_code == 200:
  print ("Certificate import successful")
else:
  print ("Error importing certificate!")
  print (r.text)
  sys.exit(1)

# Sleep for a few seconds to let the cert propagate
time.sleep(5)

# Download certificate list
limit = {'limit': 0} # set limit to 0 to disable paging in the event of many certificates
r = session.get(
  BASE_URL + '/api/v2.0/certificate/',
  verify=VERIFY,
  params=limit
)

if r.status_code == 200:
  print ("Certificate list successful")
else:
  print ("Error listing certificates!")
  print (r.text)
  sys.exit(1)

# Parse certificate list to find the id that matches our cert name
cert_list = r.json()

new_cert_data = None
for cert_data in cert_list:
  if cert_data['name'] == cert:
    new_cert_data = cert_data
    cert_id = new_cert_data['id']
    break

if not new_cert_data:
  print ("Error searching for newly imported certificate in certificate list.")
  sys.exit(1)

if UPDATE_UI:
  # Set our cert as active for UI
  r = session.put(
    BASE_URL + '/api/v2.0/system/general/',
    verify=VERIFY,
    data=json.dumps({
      "ui_certificate": cert_id,
    })
  )

  if r.status_code == 200:
    print ("Setting active UI certificate successful")
  else:
    print ("Error setting active UI certificate!")
    print (r.text)
    sys.exit(1)

if UPDATE_FTP:
  # Set our cert as active for FTP plugin
  r = session.put(
    BASE_URL + '/api/v2.0/ftp/',
    verify=VERIFY,
    data=json.dumps({
      "ssltls_certificate": cert_id,
    }),
  )

  if r.status_code == 200:
    print ("Setting active FTP certificate successful")
  else:
    print ("Error setting active FTP certificate!")
    print (r.text)
    sys.exit(1)

if UPDATE_WEBDAV:
  # Set our cert as active for WEBDAV plugin
  r = session.put(
    BASE_URL + '/api/v2.0/webdav/',
    verify=VERIFY,
    data=json.dumps({
      "certssl": cert_id,
    }),
  )

  if r.status_code == 200:
    print ("Setting active WEBDAV certificate successful")
  else:
    print ("Error setting active WEBDAV certificate!")
    print (r)
    sys.exit(1)

# Get expired and old certs with same SAN
cert_ids_same_san = set()
cert_ids_expired = set()
for cert_data in cert_list:
  if set(cert_data['san']) == set(new_cert_data['san']):
      cert_ids_same_san.add(cert_data['id'])

  issued_date = datetime.strptime(cert_data['from'], "%c")
  lifetime = timedelta(days=cert_data['lifetime'])
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
  r = session.delete(
    BASE_URL + '/api/v2.0/certificate/id/' + str(cid),
    verify=VERIFY
  )

  for c in cert_list:
    if c['id'] == cid:
      cert_name = c['name']

  if r.status_code == 200:
    print ("Deleting certificate " + cert_name + " successful")
  else:
    print ("Error deleting certificate " + cert_name + "!")
    print (r.text)
    sys.exit(1)

if UPDATE_UI:
  # Reload nginx with new cert
  # If everything goes right in 12.0-U3 and later, it returns 200
  # If everything goes right with an earlier release, the request
  # fails with a ConnectionError
  r = session.post(
    BASE_URL + '/api/v2.0/system/general/ui_restart',
    verify=VERIFY
  )
  if r.status_code == 200:
    print ("Reloading WebUI successful")
    print ("deploy_freenas.py executed successfully")
    sys.exit(0)
  elif r.status_code != 405:
    print ("Error reloading WebUI!")
    print (r.text)
    sys.exit(1)
  else:
    try:
      r = session.get(
        BASE_URL + '/api/v2.0/system/general/ui_restart',
        verify=VERIFY
      )
      # If we've arrived here, something went wrong
      print ("Error reloading WebUI!")
      print (r.text)
      sys.exit(1)
    except requests.exceptions.ConnectionError:
      print ("Reloading WebUI successful")

print ("deploy_freenas.py executed successfully")
