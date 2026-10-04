# Backend on an Oracle Cloud Always Free VM

Runs the existing FastAPI backend unchanged: systemd → Uvicorn (one worker) → FastAPI, behind Nginx on
port 80, with SQLite and files on the VM's boot volume.

```text
Internet → Nginx :80 → 127.0.0.1:8000 (Uvicorn, user "investigator") → SQLite + files in /var/lib/document-investigator
```

## Always Free resources used

- One compute instance: `VM.Standard.A1.Flex` (ARM64), up to 4 OCPU and 24 GB RAM in total are free.
  2 OCPU / 12 GB is plenty. The x86 alternative, `VM.Standard.E2.1.Micro`, has 1 GB RAM and 1/8 OCPU.
- Its boot volume (the default 47–50 GB is inside the 200 GB free allowance).
- One virtual cloud network with a public subnet and an ephemeral public IPv4 address.

Nothing else is needed. Do not add a load balancer, NAT gateway, extra block volume or reserved IP.

## Console steps

1. **Create the instance.** Compute → Instances → Create instance.
   - Image: Canonical Ubuntu 22.04. Shape: Ampere → `VM.Standard.A1.Flex`, 2 OCPU, 12 GB.
   - Networking: create a new VCN and public subnet; assign a public IPv4 address.
   - SSH keys: generate a key pair and download the private key.
   - Check that the summary shows "Always Free-eligible" before clicking Create.
2. **Open the web ports.** Networking → the VCN → the subnet → its security list → Add ingress rules:
   source `0.0.0.0/0`, TCP, destination port `80` (and `443` if HTTPS is added later).

## On the VM

```bash
ssh -i <private-key> ubuntu@<public-ip>
git clone https://github.com/thorathharish/Intelligent-Document-Investigator.git
bash Intelligent-Document-Investigator/deploy/oracle/setup.sh

sudo nano /etc/document-investigator.env      # set OPENROUTER_API_KEY and ALLOWED_ORIGINS
sudo systemctl restart document-investigator
curl http://127.0.0.1/api/health
```

`setup.sh` installs Python 3.11 and the pinned requirements, creates the `investigator` user, the
service and the Nginx site, and opens ports 80 and 443 in the VM's own firewall. Oracle's Ubuntu images
ship with iptables rules that reject everything except SSH, so the script adds iptables rules rather
than using UFW, which conflicts with those rules.

## Operating it

```bash
sudo systemctl status document-investigator        # state
sudo journalctl -u document-investigator -f        # logs
sudo systemctl restart document-investigator       # restart; the database and files are kept
bash /opt/document-investigator/deploy/oracle/setup.sh   # update to the latest code
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

Copy the archive off the VM with `scp`. Keep a private copy of `/etc/document-investigator.env`
separately; it holds the API key and is never committed.

## HTTPS

The script serves plain HTTP. A frontend served over HTTPS cannot call an HTTP API (browsers block it
as mixed content), so before connecting a hosted frontend, add a certificate. This needs a host name,
not a bare IP address. A free name from a dynamic-DNS service plus Let's Encrypt (`certbot --nginx`)
costs nothing.
