from flask import Flask, render_template, request, jsonify
from flask_babel import Babel
from flask_babel import gettext as _

import json
import requests
import subprocess
import os

from time import sleep
from internetcube_install import steps

steps = [step.__name__ for step in steps]

app = Flask(__name__, static_folder='assets')
babel = Babel(app)

@babel.localeselector
def get_locale():
    return "fr"


@app.route('/', methods = ['POST', 'GET'])
def main():

    # We need this here because gettext (_) gotta be called when user makes the
    # request to know their language ... (or at least not sure how to do this
    # another way ... we can have a loop but that will probably hide what
    # strings are needed and therefore we won't be able to easily collect them
    # for translation generation)
    # But the consequence is : this gotta be kept in sync with the step list
    steps_with_i18n = {
        "upgrade": _("Upgrade the system"),
        "postinstall": _("Postinstall Yunohost"),
        "firstuser": _("Create first user"),
        "vpnclient": _("Install and configure the VPN"),
        "hotspot": _("Install and configure the WiFi Hotspot"),
        "customscript": _("Run the custom script"),
        "reboot": _("Reboot the system"),
    }

    assert set(steps_with_i18n.keys()) == set(steps)


    if request.method == "GET":
        status = subprocess.check_output("systemctl is-active internetcube_install.service || true", shell=True).strip().decode("utf-8")
        if status == "inactive" or not os.path.exists("./data/install_params.json"):
            return render_template('form.html')
        else:
            return render_template('status.html', steps=steps_with_i18n, status=status)


    if request.method == 'POST':
        form_data = {k:v for k, v in request.form.items()}
        try:
            validate(form_data)
        except Exception as e:
            return str(e), 400

        return start_install(form_data)

def start_install(form_data):

    with open("./data/install_params.json", "w") as f:
        f.write(json.dumps(form_data))

    os.system("systemctl reset-failed internetcube_install.service &>/dev/null || true ")
    start_status = os.system("systemd-run --same-dir --unit=internetcube_install python3 ./internetcube_install.py")

    sleep(3)

    status = subprocess.check_output("systemctl is-active internetcube_install.service || true", shell=True).strip().decode("utf-8")
    if status == "active":
        return "", 200
    elif start_status != 0:
        return "Failed to start the install script ... maybe the app ain't started as root ?", 500
    else:
        status = subprocess.check_output("systemctl status internetcube_install.service || true", shell=True).strip().decode("utf-8")
        return "The install script was started but is still not active ... \n" + status , 500


def validate(form):

    # Connected to the internet ?
    try:
        requests.get("https://wikipedia.org", timeout=15)
    except Exception as e:
        raise Exception(_("It looks like the board is not connected to the internet !?"))

    # Dyndns domain is available ?
    dyndns_domains = ["nohost.me", "noho.st", "ynh.fr"]
    if any(form["main_domain"].endswith(dyndns_domain) for dyndns_domain in dyndns_domains):
        try:
            r = requests.get('https://dyndns.yunohost.org/test/' + form["main_domain"], timeout=15)
            assert r.text.endswith("is available")
        except Exception as e:
            raise Exception(_("It looks like domain %(domain)s is not available.", domain=form["main_domain"]))

    # .cube format ?
    if form["enable_vpn"]:
        try:
            cube_config = json.loads(form["cubefile"])
        except Exception as e:
            raise Exception(_("Could not load this file as json ... Is it a valid .cube file ?"))

        # TODO : refine this ?
        expected_fields = ["server_name", "server_port", "crt_server_ca", "dns0"]
        if not all(field in cube_config for field in expected_fields):
            raise Exception(_("This cube file does not look valid because some fields are missing ?"))

    return True

@app.route('/status', methods = ['GET'])
def status():

    def most_recent_info(log_path):

        cmd = "tac %s | grep -m 1 ' INFO \| SUCCESS ' | cut -d ' ' -f 5-" % log_path
        return subprocess.check_output(cmd, shell=True).strip().decode("utf-8")

    data = []
    for step in steps:
        status_path = "./data/%s.status" % step
        logs_path = "./data/%s.logs" % step
        data.append({
            "id": step,
            "status": open(status_path).read().strip() if os.path.exists(status_path) else "pending",
            "message": most_recent_info(logs_path) if os.path.exists(logs_path) else None,
        })

    return jsonify(data)


@app.route('/debug', methods = ['GET'])
def debug():

    data = []
    for step in steps:
        logs_path = "./data/%s.logs" % step
        data.append({
            "id": step,
            "logs": open(logs_path).read().strip() if os.path.exists(logs_path) else [],
        })
    return jsonify(data)


