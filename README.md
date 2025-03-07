# deploy-freenas

deploy-freenas.py is a Python script to deploy TLS certificates to a TrueNAS SCALE server using the TrueNAS Websocket API.  This should ensure that the certificate data is properly stored in the configuration database, and that all appropriate services use this certificate.  Its original intent was to be called from an ACME client like [acme.sh](https://github.com/acmesh-official/acme.sh) after the certificate is issued, so that the entire process of issuance (or renewal) and deployment can be automated.  However, it can be used with certificates from any source, whether a different ACME-based certificate authority or otherwise.

Since this script was developed, acme.sh has added a [deployment script](https://github.com/acmesh-official/acme.sh/wiki/deployhooks#25-deploy-the-cert-on-truenas-core-server) which can deploy newly-issued certs to your TrueNAS system, so you may not need this script.  However, it isn't clear whether the acme.sh deployment script handles the services covered by this script (S3, FTP, WebDAV, Apps for SCALE).

# WORK IN PROGRESS
This version of this script is a work in progress.  Connection to a host separate from the one on which the script is being run is not currently supported due to an apparent bug in iX' API client.

# Installation
This script can run on any machine running Python 3 that has network access to your TrueNAS server, but in most cases it's best to run it directly on the TrueNAS box.  Change to a convenient directory and run `git clone https://github.com/danb35/deploy-freenas`.  If you're installing this on your TrueNAS server, it cannot be in your home directory; place it in a convenient place on a storage pool instead.

If you're not running this script on your TrueNAS server itself, you'll need to make sure that the Python `requests` module is available (it's there by default in TrueNAS).  How you'll do that will depend on the OS you're using wherever you're running the script.  You'll also need to install the TrueNAS API client; you can do this by running `pip install git+https://github.com/truenas/api_client.git`.

# Usage

The relevant configuration takes place in the `deploy_config` file.  You can create this file either by copying `deploy_config.example` from this repository, or directly using your preferred text editor.  Its format is as follows:

```
[deploy]
api_key = YourReallySecureAPIKey
connect_host = baz.bar.foo
verify = false
privkey_path = /some/other/path
fullchain_path = /some/other/other/path
ui_certificate_enabled = true
ftp_enabled = false
apps_enabled = false
cert_base_name = letsencrypt
```

Everything but `api_key` is optional, and the defaults are documented in `deploy_config.example`.

On TrueNAS (Core) 12.0 and up you should use API key authentication instead of password authentication.
[Generate a new API token in the UI](https://www.truenas.com/docs/hub/additional-topics/api/#creating-api-keys) first, then add it as `api_key` to the config, which replaces the `password` field:
```
api_key = 1-DXcZ19sZoZFdGATIidJ8vMP6dxk3nHWz3XX876oxS7FospAGMQjkOft0h4itJDSP
```

Once you've prepared `deploy_config`, you can run `deploy_freenas.py`.  The intended use is that it would be called by your ACME client after issuing a certificate.  With acme.sh, for example, you'd add `--reloadcmd "/path/to/deploy_freenas.py"` to your command.

There is an optional paramter, `-c` or `--config`, that lets you specify the path to your configuration file. By default the script will try to use `deploy_config` in the script working directoy:

```
/path/to/deploy_freenas.py --config /somewhere/else/deploy_config
```
