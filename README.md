# Deploy TLS Certificates to FreeNAS/TrueNAS
This repository contains scripts to automate deployment of a TLS certificate to your FreeNAS (11.1 or newer) or TrueNAS server.  Due to a complete overhaul of the API in more recent versions of TrueNAS, this repo contains two different scripts, each with its own README.

* If you're using FreeNAS, or TrueNAS CORE, use `deploy_freenas.py`. [README](README_freenas.md).  This will also work with TrueNAS SCALE through 24.10, but as SCALE introduced a websocket API, the other script is recommended.
* If you're using TrueNAS SCALE or Community Edition (as of 25.04), use `deploy_truenas.py`. [README](README_truenas.md)
* I've had no reports of compatibility, pro or con, with any version of TrueNAS Enterprise.  I expect the `_freenas` version will work with FreeBSD-based TrueNAS Enterprise installations, while the `_truenas` version will work with Linux-based installations, but I'm afraid you're largely on your own.

## Support
If you have questions about these scripts, or issues with them, let me know in [this topic](https://forums.truenas.com/t/lets-encrypt-with-freenas-11-1-and-later/425/) on the TrueNAS forums.
