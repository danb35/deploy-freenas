# deploy-truenas

deploy_truenas.py is a Python script to deploy TLS certificates to a TrueNAS SCALE/Community Edition server using the TrueNAS Websocket API.  This should ensure that the certificate data is properly stored in the configuration database, and that all appropriate services use this certificate.  Its original intent was to be called from an ACME client like [acme.sh](https://github.com/acmesh-official/acme.sh) after the certificate is issued, so that the entire process of issuance (or renewal) and deployment can be automated.  However, it can be used with certificates from any source, whether a different ACME-based certificate authority or otherwise.

# Alternatives
This script isn't the only way to automate deployment of a TLS certificate to your TrueNAS SCALE/CE system.  Known alternatives include:
* [TrueNAS' own built-in mechanism](https://wiki.familybrown.org/en/fester/maintain-truenas/letsencrypt-scale).  It's far more complicated than necessary to set up, but if you use one of the supported DNS providers (Cloudflare, Digital Ocean, OVH, or Route53), and you don't need to deploy the same cert anywhere else, it's still probably the simplest way to go.
* Although it doesn't currently (early May 2025) seem to be documented anywhere, `acme.sh` has a deploy hook that works with the websocket API.  The closest I've found to documentation is [this section](https://github.com/acmesh-official/acme.sh/wiki/deployhooks#25-deploy-the-cert-on-truenas-core-server) in its wiki.  Substitute `--deploy-hook truenas_ws` in the given command to use this hook.  Note that as of this writing, this script can only be run on the TrueNAS host to which you're deploying the cert; it doesn't have any option to connect to a different host.
* [tnascert-deploy](https://github.com/jrushford/tnascert-deploy) implements many of the features of this script in Go, resulting in a statically-linked binary you can run pretty much anywhere with no other dependencies.  File size is much larger (roughly 8 MB for the binary vs. 10 KB for this script), but simplicity of installation may outweigh this, and the comparison is a little misleading, as it doesn't account for this script's dependencies.  Binaries are presently available for Linux/x64, FreeBSD/x64, macOS/ARM, and Windows, or you can build it yourself under any OS using Go.

Support for any of these, of course, is with their respective sources.

# Known issues
Connections to the Websocket API will fail if you have a HTTP -> HTTPS redirect enabled, either in TrueNAS itself or in some other system (e.g., Traefik) in front of TrueNAS.  This results from an [issue](https://github.com/truenas/api_client/issues/13) in the upstream API client.  If your NAS has a trusted and valid certificate, or you've set `verify_ssl = false` in `deploy_config`, you may be able to avoid this issue by setting `protocol = wss` in `deploy_config`.

# Status
* TrueNAS CE 25.04 - Works locally (running on the TrueNAS host) and remotely (so long as all dependencies are installed), but see notes below.
* TrueNAS SCALE 24.10 - Works locally and remotely.
* TrueNAS SCALE 24.04 - Works remotely only--the TrueNAS API client isn't installed in this version of TrueNAS.  Will not update certificates for apps on this or earlier versions of TrueNAS SCALE.
* TrueNAS SCALE 23.10 - Same as 24.04.

## Notes for 25.04
Security measures in TrueNAS Community Edition 25.04 require that the API keys be passed over a secure channel.  In order to use this script with 25.04, you must set `protocol = wss` in `deploy_config`.  And then, either:
* You must have already deployed a trusted cert to your NAS
* That cert must not be expired
* You must have configured the UI to use that cert
* The address you're using to connect to the NAS (`connect_host` in `deploy_config`) must be named in that cert

Or set `verify_ssl = false` in `deploy_config`.  This will disable validation of the TLS certificate, and should not be used on a routine basis.

# Installation
This script can run on any machine running Python 3 that has network access to your TrueNAS server, but in most cases it's best to run it directly on the TrueNAS box.  Change to a convenient directory and run `git clone https://github.com/danb35/deploy-freenas`.  If you're installing this on your TrueNAS server, it cannot be in your home directory; place it in a convenient place on a storage pool instead.

## Running the script somewhere else
As noted above, this script doesn't need to run on your NAS; it can run on any system running Python 3 that can reach your NAS over the network, but it does have a couple of dependencies.  Assuming a bare-bones Debian 12 system, start with `apt install curl wget nano git cron python3 python3-setuptools python3-openssl`.

You'll next need to install the [TrueNAS API client](https://github.com/truenas/api_client).  To do this, change to a convenient directory and run `git clone https://github.com/truenas/api_client`.  Change into the `api_client` directory and run `python3 setup.py install`.

Then clone this repository as described above.  Your system should be prepared to run the script.

# Usage

The relevant configuration takes place in the `deploy_config` file.  You can create this file either by copying `deploy_config_truenas.example` from this repository, or directly using your preferred text editor.  Its format is as follows:

```
[deploy]
api_key = YourReallySecureAPIKey
privkey_path = /some/other/path
fullchain_path = /some/other/other/path
connect_host = baz.bar.foo
verify_ssl = false
ui_certificate_enabled = true
ftp_enabled = false
apps_enabled = false
cert_base_name = letsencrypt
protocol = ws
```

Everything but `api_key` and paths to the cert and key are optional, and the defaults are documented in `deploy_config.example`.

An API key is required for authentication.  [Generate a new API token in the UI](https://www.truenas.com/docs/scale/24.10/scaleuireference/toptoolbar/settings/apikeysscreen/) first, then add it as `api_key` to the config:
```
api_key = 1-DXcZ19sZoZFdGATIidJ8vMP6dxk3nHWz3XX876oxS7FospAGMQjkOft0h4itJDSP
```

You can optionally configure more than one TrueNAS host in `deploy_config`.  To do so, add a second (or subsequent) header with a label for that host.  The file would look something like this:

```
[nas01]
api_key = YourReallySecureAPIKey
privkey_path = /some/other/path
fullchain_path = /some/other/other/path
connect_host = nas01.baz.bar.foo

[nas02]
api_key = YourReallySecureAPIKey
privkey_path = /some/other/path
fullchain_path = /some/other/other/path
connect_host = nas02.baz.bar.foo
```

Then run the script, specifying the label name, e.g., `deploy_truenas.py nas02`.  If the label name is not specified, it defaults to `deploy` as had been required with previous versions of this script.

Once you've prepared `deploy_config`, you can run `deploy_truenas.py`.  The intended use is that it would be called by your ACME client after issuing a certificate.  With acme.sh, for example, you'd add `--reloadcmd "/path/to/deploy_truenas.py"` to your command.

There is an optional paramter, `-c` or `--config`, that lets you specify the path to your configuration file. By default the script will try to use `deploy_config` in the script working directoy:

```
/path/to/deploy_truenas.py --config /somewhere/else/deploy_config
```
