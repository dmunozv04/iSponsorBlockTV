from iSponsorBlockTV import helpers
import sys
import os

if getattr(sys, 'frozen', False):
    os.environ['SSL_CERT_FILE'] = os.path.join(sys._MEIPASS, 'lib', 'cert.pem')
helpers.app_start()