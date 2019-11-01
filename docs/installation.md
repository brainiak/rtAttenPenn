## Installing RtAtten Software ##
- git clone https://github.com/brainiak/rtAttenPenn.git
- bash scripts/install-rtAtten.sh

### How to install self-signed ssl certificate to use with the web interface
This is used by the web interface for https connections<br>

#### On Mac:
1. Open 'Keychain Access'
  chrome->settings->advanced->manage certificates
2. Select 'login' keychain
3. Select 'Certificates' category
4. Drag certificate file to the list of certificates (or use File->Import Items...)
5. Double click the imported certificate (or right click 'Get Info') and add trust for ssl
  In the 'trust' section, under 'Secure Socket Layers' select 'Always Trust'

### To export self-signed ssl certificate from web page that say not authorized.
Chrome:
1. click three dots in chrome and click 'more tools'->'developer tools'->'Security' tab
2. Click view certificate
3. Drag the picture (image) of a certificate to your desktop

Firefox:
1. Open Firefox to webpage - should see 'Your connection is not secure'
2. Click 'Advanced' button, click 'Add Exception' button
3. In pop-up window click 'view...', select the 'Details' tab, and 'Export' button




### Troubleshooting
- Client-Server SSL Certificate error
    - This happens if the self-signed certificate used to establish encryption between client and server has either expired or doesn't exist. The two files needed are the self-signed certificate 'rtfMRI.crt', and the private-key 'rtfMRI_rsa.private'. These can be regenerated using the script 'certs/create-certs.sh'. The files are linked to a numbered version, so it maybe necessary to unlink previous versions.
