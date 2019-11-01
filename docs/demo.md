## NIH DEMO

### Notes:
- If the certificate expires you need to make a new one, previously it expired after 1 year, changed to 10 years. There are two certificates, the one for communicating between client and server and the one for the web-browser
- Subject data is located here: /Data1/subjects/20180122.0122182_rtAttenPenn.0122182_rtAttenPenn
- For registration use highres scan #5 (176 files) and functional scan # 7 (8 files)
- Note - you can logout at the https://<ipaddr_cloud_computer>/logout

### Starting Demo Components
- On the cloud computer:<br>
<i>No need to run classification server (i.e. scripts/run-server.sh) because the web-server runs the classification server with the client, i.e. using run-local or -l mode</i>
    - Start the web-server running<br>
        bash scripts/run-web.sh -e DEMO_SUBJECT6_INTELRT.toml -ip <ipaddr_cloud_computer>
- On the Intelrt computer
    - Start the fileWatcher running<br>
    python FileWatchServer.py -d /Data1 -f .dcm,.txt,.mat -s <ipaddr_cloud_computer>:8888 -u <user> -p <passwd>
- From a web browser
    - Open the main control page
        https://<cloud_ip_addr>:8888
    - Open the subject view page
        https://<cloud_ip_addr>:8888/feedback
