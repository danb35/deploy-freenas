#!/usr/bin/env python3

"""
Import and activate a SSL/TLS certificate into TrueNAS SCALE 24.10 or later
Uses the TrueNAS API to make the change, so everything's properly saved in the config
database and captured in a backup.

Requires paths to the cert (including the any intermediate CA certs) and private key.  
Also requires an API key with appropriate permissions.  If deploying to a
remote TrueNAS system, also requires FQDN of the remote NAS.

The config file contains your API key, so it should only be readable by
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
from OpenSSL import crypto
import re

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
PROTOCOL = deploy.get('protocol', "ws")
CONNECT_HOST = deploy.get('connect_host',"localhost")
CONNECT_URI = PROTOCOL + "://" + CONNECT_HOST + "/websocket"

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

def extract_leaf_certificate(fullchain_pem):
    """Extract the first certificate (leaf) from a full chain PEM file."""
    certs = re.findall(r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", 
                       fullchain_pem, re.DOTALL)
    if not certs:
        raise ValueError("No valid certificate found in the provided PEM data.")
    return certs[0]  # Return the first certificate (leaf)

def validate_cert_key_pair(cert_pem, key_pem):
    """Validate that the certificate's public key matches the private key."""
    leaf_cert_pem = extract_leaf_certificate(cert_pem)

    # Load the extracted leaf certificate and key
    cert_obj = crypto.load_certificate(crypto.FILETYPE_PEM, leaf_cert_pem)
    key_obj = crypto.load_privatekey(crypto.FILETYPE_PEM, key_pem)

    # Verify that the certificate's public key matches the private key
    try:
        return cert_obj.get_pubkey().to_cryptography_key().public_numbers() == \
               key_obj.to_cryptography_key().public_key().public_numbers()
    except Exception as e:
        print(f"Validation error: {e}")
        return False

if validate_cert_key_pair(full_chain, priv_key):
    print("✅ Certificate and private key match.")
else:
    print("❌ Certificate and private key do not match.")
    exit(1)

with Client(CONNECT_URI) as c:
    result=c.call("auth.login_with_api_key", API_KEY)
    if result==False:
        print("Failed to authenticate!")
        exit(1)
    # Import the certificate
    args = {"name": cert_name, "certificate": full_chain, "privatekey": priv_key, "create_type": "CERTIFICATE_CREATE_IMPORTED"}
    cert = c.call("certificate.create", args, job=True)
    print("Certificate " + cert_name + " imported.\n")
    cert_id = cert["id"]
    if UI_CERTIFICATE_ENABLED==True:
        # Update the UI to use the new cert
        args = {"ui_certificate": cert_id}
        c.call("system.general.update", args)
        print("UI cert updated to " + cert_name)
  
    if FTP_ENABLED==True:
        # Update the FTP service to use the new cert
        args = {"ssltls_certificate": cert_id}
        c.call("ftp.update", args)
        print("FTP cert updated to " + cert_name)
    
    if APPS_ENABLED==True:
        # Update apps.  Any app whose configuration includes "ix_certificates" where
        # that dictionary includes any content are updated to use the cert we just
        # uploaded.  This should mean any catalog apps for which a certificate has been
        # configured.
        apps = c.call("app.query")
        for app in apps:
            app_config = c.call("app.config", (app["id"]))
            if 'ix_certificates' in app_config and app_config['ix_certificates']:
                c.call("app.update", app["id"], {"values": {"network": {"certificate_id": cert_id}}}, job=True)
                print("App "+ app["id"] + " updated to " + cert_name)
            else:
                print("App " + app["id"] + " not updated.")
            
    if DELETE_OLD_CERTS==True:
        # Delete old certs.  Any existing certs whose name start with CERT_BASE_NAME
        # that aren't what we just uploaded are deleted.  Certs with different names
        # are ignored.  The Force flag isn't used, so attempts to delete a cert that's
        # in use will cause the script to fail.
        certs = c.call("certificate.query")
        for cert in certs:
            name = cert['name']
            if name.startswith(CERT_BASE_NAME) and cert['id'] != cert_id:
                print("Deleting cert "+ name)
                c.call("certificate.delete", cert['id'], job=True)

    # Restart the UI
    c.call("system.general.ui_restart")
