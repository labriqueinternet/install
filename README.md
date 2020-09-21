apt install python3-venv -y
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp deploy/nginx.conf /etc/nginx/conf.d/default.d/internetcube.conf
cp deploy/regenconf.hook /usr/share/yunohost/hooks/conf_regen/99-nginx_internetcube
echo "" > /etc/nginx/conf.d/default.d/redirect_to_admin.conf
systemctl reload nginx

cp deploy/internetcube.service /etc/systemd/system
systemctl daemon-reload
systemctl enable internetcube
systemctl start internetcube
