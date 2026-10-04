# Hosting on one AWS EC2 instance

The whole application runs on a single instance: Nginx serves the built frontend and passes `/api` to
the unchanged FastAPI backend. Frontend and API share one origin, so no CORS setting is needed.

```text
Internet → Nginx :443 ─┬─ /        → /var/www/document-investigator (frontend/dist)
                       └─ /api/... → 127.0.0.1:8000 (Uvicorn, user "investigator")
                                     → SQLite + files in /var/lib/document-investigator
```

## Instance

EC2 → Launch instance:

- Image: Ubuntu Server 24.04 LTS, 64-bit (x86)
- Type: at least 2 GB of memory. Tested on `c7i-flex.large` (2 vCPU, 4 GB); OCR peaks at about 800 MB,
  so 1 GB types such as `t3.micro` run out of memory.
- Key pair: create one and keep the `.pem` file
- Network: allow SSH, HTTP and HTTPS
- Storage: 20 GB gp3

Stopping and starting the instance changes its public IP address (a reboot does not).

## Backend

```bash
ssh -i <key.pem> ubuntu@<public-ip>
git clone https://github.com/thorathharish/Intelligent-Document-Investigator.git
bash Intelligent-Document-Investigator/deploy/aws/setup.sh

sudo nano /etc/document-investigator.env      # set OPENROUTER_API_KEY
sudo systemctl restart document-investigator
curl http://127.0.0.1/api/health
```

`setup.sh` installs Python 3.11 and the pinned requirements, creates the `investigator` user, the
systemd service and the Nginx site. It takes about a minute.

To serve recorded answers for the rehearsed demo questions, copy `data/llm_recordings/*.json` from the
development machine into `/var/lib/document-investigator/llm_recordings/` (owner `investigator`).

## Frontend

Build on the development machine, with `VITE_API_BASE_URL` unset so the app calls `/api` on its own
origin, then copy the result to the instance:

```powershell
npm --prefix frontend run build
scp -i <key.pem> -r frontend\dist ubuntu@<public-ip>:/tmp/dist
ssh -i <key.pem> ubuntu@<public-ip> "sudo rm -rf /var/www/document-investigator && sudo cp -r /tmp/dist /var/www/document-investigator && sudo chmod -R a+rX /var/www/document-investigator"
```

Repeat these three commands after any frontend change.

## HTTPS

A certificate needs a host name. Without a domain, `sslip.io` gives one for any address: the IP
`1.2.3.4` is reachable as `1-2-3-4.sslip.io`.

```bash
HOST=<ip-with-dashes>.sslip.io
sudo apt-get install -y certbot python3-certbot-nginx
sudo sed -i "s/server_name _;/server_name $HOST;/" /etc/nginx/sites-available/document-investigator
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d $HOST --agree-tos --register-unsafely-without-email --redirect
curl https://$HOST/api/health
```

Certbot renews the certificate automatically.

## Operating it

```bash
sudo systemctl status document-investigator        # state
sudo journalctl -u document-investigator -f        # logs
sudo systemctl restart document-investigator       # restart; the database and files are kept
bash /opt/document-investigator/deploy/aws/setup.sh   # update to the latest code
free -h                                            # memory
```

## Backup and restore

```bash
# back up the database, uploaded documents and recordings
sudo systemctl stop document-investigator
sudo tar czf ~/investigator-backup-$(date +%F).tgz -C /var/lib document-investigator
sudo systemctl start document-investigator

# restore
sudo systemctl stop document-investigator
sudo tar xzf ~/investigator-backup-<date>.tgz -C /var/lib
sudo systemctl start document-investigator
```

Copy the archive off the instance with `scp`. Keep a private copy of `/etc/document-investigator.env`
separately; it holds the API key and is never committed.
