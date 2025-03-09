# deploy-freenas

deploy-freenas.py is a Python script to deploy TLS certificates to a TrueNAS SCALE server using the TrueNAS Websocket API.  This should ensure that the certificate data is properly stored in the configuration database, and that all appropriate services use this certificate.  Its original intent was to be called from an ACME client like [acme.sh](https://github.com/acmesh-official/acme.sh) after the certificate is issued, so that the entire process of issuance (or renewal) and deployment can be automated.  However, it can be used with certificates from any source, whether a different ACME-based certificate authority or otherwise.

Since this script was developed, acme.sh has added a [deployment script](https://github.com/acmesh-official/acme.sh/wiki/deployhooks#25-deploy-the-cert-on-truenas-core-server) which can deploy newly-issued certs to your TrueNAS system, so you may not need this script.  However, it isn't clear whether the acme.sh deployment script handles the services covered by this script (S3, FTP, WebDAV, Apps for SCALE).

# WORK IN PROGRESS
This version of this script is a work in progress, and has had minimal testing.

# Known issues
Connections to the Websocket API will fail if you have a HTTP -> HTTPS redirect enabled, either in TrueNAS itself or in some other system (e.g., Traefik) in front of TrueNAS.  This results from an [issue](https://github.com/truenas/api_client/issues/13) in the upstream API client.  If your NAS has a trusted and valid certificate, or you've set `verify_ssl = false` in `deploy_config`, you may be able to avoid this issue by setting `protocol = wss` in `deploy_config`.

# Status
* TrueNAS 25.04-BETA1 - Works locally (running on the TrueNAS host) and remotely (so long as all dependencies are installed), but see notes below.
* TrueNAS SCALE 24.10 - Works locally and remotely.
* TrueNAS SCALE 24.04 - Works remotely only--the TrueNAS API client isn't installed in this version of TrueNAS.  Will not update certificates for apps on this or earlier versions of TrueNAS SCALE.
* TrueNAS SCALE 23.10 - Same as 24.04.

## Notes for 25.04
Security measures in TrueNAS SCALE 25.04 require that the API keys be passed over a secure channel.  In order to use this script with 25.04, you must set `protocol = wss` in `deploy_config`.  And then, either:
* You must have already deployed a trusted cert to your NAS
* That cert must not be expired
* You must have configured the UI to use that cert
* The address you're using to connect to the NAS (`connect_host` in `deploy_config`) must be named in that cert

Or set `verify_ssl = false` in `deploy_config`.  This will disable validation of the TLS certificate, and should not be used on a routine basis.

# Installation
This script can run on any machine running Python 3 that has network access to your TrueNAS server, but in most cases it's best to run it directly on the TrueNAS box.  Change to a convenient directory and run `git clone https://github.com/danb35/deploy-freenas`.  If you're installing this on your TrueNAS server, it cannot be in your home directory; place it in a convenient place on a storage pool instead.

If you're not running this script on your TrueNAS server itself, you'll need to install the TrueNAS API client; you can do this by running `pip install git+https://github.com/truenas/api_client.git`.

# Usage

The relevant configuration takes place in the `deploy_config` file.  You can create this file either by copying `deploy_config.example` from this repository, or directly using your preferred text editor.  Its format is as follows:

```
[deploy]
api_key = YourReallySecureAPIKey
privkey_path = /some/other/path
fullchain_path = /some/other/other/path
connect_host = baz.bar.foo
verify = false
ui_certificate_enabled = true
ftp_enabled = false
apps_enabled = false
cert_base_name = letsencrypt
protocol = ws
```

Everything but `api_key` and paths to the cert and key are optional, and the defaults are documented in `deploy_config.example`.

An API key is required for authentication.  [Generate a new API token in the UI](https://www.truenas.com/docs/hub/additional-topics/api/#creating-api-keys) first, then add it as `api_key` to the config:
```
api_key = 1-DXcZ19sZoZFdGATIidJ8vMP6dxk3nHWz3XX876oxS7FospAGMQjkOft0h4itJDSP
```

Once you've prepared `deploy_config`, you can run `deploy_freenas.py`.  The intended use is that it would be called by your ACME client after issuing a certificate.  With acme.sh, for example, you'd add `--reloadcmd "/path/to/deploy_freenas.py"` to your command.

There is an optional paramter, `-c` or `--config`, that lets you specify the path to your configuration file. By default the script will try to use `deploy_config` in the script working directoy:

```
/path/to/deploy_freenas.py --config /somewhere/else/deploy_config
```
