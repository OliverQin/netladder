# netladder

A tool to help you accessing Internet scientifically. :)

This tool is written in Python 2, it simply wraps all TCP commnunications in WebSocket. Therefore it can run on any PaaS which supports WebSocket. For different environments to deploy on, you may need slightly revise the code.

## Usage
Deploy the `app.py` on server side. Run `local.py` locally. It works as a SOCKS5 proxy.

## Dependencies
- [trollius](http://trollius.readthedocs.io/asyncio.html) >= 1.0.4
- [autobahn](http://autobahn.ws/python/) >= 0.9.4

## Known issues
- SOCKS5 server only supports IPv4.
- TCP Only, UDP not supported.
- It supports HTTPS (it's required in severe environments), but certificates are not checked. Thus it may suffer from MITM attack.

Use It At Your Own Risk!
