# deploy-freenas

deploy-freenas.py is a Python script to deploy TLS certificates to a FreeNAS server using the FreeNAS API.  This should ensure that the certificate data is properly stored in the configuration database, and that all appropriate services use this certificate.  It's intended to be called from a Let's Encrypt client like [acme.sh](https://github.com/Neilpang/acme.sh) after the certificate is issued, so that the entire process of issuance (or renewal) and deployment can be automated.

# Usage

There are no command-line arguments to deploy-freenas.py; the relevant configuration needs to be made in the script itself.  The required changes are mostly self-explanatory, but are as follows:
* PRIVATEKEY_PATH is the path to your TLS private key
* FULLCHAIN_PATH is the path to concatenation of your certificate and the issuer's certificate.  With most ACME clients, this file is saved as fullchain.pem or fullchain.cer.
* USER should always be "root"
* PASSWORD needs to be the root password for your FreeNAS server
* DOMAIN_NAME is the FQDN of your FreeNAS server
* PROTOCOL is the protocol used to connect to the API.  If your FreeNAS server is configured to use HTTPS with a trusted certificate, it can be set to "https://".  Otherwise, set it to "http://".


