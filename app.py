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
    steps_with_i18n = [
        ("upgrade", _("Upgrade the system")),
        ("postinstall", _("Postinstall Yunohost")),
        ("firstuser", _("Create first user")),
        ("install_vpnclient", _("Install VPN client")),
        ("configure_vpnclient", _("Configure the VPN")),
        ("install_hotspot", _("Install the WiFi Hotspot")),
        ("configure_hotspot", _("Configure the WiFi Hotspot")),
        ("customscript", _("Run the custom script")),
        ("reboot", _("Reboot the system")),
        ("cleanup", _("Clean things up")),
    ]

    translated_steps = [step for step, _ in steps_with_i18n]
    assert set(translated_steps) == set(steps)

    if request.method == "GET":
        if not os.path.exists("./data/install_params.json"):
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


@app.route('/retry', methods = ['POST'])
def retry():
    return start_install()


def start_install(form_data=None):

    os.system("mkdir -p ./data/")
    if form_data:
        with open("./data/install_params.json", "w") as f:
            f.write(json.dumps(form_data))

    os.system("systemctl reset-failed internetcube_install.service &>/dev/null || true ")
    cwd = os.path.dirname(os.path.realpath(__file__))
    start_status = os.system("systemd-run --unit=internetcube_install %s/venv/bin/python3 %s/internetcube_install.py" % (cwd, cwd))

    sleep(3)

    status = subprocess.check_output("systemctl is-active internetcube_install.service || true", shell=True).strip().decode("utf-8")
    if status == "active":
        return "", 200
    elif start_status != 0:
        return "Failed to start the install script ... maybe the app ain't started as root ?", 500
    else:
        status = subprocess.check_output("journalctl --no-pager --no-hostname -n 20 -u internetcube_install.service || true", shell=True).strip().decode("utf-8")
        return "The install script was started but is still not active ... \n<pre style='text-align:left;'>" + status + "</pre>", 500


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

        cmd = "tac %s | tail -n 50 | grep -m 1 ' INFO \| SUCCESS ' | cut -d ' ' -f 5-" % log_path
        message = subprocess.check_output(cmd, shell=True).strip().decode("utf-8")

        if not message:
            message = subprocess.check_output("tail -n 1 %s" % log_path, shell=True).strip().decode("utf-8")

        return redact_passwords(message)

    update_info_to_redact()

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

    update_info_to_redact()
    data = []
    for step in steps:
        logs_path = "./data/%s.logs" % step
        data.append({
            "id": step,
            "logs": redact_passwords(open(logs_path).read().strip()) if os.path.exists(logs_path) else [],
        })
    return jsonify(data)


to_redact = []
def update_info_to_redact():

    if not os.path.exists("./data/install_params.json"):
        return content

    data = json.loads(open("./data/install_params.json").read())

    global to_redact
    to_redact = []
    for key, value in data.items():
        if value and "pass" in key:
            to_redact.append(value)


def redact_passwords(content):

    for value in to_redact:
        content = content.replace(value, "[REDACTED]")

    return content
