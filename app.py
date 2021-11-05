from flask import Flask, render_template, request, jsonify
from flask_babel import Babel
from flask_babel import gettext as _

import json
import requests
import subprocess
import os

from time import sleep
from install_procedure import steps

DYNDNS_DOMAINS = ["nohost.me", "noho.st", "ynh.fr"]
AVAILABLE_LANGUAGES = ["en"] + os.listdir("translations")

# Copypasta from https://stackoverflow.com/a/36033627
class PrefixMiddleware(object):

    def __init__(self, app, prefix=''):
        self.app = app
        self.prefix = prefix

    def __call__(self, environ, start_response):

        if environ['PATH_INFO'].startswith(self.prefix):
            environ['PATH_INFO'] = environ['PATH_INFO'][len(self.prefix):]
            environ['SCRIPT_NAME'] = self.prefix
            return self.app(environ, start_response)
        else:
            start_response('404', [('Content-Type', 'text/plain')])
            return ["This url does not belong to the app.".encode()]


steps = [step.__name__ for step in steps]

app = Flask(__name__, static_folder='assets')
app.wsgi_app = PrefixMiddleware(app.wsgi_app, prefix='/install')

babel = Babel(app)

@babel.localeselector
def get_locale():
    # try to guess the language from the user accept
    # header the browser transmits.  We support de/fr/en in this
    # example.  The best match wins.
    return request.accept_languages.best_match(AVAILABLE_LANGUAGES)


@app.route('/', methods = ['POST', 'GET'])
def main():

    if not os.path.exists("/etc/yunohost/internetcube_to_be_installed"):
        return "The InternetCube is already installed"

    # We need this here because gettext (_) gotta be called when user makes the
    # request to know their language ... (or at least not sure how to do this
    # another way ... we can have a loop but that will probably hide what
    # strings are needed and therefore we won't be able to easily collect them
    # for translation generation)
    # But the consequence is : this gotta be kept in sync with the step list
    steps_with_i18n = [
        ("upgrade", _("System upgrade")),
        ("postinstall", _("Server initialization")),
        ("firstuser", _("First user creation")),
        ("install_vpnclient", _("VPN installation")),
        ("configure_vpnclient", _("VPN configuration")),
        ("install_hotspot", _("WiFi Hotspot installation")),
        ("cleanup", _("Cleaning")),
    ]

    translated_steps = [step for step, _ in steps_with_i18n]
    assert set(translated_steps) == set(steps)

    if request.method == "GET":
        if not os.path.exists("./data/install_params.json"):
            return render_template('form.html')
        else:
            install_params = json.loads(open("./data/install_params.json").read())
            return render_template('status.html', steps=steps_with_i18n, install_params=install_params)

    if request.method == 'POST':
        form_data = {k:v for k, v in request.form.items()}
        try:
            validate(form_data)
        except Exception as e:
            return str(e), 400

        return start_install(form_data)


@app.route('/retry', methods=['POST'])
def retry():
    return start_install(json.loads(open("./data/install_params.json").read()))


@app.route('/fullreset', methods=['POST'])
def fullreset():
    cwd = os.path.dirname(os.path.realpath(__file__))
    return os.system("bash %s/deploy/fullreset.sh" % cwd) == 0


def start_install(form_data={}):

    form_data["enable_vpn"] = form_data.get("enable_vpn") in ["true", True]
    form_data["enable_wifi"] = form_data.get("enable_wifi") in ["true", True]
    form_data["use_dyndns_domain"] = any(form_data.get("main_domain").endswith("."+dyndns_domain) for dyndns_domain in DYNDNS_DOMAINS)
    form_data["request_host"] = request.host

    os.system("mkdir -p ./data/")
    os.system("chown root:root ./data/")
    os.system("chmod o-rwx ./data/")
    if form_data:
        with open("./data/install_params.json", "w") as f:
            f.write(json.dumps(form_data))

    os.system("systemctl reset-failed internetcube_install.service &>/dev/null || true ")
    cwd = os.path.dirname(os.path.realpath(__file__))
    start_status = os.system("systemd-run --unit=internetcube_install %s/venv/bin/python3 %s/install_procedure.py" % (cwd, cwd))

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
    if any(form["main_domain"].endswith("."+dyndns_domain) for dyndns_domain in DYNDNS_DOMAINS):
        try:
            r = requests.get('https://dyndns.yunohost.org/test/' + form["main_domain"], timeout=15)
            assert "is available" in r.text.strip()
        except Exception as e:
            raise Exception(_("It looks like domain %(domain)s is not available.", domain=form["main_domain"]))

    # .cube format ?
    if form.get("enable_vpn") in ["true", True]:
        try:
            cube_config = json.loads(form["cubefile"])
        except Exception as e:
            raise Exception(_("Could not load this file as json ... Is it a valid .cube file ?" + str(form["enable_vpn"])))

        # TODO : refine this ?
        expected_fields = ["server_name", "server_port", "crt_server_ca", "dns0"]
        if not all(field in cube_config for field in expected_fields):
            raise Exception(_("This cube file does not look valid because some fields are missing ?"))

        if cube_config.get("crt_client"):
            read, write = os.pipe();
            os.write(write, cube_config['crt_client'].replace('|', '\n').encode());
            os.close(write);
            try:
                subprocess.check_call('openssl x509 -noout -checkend 0 >/dev/null', shell=True, stdin=read)
            except Exception as e:
                raise Exception(_("It looks like the user certificate in the .cube file is already expired ?!"))

    if form.get("enable_wifi") in ["true", True]:
        # This doesnt work properly because of missing drivers
        # so the interface doesn't show up
        # Though we could maybe tweak something with lsusb (but that doesn't cover non-usb devices)
        pass
        #try:
        #    subprocess.check_call("/sbin/iw dev | grep -q Interface", shell=True)
        #except Exception as e:
        #    raise Exception(_("The hotspot option can't enabled because it looks like no WiFi interface is available on the system ... did you forget to plug the antenna ?"))

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

    status = subprocess.check_output("systemctl is-active internetcube_install.service || true", shell=True).strip().decode("utf-8")

    return jsonify({ "active": status == "active",
                     "steps": data })


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
        return

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
