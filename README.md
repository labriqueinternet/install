
```
apt install python3-venv avahi-utils python3-setuptools python3-wheel -y
python3 -m venv venv
source venv/bin/activate
pip install wheel
pip install -r requirements.txt

cp deploy/avahi-alias.service /etc/systemd/system/avahi-alias@.service
systemctl enable --now avahi-alias@internetcube.local.service
systemctl enable --now avahi-alias@briqueinternet.local.service

cp deploy/nginx.conf /etc/nginx/conf.d/default.d/internetcube_install.conf
echo '{"redirected_urls": { "/": "/install" }}' > /etc/ssowat/conf.json.persistent
systemctl reload nginx

cp deploy/internetcube.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now internetcube

touch /etc/yunohost/internetcube_to_be_installed
```
