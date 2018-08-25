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

import argparse
import sys
import json
import requests
import subprocess
from datetime import datetime

parser = argparse.ArgumentParser()
parser.add_argument('cert', help='Path to your certificate.')
parser.add_argument('key', help='Path to your private key.')
parser.add_argument('password', help='Login password.')
parser.add_argument('protocol', choices=['http', 'https'], help='Protocol for request.')
parser.add_argument('domain', help='IP or domain to connect to the web interface.')
parser.add_argument('-u', '--username', default='root', help='Login username, default root.')
parser.add_argument('-p', '--port', type=int, help='Port to access the webinterface, default none.')
args = parser.parse_args()

now = datetime.now()
cert = "letsencrypt-%s-%s-%s" %(now.year, now.strftime('%m'), now.strftime('%d'))

# Set url
if not args.port:
    url = args.protocol + '://' +  args.domain
else:
    url = args.protocol + '://' +  args.domain + ':' + str(args.port)

# Load cert/key
with open(args.key, 'r') as file:
  priv_key = file.read()
with open(args.cert, 'r') as file:
  full_chain = file.read()

# Update or create certificatr = requests.post(
r = requests.post(
  url + '/api/v1.0/system/certificate/import/',
  auth=(args.username, args.password),
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
  url + '/api/v1.0/system/certificate/',
  params=limit,
  auth=(args.username, args.password))

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
  url + '/api/v1.0/system/settings/',
  auth=(args.username, args.password),
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
    url + '/api/v1.0/system/settings/restart-httpd-all/',
    auth=(args.username, args.password),
  )
except requests.exceptions.ConnectionError:
  pass # This is expected when restarting the web server
