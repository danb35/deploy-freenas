#!/usr/bin/env python3

"""
Import and activate a SSL/TLS certificate into FreeNAS 11.1 or later
Uses the FreeNAS/TrueNAS API to make the change, so everything's properly saved in the config
database and captured in a backup.

Requires paths to the cert (including the any intermediate CA certs).  If deploying to a
remote TrueNAS system, also requires FQDN of the remote NAS and an API key with
appropriate permissions.

The config file contains your root password or API key, so it should only be readable by
root.  Your private key should also only be readable by root, so this script must run 
with root privileges.

Source: https://github.com/danb35/deploy-freenas
"""

import argparse
import os
import sys
import json
import time
import configparser
import socket
from datetime import datetime, timedelta
from truenas_api_client import Client

parser = argparse.ArgumentParser(description='Import and activate a SSL/TLS certificate into TrueNAS.')
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

API_KEY = deploy.get('api_key')
CONNECT_HOST = deploy.get('connect_host',"localhost")
CONNECT_URI = "ws://" + CONNECT_HOST + "/websocket"

PRIVATEKEY_PATH = deploy.get('privkey_path')
if os.path.isfile(PRIVATEKEY_PATH)==False:
    print("Private key file must exist!")
    exit(1)
FULLCHAIN_PATH = deploy.get('fullchain_path')
if os.path.isfile(FULLCHAIN_PATH)==False:
    print("Full chain file must exist!")
    exit(1)
UI_CERTIFICATE_ENABLED = deploy.getboolean('ui_certificate_enabled',fallback=True)
FTP_ENABLED = deploy.getboolean('ftp_enabled',fallback=False)
APPS_ENABLED = deploy.getboolean('apps_enabled', fallback=False)
APPS_ONLY_MATCHING_SAN = deploy.getboolean('apps_only_matching_san', fallback=False)
DELETE_OLD_CERTS = deploy.getboolean('delete_old_certs', fallback=False)
CERT_BASE_NAME = deploy.get('cert_base_name','letsencrypt')
now = datetime.now()
cert_name = CERT_BASE_NAME + "-%s-%s-%s-%s" %(now.year, now.strftime('%m'), now.strftime('%d'), ''.join(c for c in now.strftime('%X') if
c.isdigit()))

# Load cert/key
with open(PRIVATEKEY_PATH, 'r') as file:
    priv_key = file.read()
with open(FULLCHAIN_PATH, 'r') as file:
    full_chain = file.read()

with Client() as c:
    # c.call("auth.login_with_api_key", API_KEY)
    # Import the certificate
    args = {"name": cert_name, "certificate": full_chain, "privatekey": priv_key, "create_type": "CERTIFICATE_CREATE_IMPORTED"}
    cert = c.call("certificate.create", args, job=True)
    print("Certificate " + cert_name + " imported.\n")
    cert_id = cert["id"]
    # print("cert_id is " + cert_id + "\n")
    if UI_CERTIFICATE_ENABLED==True:
        # Update the UI to use the new cert
        args = {"ui_certificate": cert_id}
        c.call("system.general.update", args)
        print("UI cert updated to " + cert_name + "\n")
        # Restart the UI
        c.call("system.general.ui_restart")
  
    if FTP_ENABLED==True:
        # Update the FTP service to use the new cert
        args = {"ssltls_certificate": cert_id}
        c.call("ftp.update", args)
        print("FTP cert updated to " + cert_name + "\n")
    
    if APPS_ENABLED==True:
        # Update apps.  Any app whose configuration includes "ix_certificates" where
        # that dictionary includes any content are updated to use the cert we just
        # uploaded.  This should mean any catalog apps for which a certificate has been
        # configured.
        apps = c.call("app.query")
        for app in apps:
            app_config = c.call("app.config", (app["id"]))
            # if app_config.get("ix_certificates") != None:
            if ix_certificates in app_config and app_config['ix_certificates']:
                c.call("app.update", app["id"], {"values": {"network": {"certificate_id": cert_id}}}, job=True)
            
    if DELETE_OLD_CERTS==True:
        # Delete old certs.  Any existing certs whose name start with CERT_BASE_NAME
        # that aren't what we just uploaded are deleted.  Certs with different names
        # are ignored.  The Force flag isn't used, so attempts to delete a cert that's
        # in use will cause the script to fail.
        certs = c.call("certificate.query")
        for cert in certs:
            name = cert['name']
            if name.startswith(CERT_BASE_NAME) and cert['id'] != cert_id:
                c.call("certificate.delete", cert['id'], job=True)
    
