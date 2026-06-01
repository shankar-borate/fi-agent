ABC Bank FI Agent — nginx Setup
================================

ALL SERVICES ON THE SAME MACHINE
  nginx     : port 80 (public)
  FastAPI   : port 8000 (loopback, not exposed externally)

STEP 1 — Add WebSocket map to /etc/nginx/nginx.conf
  Open /etc/nginx/nginx.conf and add this INSIDE the http { } block
  (if not already present):

      map $http_upgrade $connection_upgrade {
          default  upgrade;
          ''       close;
      }

STEP 2 — Install the site config
  sudo cp fi-agent.conf /etc/nginx/sites-available/fi-agent
  sudo ln -s /etc/nginx/sites-available/fi-agent /etc/nginx/sites-enabled/fi-agent
  sudo rm -f /etc/nginx/sites-enabled/default     # remove nginx default page

STEP 3 — Test and reload
  sudo nginx -t
  sudo systemctl reload nginx

STEP 4 — Start FastAPI (if not already running)
  cd /opt/fi-agent/server
  ./start.sh

URLS after setup
----------------
  Customer App    http://<your-server-ip>/fi/
  Auditor Portal  http://<your-server-ip>/auditor/    login: test / test
  Dashboard       http://<your-server-ip>/
  API Docs        http://<your-server-ip>/docs
  Health Check    http://<your-server-ip>/health

TROUBLESHOOTING
---------------
  nginx config errors : sudo nginx -t
  nginx logs          : sudo tail -f /var/log/nginx/fi-agent-error.log
  FastAPI logs        : sudo journalctl -u fi-agent -f
  WebSocket issues    : Check the map block is inside http {} in nginx.conf
  413 errors          : client_max_body_size is set to 600m — should be fine
  504 Gateway Timeout : Increase proxy_read_timeout in fi-agent.conf
