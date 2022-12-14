"""Cisco Meraki Cloud Simulator for External Captive Portal labs."""
from merakicloudsimulator import merakicloudsimulator
from merakicloudsimulator.alert_settings import alert_settings, http_servers
from merakicloudsimulator.sample_alert_messages import alert_messages
from merakicloudsimulator.meraki_settings import ORGANIZATIONS, NETWORKS
from flask import request, render_template, redirect, jsonify, abort
import string
import requests
import random
import json
from datetime import datetime
from time import sleep
import threading

stop_post_thread = False

def post_webhook_alerts():
    while True:
        print("in big while")
        global stop_post_thread
        if stop_post_thread:
            print("breaking while")
            break
        for alert in alert_settings["alerts"]:
            if stop_post_thread:
                print("breaking for loop")
                break
            if alert["enabled"] == True:
                alert_message = alert_messages[alert["type"]]
                for http_server in http_servers:
                    alert_message["sharedSecret"] = http_server["sharedSecret"]
                    alert_message["organizationId"] = ORGANIZATIONS[0]["id"]
                    alert_message["organizationName"] = ORGANIZATIONS[0]["name"]
                    alert_message["networkId"] = NETWORKS[ORGANIZATIONS[0]["id"]][0]["id"]
                    alert_message["networkName"] = NETWORKS[ORGANIZATIONS[0]["id"]][0]["name"]
                    alert_message["alertId"] = ''.join([random.choice(string.digits) for n in range(16)])
                    alert_message["sentAt"] = datetime.now().isoformat(sep='T')
                    alert_message["occurredAt"] = datetime.now().isoformat(sep='T')
                    requests.post(http_servers[0]["url"], json=alert_message)
                    sleep(10)


post_thread = threading.Thread(target = post_webhook_alerts, daemon=True) 

# Helper Functions
def generate_fake_http_server_id():
    """Generate a fake http_server_id."""
    return ''.join([random.choice(string.ascii_letters + string.digits) for n in range(36)])


# Flask micro-webservice API/URI endpoints
@merakicloudsimulator.route("/api/v1/networks/<network_id>/webhooks/httpServers", methods=["GET"])
def get_http_servers(network_id):
    """Simulate getting httpServers configurations."""
    print(f"Getting httpServers for {network_id}.")
    return jsonify(http_servers)

@merakicloudsimulator.route("/api/v1/networks/<network_id>/webhooks/httpServers", methods=["POST"])
def post_httpServers(network_id):
    """Simulate setting httpServers configurations."""
    print(f"Settings updated for network {network_id}.")
    new_server = request.json
    new_server_keys = new_server.keys()
    if "name" in new_server_keys and "url" in new_server_keys and "sharedSecret" in new_server_keys:
        new_server["id"] = generate_fake_http_server_id()
        new_server["networkId"] = network_id
        http_servers.append(new_server)
        return jsonify(new_server)
    else:
        abort(400)


@merakicloudsimulator.route("/api/v1/networks/<network_id>/alerts/settings",
    methods=["GET"],
)
def get_alert_settings(network_id):
    """Simulate getting alertSettings configurations."""
    print(f"Getting alertSettings for {network_id}.")
    return jsonify(alert_settings)

@merakicloudsimulator.route("/api/v1/networks/<network_id>/alerts/settings",
    methods=["PUT"],
)
def put_alert_settings(network_id):
    global post_thread
    global stop_post_thread

    destination_set = False
    alert_set = False
    """Simulate setting alertSettings configurations."""
    print(f"Setting alertSettings for {network_id}.")
    new_settings = request.json
    new_settings_keys = new_settings.keys()
    if "defaultDestinations" in new_settings_keys or "alerts" in new_settings_keys:
        if "defaultDestinations" in new_settings_keys:
            defaultDestinations_keys = new_settings["defaultDestinations"].keys()
            if "httpServerIds" in defaultDestinations_keys:
                alert_settings["defaultDestinations"]["httpServerIds"].clear()
                if len(new_settings["defaultDestinations"]["httpServerIds"]) > 0:
                    alert_settings["defaultDestinations"]["httpServerIds"].append(new_settings["defaultDestinations"]["httpServerIds"][0])
                    destination_set = True
            else:
                abort(400)
        if "alerts" in new_settings_keys:
            for new_alert in new_settings["alerts"]:
                alert_keys = new_alert.keys()
                if "enabled" in alert_keys and "type" in alert_keys:
                    alert_index = next((index for (index, alert) in enumerate(alert_settings["alerts"]) if alert["type"] == new_alert["type"]), None)
                    alert_settings["alerts"][alert_index] = new_alert
                    alert_set = True
                else:
                    abort(400)
    else:
        abort(400)

    if destination_set and alert_set:
        print("destination set and alert set")
        if not post_thread.is_alive():
            print("posting thread not started, starting")
            post_thread.start() 
        else:
            print("posting thread already started, killing an restarting")
            stop_post_thread = True
            post_thread.join() 
            print('post_thread killed')
            stop_post_thread = False
            post_thread = threading.Thread(target = post_webhook_alerts, daemon=True) 
            post_thread.start()

    return jsonify(alert_settings)


@merakicloudsimulator.route("/webhook", methods=["POST","GET"])
def webhooksettings():
    global post_thread
    global stop_post_thread

    if request.method == 'POST':
        webhook_server_name = request.form["server_name"]
        webhook_server_url  = request.form["server_url"]
        webhook_shared_secret = request.form["shared_secret"]
        webhook_default_destination = request.form.getlist("default_destination")
        
        if webhook_shared_secret != "" and webhook_server_name != "" and webhook_server_url != "":
            http_servers.clear()
            http_servers.append({
                "name": webhook_server_name,
                "url": webhook_server_url,
                "sharedSecret": webhook_shared_secret,
                "id": generate_fake_http_server_id(),
                "networkId": NETWORKS[ORGANIZATIONS[0]["id"]][0]["id"]
            })
            print(f"Alert webhook receiver added: \n{http_servers}")

        if len(webhook_default_destination) > 0 and len(http_servers) > 0:
            alert_settings["defaultDestinations"]["httpServerIds"].clear()
            alert_settings["defaultDestinations"]["httpServerIds"].\
            append(http_servers[0]["id"])
            print(f"Alert Destination Changed in GUI")

        webhook_checked_settings = request.form.getlist("checked_settings")
        for alert in alert_settings['alerts']:
            if alert["type"] in webhook_checked_settings:
                alert["enabled"] = True
            else:
                alert["enabled"] = False

        print(f"Alert Settings Changed in GUI: {alert_settings['alerts']}")
        if len(webhook_default_destination) > 0 and len(http_servers) > 0 and len(webhook_checked_settings) > 0:
            if not post_thread.is_alive():
                print("posting thread not started, starting")
                post_thread.start() 
            else:
                print("posting thread already started, killing an restarting")
                stop_post_thread = True
                post_thread.join()
                print('post_thread killed')
                stop_post_thread = False
                post_thread = threading.Thread(target = post_webhook_alerts, daemon=True) 
                post_thread.start()
    else:
        if len(http_servers) > 0:
            webhook_server_name = http_servers[0]["name"]
            webhook_server_url = http_servers[0]["url"]
            webhook_shared_secret = http_servers[0]["sharedSecret"]
        else:
            webhook_server_name = ""
            webhook_server_url = ""
            webhook_shared_secret = ""

        print(alert_settings["alerts"])
        webhook_checked_settings = []
        for alert in alert_settings["alerts"]:
            if alert["enabled"]:
                webhook_checked_settings.append(alert["type"])
        
        webhook_default_destination = []
        if len(alert_settings["defaultDestinations"]["httpServerIds"]) > 0:
            webhook_default_destination.append("default_destination")
        

    return render_template("webhook.html", \
    checked_settings=webhook_checked_settings, server_name=webhook_server_name, \
    server_url=webhook_server_url, shared_secret=webhook_shared_secret, \
    default_destination=webhook_default_destination)
    

