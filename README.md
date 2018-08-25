# deploy-freenas

deploy-freenas.py is a Python script to deploy TLS certificates to a FreeNAS server using the FreeNAS API.  This should ensure that the certificate data is properly stored in the configuration database, and that all appropriate services use this certificate.  It's intended to be called from a Let's Encrypt client like [acme.sh](https://github.com/Neilpang/acme.sh) after the certificate is issued, so that the entire process of issuance (or renewal) and deployment can be automated.

# Usage

```
usage: deploy_freenas.py [-h] [-u USERNAME] [-p PORT]
                         cert key password {http,https} domain

positional arguments:
  cert                  Path to your certificate.
  key                   Path to your private key.
  password              Login password.
  {http,https}          Protocol for request.
  domain                IP or domain to connect to the web interface.

optional arguments:
  -h, --help            show this help message and exit
  -u USERNAME, --username USERNAME
                        Login username, default root.
  -p PORT, --port PORT  Port to access the webinterface, default none.
```

Usage should be self explanatory, here are some examples.

* Update the certificate from the local FreeNAS box.

`./deploy_freenas.py cert.pem key.pem 'foo' http localhost`

* Update the certificate using https and a fqdn.

`./deploy_freenas.py cert.pem key.pem 'foo' https nas.example.com`

* Update the certificate with a custom port.

`./deploy_freenas.py cert.pem key.pem 'foo' http localhost -p 8080`


