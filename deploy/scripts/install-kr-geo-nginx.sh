#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
sudo install -d -m 755 /etc/nginx/snippets
sudo cp "$ROOT/deploy/nginx/10-kr-country-geo.conf" /etc/nginx/conf.d/10-kr-country-geo.conf
sudo chmod 644 /etc/nginx/conf.d/10-kr-country-geo.conf
sudo cp "$ROOT/deploy/nginx/career-counsel" /etc/nginx/sites-available/career-counsel
sudo chmod 644 /etc/nginx/sites-available/career-counsel
sudo cp "$ROOT/deploy/scripts/update-nginx-kr-geo.sh" /usr/local/sbin/update-nginx-kr-geo.sh
sudo chmod 755 /usr/local/sbin/update-nginx-kr-geo.sh
sudo /usr/local/sbin/update-nginx-kr-geo.sh
