
[ ! -e /etc/yunohost/apps/hotspot ] || yunohost app remove hotspot
[ ! -e /etc/yunohost/apps/vpnclient ] || yunohost app remove vpnclient

# Remove nginx conf
rm -rf $(ls /etc/nginx/conf.d/* -d | grep -v "yunohost\|global\|ssowat")
# Remove all yunohost stuff
rm -rf /etc/yunohost/
# Remove all certs / ssl stuff
rm -f /etc/ssl/certs/ca-yunohost_crt.pem
rm -f /etc/ssl/certs/*yunohost*.pem
rm -f /etc/ssl/*/yunohost_*.pem
rm -rf /usr/share/yunohost/yunohost-config/ssl/yunoCA/
rm -f /etc/cron.d/yunohost-dyndns

dpkg --purge --force-depends slapd

# This stuff may not be needed with yunohost >= 4.2
debconf-set-selections << EOF
slapd slapd/password1 password yunohost
slapd slapd/password2 password yunohost
slapd slapd/domain string yunohost.org
slapd shared/organization string yunohost.org
slapd slapd/allow_ldap_v2 boolean false
slapd slapd/invalid_config boolean true
slapd slapd/backend select MDB
EOF

apt-get install slapd --reinstall

# Reconfigure yunohost to run the postinst script that will re-init everything
dpkg-reconfigure yunohost

cp /var/www/install_internetcube/deploy/nginx.conf /etc/nginx/conf.d/default.d/internetcube_install.conf
echo '{"redirected_urls": { "/": "/install" }}' > /etc/ssowat/conf.json.persistent
systemctl reload nginx

rm -rf /var/www/install_internetcube/data/
touch /etc/yunohost/internetcube_to_be_installed
