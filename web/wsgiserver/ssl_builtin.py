"""A library for integrating pyOpenSSL with CherryPy.

The ssl module must be importable for SSL functionality.

To use this module, set CherryPyWSGIServer.ssl_adapter to an instance of
BuiltinSSLAdapter.

    ssl_adapter.certificate: the filename of the server SSL certificate.
    ssl_adapter.private_key: the filename of the server's private key file.
"""

try:
    import ssl
except ImportError:
    ssl = None


from web import wsgiserver

def decode_cert( prefix, cert ):

    if not cert:
        return None

    key_map = { 'countryName':'C',
                'stateOrProvinceName':'ST',
                'localityName':'L',
                'organizationName':'O',
                'organizationalUnitName':'OU',
                'commonName':'CN',
                # Don't know by what key names python's ssl
                # implementation uses for these fields.
                #'???':'T',
                #'???':'I',
                #'???':'G',
                #'???':'S',
                #'???':'D',
                #'???':'UID',
                'emailAddress':'Email',
                }

    DN_string = ["subject=",]
    cert_dict = {}

    for rdn in cert:
        for key, item in rdn:
            if key in key_map:
                cert_dict["%s_%s" % ( prefix, key_map[key] ) ] = item
                DN_string.append( "%s=%s" % ( key_map[key], item ))

    cert_dict[prefix] = "/".join( DN_string )
        
    return cert_dict


class BuiltinSSLAdapter(wsgiserver.SSLAdapter):
    """A wrapper for integrating Python's builtin ssl module with CherryPy."""
    
    def __init__(self, certificate, private_key, certificate_chain=None, client_CA=None):
        if ssl is None:
            raise ImportError("You must install the ssl module to use HTTPS.")
        self.certificate = certificate
        self.private_key = private_key
        self.certificate_chain = certificate_chain
        self.client_CA = client_CA
    
    def bind(self, sock):
        """Wrap and return the given socket."""
        return sock
    
    def wrap(self, sock):
        """Wrap and return the given socket, plus WSGI environ entries."""
        try:
            if self.client_CA:
                s = ssl.wrap_socket(sock, do_handshake_on_connect=True,
                                    server_side=True, certfile=self.certificate,
                                    keyfile=self.private_key, ssl_version=ssl.PROTOCOL_SSLv23,
                                    ca_certs=self.client_CA,
                                    cert_reqs=ssl.CERT_REQUIRED)
            else:
                s = ssl.wrap_socket(sock, do_handshake_on_connect=True,
                                    server_side=True, certfile=self.certificate,
                                    keyfile=self.private_key, ssl_version=ssl.PROTOCOL_SSLv23)
        except ssl.SSLError, e:
            if e.errno == ssl.SSL_ERROR_EOF:
                # This is almost certainly due to the cherrypy engine
                # 'pinging' the socket to assert it's connectable;
                # the 'ping' isn't SSL.
                return None, {}
            elif e.errno == ssl.SSL_ERROR_SSL:
                if e.args[1].endswith('http request'):
                    # The client is speaking HTTP to an HTTPS server.
                    raise wsgiserver.NoSSLError
            raise
        return s, self.get_environ(s)
    
    # TODO: fill this out more with mod ssl env
    def get_environ(self, sock):
        """Create WSGI environ entries to be merged into each request."""
        cipher = sock.cipher()
        ssl_environ = {
            "wsgi.url_scheme": "https",
            "HTTPS": "on",
            'SSL_PROTOCOL': cipher[1],
            'SSL_CIPHER': cipher[0]
##            SSL_VERSION_INTERFACE 	string 	The mod_ssl program version
##            SSL_VERSION_LIBRARY 	string 	The OpenSSL program version
            }

        
        client_cert = sock.getpeercert()

        client_cert_subject = decode_cert( "SSL_CLIENT_S_DN", client_cert["subject"] )


        # Update for client environment variables
        ssl_environ.update( {
            #"SSL_CLIENT_M_VERSION":              "",
            #"SSL_CLIENT_M_SERIAL":               "",
            #"SSL_CLIENT_V_START":	         "",
            "SSL_CLIENT_V_END":	                 client_cert["notAfter"],
            #"SSL_CLIENT_A_SIG":	                 "",
            #"SSL_CLIENT_A_KEY":	                 "",
            #"SSL_CLIENT_CERT":	                 "",
            #"SSL_CLIENT_CERT_CHAIN":	         "",
            #"SSL_CLIENT_VERIFY":	         "",
            } )

        ssl_environ.update( client_cert_subject )

        # Update for server environment variables
        ssl_environ.update( {
            #"SSL_SERVER_M_VERSION":              "",
            #"SSL_SERVER_M_SERIAL":               "",
            #"SSL_SERVER_V_START":	         "",
            #"SSL_SERVER_V_END":	                 "",
            #"SSL_SERVER_A_SIG":	                 "",
            #"SSL_SERVER_A_KEY":	                 "",
            #"SSL_SERVER_CERT":	                 "",
            } )

        
        return ssl_environ
    
    def makefile(self, sock, mode='r', bufsize=-1):
        return wsgiserver.CP_fileobject(sock, mode, bufsize)

