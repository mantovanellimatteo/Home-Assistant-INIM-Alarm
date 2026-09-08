import yaml
import json
import urllib.request
import urllib.parse
import ssl
import base64
import subprocess
import socket
import asyncio
import logging
import sys
import os
from datetime import datetime
import websockets
import paho.mqtt.client as mqtt

# Setup Logging
logger = logging.getLogger("inim_bridge")
logger.setLevel(logging.INFO)
formatter = logging.Formatter('[%(levelname)s][%(asctime)s] %(message)s')

# Ensure log directory exists
os.makedirs('/srv/inim-hub/log', exist_ok=True)
file_handler = logging.FileHandler('/srv/inim-hub/log/python_bridge.log')
file_handler.setFormatter(formatter)
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.addHandler(stream_handler)

# AES decryption key from inimclient binary
qwords = [
    0x2333634E3F4C6658,
    0x3F2F4D3747316473,
    0x6E42432E337C3D26,
    0x5A4659385431452C
]
key = b"".join(q.to_bytes(8, byteorder='little') for q in qwords)
key_hex = key.hex()

def decrypt(ciphertext_base64):
    try:
        data = base64.b64decode(ciphertext_base64)
        iv = data[:16]
        encrypted = data[16:]
        proc = subprocess.Popen(
            ['openssl', 'enc', '-d', '-aes-256-cbc', '-K', key_hex, '-iv', iv.hex()],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        out, err = proc.communicate(input=encrypted)
        if proc.returncode != 0:
            raise Exception(err.decode('utf-8'))
        return out.decode('utf-8')
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        raise

class InimMQTTBridge:
    def __init__(self, config_path='/srv/inim-hub/config.yaml'):
        self.config_path = config_path
        self.config = {}
        self.token = ""
        self.username = ""
        self.password = ""
        self.client_id = ""
        self.client_name = socket.gethostname()
        self.mqtt_client = None
        self.device_id = None
        self.scenarios_map = {} # ScenarioId -> Name
        self.active_scenario = None
        self.active_scenarios_str = ""
        self.loop = None

    def load_config(self):
        with open(self.config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        # Set log level
        level_str = self.config.get('log', {}).get('level', 'INFO').upper()
        level = getattr(logging, level_str, logging.INFO)
        logger.setLevel(level)
        
        self.username = decrypt(self.config['inim']['username'])
        self.password = decrypt(self.config['inim']['password'])
        self.client_id = self.config['inim']['client-id']
        logger.info("Config loaded and credentials decrypted successfully.")

    def login(self):
        url = "https://api.inimcloud.com"
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        payload = {
            "Node": "",
            "Name": "",
            "ClientIP": "",
            "Method": "RegisterClient",
            "Token": "",
            "ClientId": self.client_id,
            "Params": {
                "Username": self.username,
                "Password": self.password,
                "ClientId": self.client_id,
                "ClientName": self.client_name,
                "ClientInfo": "Inim Home",
                "ClientApp": "Inim Home",
                "ClientVersion": "2.4.5",
                "ClientPlatform": "Inim Home"
            }
        }
        
        json_str = json.dumps(payload, separators=(',', ':'))
        data = urllib.parse.urlencode({"req": json_str}).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
        
        logger.debug("Sending RegisterClient request to Inim Cloud...")
        with urllib.request.urlopen(req, context=ctx) as response:
            body = response.read().decode('utf-8')
            res = json.loads(body)
            if res.get("Status") == 0:
                self.token = res["Data"]["Token"]
                logger.info("Successfully registered client and obtained new token.")
            else:
                raise Exception(f"RegisterClient failed: {res}")

    def fetch_devices(self):
        url = "https://api.inimcloud.com"
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        payload = {
            "Node": "",
            "Name": "",
            "ClientIP": "",
            "Method": "GetDevicesExtended",
            "Token": self.token,
            "ClientId": self.client_id,
            "Params": {
                "ClientId": self.client_id
            }
        }
        
        json_str = json.dumps(payload, separators=(',', ':'))
        data = urllib.parse.urlencode({"req": json_str}).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
        
        logger.debug("Fetching devices from Inim Cloud...")
        with urllib.request.urlopen(req, context=ctx) as response:
            body = response.read().decode('utf-8')
            res = json.loads(body)
            if res.get("Status") == 0:
                data_dict = res.get("Data", {})
                # Find the first device ID key (it's a string representing the integer ID)
                device_keys = [k for k in data_dict.keys() if k.isdigit()]
                if not device_keys:
                    raise Exception("No alarm devices found in GetDevicesExtended response")
                
                self.device_id = int(device_keys[0])
                dev_data = data_dict[device_keys[0]]
                self.active_scenario = dev_data.get("ActiveScenario")
                self.active_scenarios_str = dev_data.get("ActiveScenarios", "")
                
                # Load scenarios
                self.scenarios_map = {}
                for s in dev_data.get("Scenarios", []):
                    self.scenarios_map[s["ScenarioId"]] = s["Name"]
                
                logger.info(f"Devices fetched. Device ID: {self.device_id}, Active Scenario: {self.active_scenario} ({self.active_scenarios_str})")
            else:
                raise Exception(f"GetDevicesExtended failed: {res}")

    def activate_scenario(self, scenario_id):
        url = "https://api.inimcloud.com"
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        payload = {
            "Node": "",
            "Name": "",
            "ClientIP": "",
            "Method": "ActivateScenario",
            "Token": self.token,
            "ClientId": self.client_id,
            "Params": {
                "DeviceId": self.device_id,
                "ScenarioId": scenario_id,
                "ClientId": self.client_id
            }
        }
        
        json_str = json.dumps(payload, separators=(',', ':'))
        data = urllib.parse.urlencode({"req": json_str}).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
        
        logger.info(f"Requesting activation of Scenario {scenario_id} ({self.scenarios_map.get(scenario_id, 'Unknown')})...")
        with urllib.request.urlopen(req, context=ctx) as response:
            body = response.read().decode('utf-8')
            res = json.loads(body)
            if res.get("Status") == 0:
                logger.info("Scenario activation request accepted by Inim Cloud.")
            else:
                logger.error(f"ActivateScenario failed: {res}")

    def connect_mqtt(self):
        mqtt_conf = self.config.get('mqtt', {})
        self.mqtt_client = mqtt.Client()
        if mqtt_conf.get('user') and mqtt_conf.get('password'):
            self.mqtt_client.username_pw_set(mqtt_conf['user'], mqtt_conf['password'])
        
        def on_connect(client, userdata, flags, rc):
            logger.info(f"Connected to MQTT broker with result code {rc}")
            # Subscribe to command topics for all configured scenarios
            scenarios = self.config.get('inim', {}).get('scenarios', [])
            for s_id in scenarios:
                topic = f"homeassistant/binary_sensor/inim_scenario_{s_id}/command"
                client.subscribe(topic)
                logger.info(f"Subscribed to MQTT topic: {topic}")

        def on_message(client, userdata, msg):
            logger.info(f"Received MQTT message on {msg.topic}: {msg.payload.decode('utf-8')}")
            # Extract scenario ID from topic
            # Topic format: homeassistant/binary_sensor/inim_scenario_{id}/command
            try:
                parts = msg.topic.split('/')
                s_id_str = parts[2].replace('inim_scenario_', '')
                scenario_id = int(s_id_str)
                # Call activate_scenario inside the running asyncio event loop
                if self.loop:
                    self.loop.call_soon_threadsafe(self.activate_scenario, scenario_id)
            except Exception as e:
                logger.error(f"Error parsing MQTT command: {e}")

        self.mqtt_client.on_connect = on_connect
        self.mqtt_client.on_message = on_message
        self.mqtt_client.connect(mqtt_conf.get('host', '127.0.0.1'), mqtt_conf.get('port', 1883), 60)
        self.mqtt_client.loop_start()

    def publish_states(self):
        if not self.mqtt_client or not self.device_id:
            return

        now_str = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+02:00")
        configured_scenarios = self.config.get('inim', {}).get('scenarios', [])
        
        # 1. Publish Scenarios configuration, state and attributes
        for s_id in configured_scenarios:
            s_name = self.scenarios_map.get(s_id, f"Scenario {s_id}")
            
            # Discovery Config (with the original 'commnad_topic' spelling to match Go client)
            config_topic = f"homeassistant/binary_sensor/inim_scenario_{s_id}/config"
            config_payload = {
                "name": f"Inim scenario {s_name}",
                "unique_id": f"alarm_inim_scenario_{s_id}",
                "state_topic": f"homeassistant/binary_sensor/inim_scenario_{s_id}/state",
                "icon": "mdi:shield-home",
                "device_class": "lock",
                "state_class": "",
                "availability_topic": f"homeassistant/binary_sensor/inim_scenario_{s_id}/availability",
                "commnad_topic": f"homeassistant/binary_sensor/inim_scenario_{s_id}/command",
                "payload_available": "online",
                "payload_not_available": "offline",
                "payload_on": "on",
                "payload_off": "off",
                "json_attributes_topic": f"homeassistant/binary_sensor/inim_scenario_{s_id}/attributes"
            }
            
            self.mqtt_client.publish(config_topic, json.dumps(config_payload), retain=True)
            self.mqtt_client.publish(f"homeassistant/binary_sensor/inim_scenario_{s_id}/availability", "online", retain=True)
            
            is_active = (self.active_scenario == s_id)
            state_val = "on" if is_active else "off"
            self.mqtt_client.publish(f"homeassistant/binary_sensor/inim_scenario_{s_id}/state", state_val, retain=True)
            logger.info(f"State published: inim_scenario_{s_id}/state -> {state_val}")
            
            attr_payload = {
                "is_active": is_active,
                "last_update": now_str,
                "scenario_id": s_id,
                "unique_id": s_id
            }
            self.mqtt_client.publish(f"homeassistant/binary_sensor/inim_scenario_{s_id}/attributes", json.dumps(attr_payload), retain=True)

        # 2. Publish Alarm State configuration, state and attributes
        alarm_config_topic = f"homeassistant/binary_sensor/inim_alarm_state_{self.device_id}/config"
        alarm_config_payload = {
            "name": "Stato allarme Inim",
            "unique_id": f"alarm_inim_state_{self.device_id}",
            "state_topic": f"homeassistant/binary_sensor/inim_alarm_state_{self.device_id}/state",
            "icon": "mdi:shield-home",
            "device_class": "safety",
            "state_class": "",
            "availability_topic": f"homeassistant/binary_sensor/inim_alarm_state_{self.device_id}/availability",
            "payload_available": "online",
            "payload_not_available": "offline",
            "payload_on": "on",
            "payload_off": "off",
            "json_attributes_topic": f"homeassistant/binary_sensor/inim_alarm_{self.device_id}/attributes"
        }
        self.mqtt_client.publish(alarm_config_topic, json.dumps(alarm_config_payload), retain=True)
        self.mqtt_client.publish(f"homeassistant/binary_sensor/inim_alarm_state_{self.device_id}/availability", "online", retain=True)
        
        # Publish overall alarm state (off)
        self.mqtt_client.publish(f"homeassistant/binary_sensor/inim_alarm_state_{self.device_id}/state", "off", retain=True)
        
        # Map device info attributes (matching Go client format)
        active_scenarios_name = self.scenarios_map.get(self.active_scenario, self.active_scenarios_str)
        alarm_attr_payload = {
            "active_scenarios": active_scenarios_name,
            "last_error": "",
            "last_keep_alive": now_str
        }
        self.mqtt_client.publish(f"homeassistant/binary_sensor/inim_alarm_{self.device_id}/attributes", json.dumps(alarm_attr_payload), retain=True)
        logger.info(f"Alarm attributes published: active_scenarios -> {active_scenarios_name}")

    async def run_wss_listener(self):
        while True:
            try:
                payload = {
                    "Node": "",
                    "Name": "",
                    "ClientIP": "",
                    "Method": "WebSocketStart",
                    "Token": self.token,
                    "ClientId": self.client_id,
                    "Params": {
                        "Username": self.username,
                        "Password": self.password,
                        "ClientId": self.client_id,
                        "ClientName": self.client_name,
                        "ClientInfo": "Inim Home",
                        "ClientApp": "Inim Home",
                        "ClientVersion": "2.4.5",
                        "ClientPlatform": "Inim Home"
                    }
                }
                
                json_str = json.dumps(payload, separators=(',', ':'))
                escaped_json = urllib.parse.quote(json_str)
                url = f"wss://ws.inimcloud.com/events?req={escaped_json}"
                
                logger.info("Connecting to Inim Cloud WebSocket...")
                async with websockets.connect(url) as websocket:
                    logger.info("WebSocket connection established successfully.")
                    while True:
                        # Receive message (pings/pongs are handled transparently by websockets library)
                        message = await websocket.recv()
                        logger.info(f"WebSocket message received: {message}")
                        
                        # Check if the message is an error notification (e.g. invalid request)
                        try:
                            msg_json = json.loads(message)
                            if isinstance(msg_json, dict) and "error" in msg_json.get("Code", "").lower():
                                logger.warning(f"Skipping state refresh due to WebSocket error response: {message}")
                                continue
                        except Exception as parse_ex:
                            logger.debug(f"Could not parse WebSocket message as JSON: {parse_ex}")
                        
                        # Trigger local refresh from API on any event
                        try:
                            self.fetch_devices()
                            self.publish_states()
                        except Exception as ex:
                            logger.error(f"Error refreshing states after event: {ex}")
                            
            except websockets.exceptions.ConnectionClosed as cc:
                logger.warning(f"WebSocket connection closed: {cc}. Reconnecting in 10s...")
                await asyncio.sleep(10)
            except Exception as e:
                logger.error(f"WebSocket error: {e}. Re-authenticating and reconnecting in 15s...")
                await asyncio.sleep(15)
                # Refresh token
                try:
                    self.login()
                except Exception as login_ex:
                    logger.error(f"Failed to refresh token: {login_ex}")

    async def start(self):
        self.loop = asyncio.get_running_loop()
        self.load_config()
        self.login()
        self.fetch_devices()
        self.connect_mqtt()
        self.publish_states()
        
        # Start WSS listener task
        await self.run_wss_listener()

if __name__ == '__main__':
    bridge = InimMQTTBridge()
    try:
        asyncio.run(bridge.start())
    except KeyboardInterrupt:
        logger.info("Shutting down bridge...")
