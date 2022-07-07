import time
import os
import json
import subprocess
from requests.utils import requote_uri

steps = []
current_step = None


def step(func):
    steps.append(func)
    return func


@step
def upgrade(install_params):

    apt = (
        "DEBIAN_FRONTEND=noninteractive APT_LISTCHANGES_FRONTEND=none LC_ALL=C "
        "apt-get -o=Acquire::Retries=3 -o=Dpkg::Use-Pty=0 --quiet --assume-yes "
    )

    run_cmd(apt + "update")
    run_cmd(
        apt
        + "dist-upgrade -o Dpkg::Options::='--force-confold' --fix-broken --show-upgraded"
    )
    run_cmd(apt + "autoremove")


@step
def postinstall(install_params):
    command = "yunohost tools postinstall --force-diskspace -d '{main_domain}' -p '{password}'".format(**install_params)
    if install_params["use_dyndns_domain"] and len(install_params["domain_password"])>0:
        command+=f" --subscribe {install_params['domain_password']}"

    run_cmd(command)


@step
def firstuser(install_params):

    if " " in install_params["fullname"].strip():
        install_params["firstname"], install_params["lastname"] = (
            install_params["fullname"].strip().split(" ", 1)
        )
    else:
        install_params["firstname"] = install_params["fullname"]
        install_params["lastname"] = "FIXMEFIXME"  # FIXME

    run_cmd(
        "yunohost user create '{username}' -q 0 "
        "-f '{firstname}' "
        "-l '{lastname}' "
        "-d '{main_domain}' "
        "-p '{password}'".format(**install_params)
    )


@step
def install_vpnclient(install_params):
    if not install_params["enable_vpn"]:
        return "skipped"

    run_cmd("yunohost app install vpnclient --force")


@step
def configure_vpnclient(install_params):
    if not install_params["enable_vpn"]:
        return "skipped"

    run_cmd("yunohost app setting vpnclient service_enabled -v 1")

    open("/tmp/config.cube", "w").write(install_params["cubefile"])
    os.system("chown root:root /tmp/config.cube")
    os.system("chmod 600 /tmp/config.cube")

    run_cmd("yunohost app config set vpnclient --args 'config_file=/tmp/config.cube'")


@step
def install_hotspot(install_params):
    if not install_params["enable_wifi"]:
        return "skipped"

    wifi_ssid_esc = requote_uri(install_params["wifi_ssid"])
    wifi_password_esc = requote_uri(install_params["wifi_password"])

    run_cmd(
        "yunohost app install hotspot --force --args '"
        f"&wifi_ssid={wifi_ssid_esc}"
        f"&wifi_passphrase={wifi_password_esc}"
        "&firmware_nonfree=no'"
    )


@step
def cleanup(install_params):

    # Update diagnosis results
    run_cmd("yunohost diagnosis run")
    run_cmd("yunohost diagnosis show --issues")
    run_cmd("rm /etc/yunohost/internetcube_to_be_installed")

    cmds = [
        "sleep 15",
        "echo '{}' > /etc/ssowat/conf.json.persistent",
        "rm /etc/nginx/conf.d/default.d/internetcube_install.conf",
        "systemctl reload nginx",
        "rm /etc/systemd/system/internetcube.service",
        "systemctl daemon-reload",
        "systemctl disable --now internetcube",
    ]

    open("/tmp/internetcube-cleanup", "w").write(
        "rm /tmp/internetcube-cleanup;\n" + "\n".join(cmds)
    )
    os.system("systemd-run --scope bash /tmp/internetcube-cleanup &")

    time.sleep(5)


# ===============================================================
# ===============================================================
# ===============================================================


def run_cmd(cmd):

    append_step_log("Running: " + cmd)
    subprocess.check_call(
        cmd + " &>> ./data/%s.logs" % current_step.__name__,
        shell=True,
        executable="/bin/bash",
    )


def append_step_log(message):
    open("./data/%s.logs" % current_step.__name__, "a").write(message + "\n")


def set_step_status(status):
    open("./data/%s.status" % current_step.__name__, "w").write(status)


def get_step_status():
    f = "./data/%s.status" % current_step.__name__
    return open(f, "r").read().strip() if os.path.exists(f) else None


if __name__ == "__main__":

    cwd = os.path.dirname(os.path.realpath(__file__))
    os.chdir(cwd)
    install_params = json.loads(open("./data/install_params.json").read())

    for step in steps:

        current_step = step

        # When re-running the whole thing multiple time,
        # skip test that were already succesfull / skipped...
        if get_step_status() in ["success", "skipped"]:
            continue

        set_step_status("ongoing")
        try:
            append_step_log("============================")
            ret = step(install_params)
            assert ret in [None, "success", "skipped"]
        except subprocess.CalledProcessError as e:
            set_step_status("failed")
            append_step_log(str(e))
            break
        except Exception as e:
            set_step_status("failed")
            import traceback

            append_step_log(traceback.format_exc())
            append_step_log(str(e))
            break

        set_step_status(ret if ret else "success")
