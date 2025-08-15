import socket
import threading
import serial
import paho.mqtt.client as paho_mqtt
import json

import sys
import time
import logging
from logging.handlers import TimedRotatingFileHandler
from collections import defaultdict
import os.path
import re

RS485_DEVICE = {
    "light": {
        "state": { "id": 0x0E, "cmd": 0x81 },
        "last": {},
        "power": { "id": 0x0E, "cmd": 0x41, "ack": 0xC1 },
    },
    "plug": {
        "state": { "id": 0x39, "cmd": 0x81 },
        "last": {},
        "power": { "id": 0x39, "cmd": 0x41, "ack": 0xC1 },
    },
    "thermostat": {
        "state": { "id": 0x36, "cmd": 0x81 },
        "last": {},
        "mode": { "id": 0x36, "cmd": 0x43, "ack": 0xC3 },
        "target": { "id": 0x36, "cmd": 0x44, "ack": 0xC4 },
        "away": { "id": 0x36, "cmd": 0x46, "ack": 0xC6 },
    },
    "fan": {
        "state": { "id": 0x32, "cmd": 0x81 },
        "last": {},
        "power": { "id": 0x32, "cmd": 0x41, "ack": 0xC1 },
        "speed": { "id": 0x32, "cmd": 0x42, "ack": 0xC2 },
        "mode": { "id": 0x32, "cmd": 0x43, "ack": 0xC3 },
    },
    "gas": {
        "state": { "id": 0x12, "cmd": 0x81 },
        "last": {},
        "close": { "id": 0x12, "cmd": 0x41, "ack": 0xC1 },
    },
    "energy": {
        "state": { "id": 0x30, "cmd": 0x81 },
        "last": {},
    },
    "elevator": {
        "state": { "id": 0x33, "cmd": 0x81 },
        "last": {},
        "power": { "id": 0x33, "cmd": 0x41, "ack": 0xC1 },
        "call": { "id": 0x33, "cmd": 0x43, "ack": 0xC3 }, # 호출(요청) 01 10 , 도착(종료) 01 80
    },
    "doorbell": {
        "state": { "id": 0x40, "cmd": 0x82 },
        "last": {},
        "ring": { "id": 0x40, "cmd": 0x93, "ack": 0xC3 },
        "talk": { "id": 0x40, "cmd": 0x12, "ack": 0xC2 },
        "open": { "id": 0x40, "cmd": 0x22, "ack": 0xC2 },
        "cancel": { "id": 0x40, "cmd": 0x11, "ack": 0xC1 },
    },
}

DISCOVERY_DEVICE = {
    "ids": [
        "ezville_wallpad",
    ],
    "name": "ezville_wallpad",
    "mf": "EzVille",
    "mdl": "EzVille Wallpad",
    "sw": "ezville_wallpad",
}

DISCOVERY_PAYLOAD = {
    "light": [
        {
            "_intg": "light",
            "~": "{prefix}/light/{idn}",
            "name": "Light {room} {num}",
            "stat_t": "~/power/state",
            "cmd_t": "~/power/command",
        }
    ],
    "plug": [
        {
            "_intg": "switch",
            "~": "{prefix}/plug/{idn}",
            "name": "Plug {room} {num}",
            "icon": "mdi:power-socket-de",
            "stat_t": "~/power/state",
            "cmd_t": "~/power/command",
            "dev_cla": "outlet",
        },
        {
            "_intg": "sensor",
            "~": "{prefix}/plug/{idn}",
            "name": "Plug {room} {num} Power",
            "stat_t": "~/current/state",
            "unit_of_meas": "W",
            "dev_cla": "power",
        }
    ],
    "thermostat": [
        {
            "_intg": "climate",
            "~": "{prefix}/thermostat/{idn}",
            "name": "Thermostat {room}",
            "mode_stat_t": "~/mode/state",
            "mode_cmd_t": "~/mode/command",
            "temp_stat_t": "~/target/state",
            "temp_cmd_t": "~/target/command",
            "curr_temp_t": "~/current/state",
            "away_stat_t": "~/away/state",
            "away_cmd_t": "~/away/command",
            "modes": ["off","heat"],
            "min_temp": 5,
            "max_temp": 40,
        }
    ],
    "fan": [
        {
            "_intg": "fan",
            "~": "{prefix}/fan/{idn}",
            "name": "Ventilation Fan Mode",
            "state_topic": "~/power/state",
            "command_topic": "~/power/command",
            "preset_mode_state_topic": "~/mode/state",
            "preset_mode_command_topic": "~/mode/command",
            "percentage_state_topic": "~/speed/state",
            "percentage_command_topic": "~/speed/command",
            "payload_low_speed": "low",
            "payload_medium_speed": "medium",
            "payload_high_speed": "high",
            "preset_modes": ["bypass","heat"],
            "speed_range_min": 1,
            "speed_range_max": 3,
        }
    ],
    "gas": [
        {
            "_intg": "valve",
            "~": "{prefix}/gas/{idn}",
            "name": "Gas Valve Close",
            "state_topic": "~/valve/state",
            "command_topic": "~/valve/command",
            "device_class": "gas",
        }
    ],
    "energy": [
        {
            "_intg": "sensor",
            "~": "{prefix}/energy/{idn}",
            "name": "Energy Meter {type}",
            "stat_t": "~/power/state",
            "unit_of_meas": "W",
            "dev_cla": "power",
        },
        {
            "_intg": "sensor",
            "~": "{prefix}/energy/{idn}",
            "name": "Energy Meter Usage",
            "stat_t": "~/usage/state",
            "unit_of_meas": "kWh",
            "dev_cla": "energy",
        }
    ],
    "elevator": [
        {
            "_intg": "sensor",
            "~": "{prefix}/elevator/{idn}",
            "name": "Elevator",
            "icon": "mdi:elevator",
            "stat_t": "~/power/state",
            "cmd_t": "~/power/command",
        }
    ],
    "doorbell": [
        {
            "_intg": "binary_sensor",
            "~": "{prefix}/doorbell/{idn}",
            "name": "Doorbell",
            "icon": "mdi:doorbell",
            "stat_t": "~/state",
            "dev_cla": "door",
        }
    ],
}

STATE_HEADER = {
    prop["state"]["id"]: (device, prop["state"]["cmd"])
    for device, prop in RS485_DEVICE.items()
    if "state" in prop
}

ACK_HEADER = {
    prop[cmd]["id"]: (device, prop[cmd]["ack"])
    for device, prop in RS485_DEVICE.items()
    for cmd, code in prop.items()
    if "ack" in code
}

ACK_MAP = defaultdict(lambda: defaultdict(dict))
for device, prop in RS485_DEVICE.items():
    for cmd, code in prop.items():
        if "ack" in code:
            ACK_MAP[code["id"]][code["cmd"]] = code["ack"]

# Ezville에서는 가스밸브 STATE Query 코드로 처리
HEADER_0_FIRST = [ [0x12, 0x01], [0x12, 0x0F] ]
header_0_first_candidate = [ [[0x33, 0x01], [0x33, 0x0F]], [[0x36, 0x01], [0x36, 0x0F]] ]

serial_queue = {}
serial_ack = {}

last_query = int(0).to_bytes(2, "big")
last_topic_list = {}

mqtt = paho_mqtt.Client()
mqtt_connected = False

logger = logging.getLogger(__name__)

# 기기별 등록된 구성요소 추적
registered_entities = defaultdict(set)
# 초기 기기 생성 여부 추적
initial_devices_created = False


class EzVilleSocket:
    def __init__(self, addr, port, capabilities="ALL"):
        self.capabilities = capabilities
        self._soc = socket.socket()
        self._soc.connect((addr, port))

        self._recv_buf = bytearray()
        self._pending_recv = 0

        self.set_timeout(5.0)
        data = self._recv_raw(1)
        self.set_timeout(None)
        if not data:
            logger.critical("no active packet at this socket!")

    def _recv_raw(self, count=1):
        return self._soc.recv(count)

    def recv(self, count=1):
        # socket은 버퍼와 in_waiting 직접 관리
        while len(self._recv_buf) < count:
            new_data = self._recv_raw(128)
            if not new_data:
                # new_data가 빈 경우, 대기 후 다시 시도
                continue
            self._recv_buf.extend(new_data)

        self._pending_recv = max(self._pending_recv - count, 0)

        res = self._recv_buf[0:count]
        del self._recv_buf[0:count]
        return res

    def send(self, a):
        self._soc.sendall(a)

    def set_pending_recv(self):
        self._pending_recv = len(self._recv_buf)

    def check_pending_recv(self):
        return self._pending_recv

    def check_in_waiting(self):
        if len(self._recv_buf) == 0:
            new_data = self._recv_raw(128)
            self._recv_buf.extend(new_data)
        return len(self._recv_buf)

    def set_timeout(self, a):
        self._soc.settimeout(a)


def init_option(argv):
    # option 파일 선택
    if len(argv) == 1:
        option_file = "options_standalone.json"
    else:
        option_file = argv[1]
    option_file = os.path.join(
        os.path.dirname(os.path.abspath(argv[0])), option_file
    )

    # configuration이 예전 버전이어도 최대한 동작 가능하도록,
    # 기본값에 해당하는 파일을 먼저 읽고나서 설정 파일로 업데이트 한다.
    global Options

    # 기본값 파일은 .py 와 같은 경로에 있음
    default_file = os.path.join(
        os.path.dirname(os.path.abspath(argv[0])), "config.json"
    )

    with open(default_file, encoding="utf-8") as f:
        config = json.load(f)
        logger.info("addon version %s", config["version"])
        Options = config["options"]
    with open(option_file, encoding="utf-8") as f:
        Options2 = json.load(f)

    # 업데이트
    for k, v in Options.items():
        if isinstance(v, dict) and k in Options2:
            Options[k].update(Options2[k])
            for k2 in Options[k].keys():
                if k2 not in Options2[k].keys():
                    logger.warning("no configuration value for '%s:%s'! try default value (%s)...", k, k2, Options[k][k2])
        else:
            if k not in Options2:
                logger.warning("no configuration value for '%s'! try default value (%s)...", k, Options[k])
            else:
                Options[k] = Options2[k]

    # 관용성 확보
    Options["mqtt"]["server"] = re.sub("[a-z]*://", "", Options["mqtt"]["server"])
    if Options["mqtt"]["server"] == "127.0.0.1":
        logger.warning("MQTT server address should be changed!")

    # internal options
    Options["mqtt"]["_discovery"] = Options["mqtt"]["discovery"]

    # MQTT 토픽 설정 초기화
    if "state_topic_suffix" not in Options["mqtt"]:
        Options["mqtt"]["state_topic_suffix"] = "/state"
    if "command_topic_suffix" not in Options["mqtt"]:
        Options["mqtt"]["command_topic_suffix"] = "/command"


def init_logger():
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)-8s %(message)s", datefmt="%H:%M:%S"
    )
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def init_logger_file():
    if Options["log"]["to_file"]:
        # 현재 파이썬 파일의 절대 경로를 기준으로 로그 파일 경로 설정
        current_file_path = os.path.abspath(__file__)
        current_dir = os.path.dirname(current_file_path)
        filename = os.path.join(current_dir, Options["log"]["filename"])

        os.makedirs(os.path.dirname(filename), exist_ok=True)

        formatter = logging.Formatter(
            fmt="%(asctime)s %(levelname)-8s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler = TimedRotatingFileHandler(
            filename, when="midnight", backupCount=7
        )
        handler.setFormatter(formatter)
        handler.suffix = "%Y%m%d"
        logger.addHandler(handler)


def create_initial_devices():
    """초기 기기들을 생성합니다."""
    global initial_devices_created
    if initial_devices_created:
        return
    
    prefix = Options["mqtt"]["prefix"]
    
    # Doorbell
    for payload in DISCOVERY_PAYLOAD["doorbell"]:
        p = payload.copy()
        p["~"] = p["~"].format(prefix=prefix, idn=1)
        p["name"] = p["name"].format(prefix=prefix, idn=1)
        mqtt_discovery(p)
    
    # Elevator
    for payload in DISCOVERY_PAYLOAD["elevator"]:
        p = payload.copy()
        p["~"] = p["~"].format(prefix=prefix, idn=1)
        p["name"] = p["name"].format(prefix=prefix, idn=1)
        mqtt_discovery(p)
    
    # Energy Meter
    for payload in DISCOVERY_PAYLOAD["energy"]:
        p = payload.copy()
        p["~"] = p["~"].format(prefix=prefix, idn=0)
        if "type" in p["name"]:
            p["name"] = p["name"].format(prefix=prefix, type="power")
        else:
            p["name"] = p["name"].format(prefix=prefix, idn=0)
        mqtt_discovery(p)
    
    # Gas Valve
    for payload in DISCOVERY_PAYLOAD["gas"]:
        p = payload.copy()
        p["~"] = p["~"].format(prefix=prefix, idn=1)
        p["name"] = p["name"].format(prefix=prefix, idn=1)
        mqtt_discovery(p)
    
    # Light 1 with 3 components
    for light_num in range(1, 4):
        p = DISCOVERY_PAYLOAD["light"][0].copy()
        p["~"] = p["~"].format(prefix=prefix, idn=f"1_{light_num}")
        p["name"] = p["name"].format(room="1", num=light_num)
        mqtt_discovery(p)
        registered_entities["light"].add(f"1_{light_num}")
    
    # Plug 1 with 2 components
    for plug_num in range(1, 3):
        for payload in DISCOVERY_PAYLOAD["plug"]:
            p = payload.copy()
            p["~"] = p["~"].format(prefix=prefix, idn=f"1_{plug_num}")
            p["name"] = p["name"].format(room="1", num=plug_num)
            mqtt_discovery(p)
        registered_entities["plug"].add(f"1_{plug_num}")
    
    # Thermostat 1
    p = DISCOVERY_PAYLOAD["thermostat"][0].copy()
    p["~"] = p["~"].format(prefix=prefix, idn="1")
    p["name"] = p["name"].format(room="1")
    mqtt_discovery(p)
    registered_entities["thermostat"].add("1")
    
    # Ventilation Fan
    for payload in DISCOVERY_PAYLOAD["fan"]:
        p = payload.copy()
        p["~"] = p["~"].format(prefix=prefix, idn=1)
        p["name"] = p["name"].format(prefix=prefix, idn=1)
        mqtt_discovery(p)
    
    initial_devices_created = True


def mqtt_init_discovery():
    # HA가 재시작됐을 때 모든 discovery를 다시 수행한다
    Options["mqtt"]["_discovery"] = Options["mqtt"]["discovery"]
    for device in RS485_DEVICE:
        RS485_DEVICE[device]["last"] = {}

    global last_topic_list
    last_topic_list = {}
    
    # 초기 기기 생성
    create_initial_devices()


def mqtt_discovery(payload):
    intg = payload.pop("_intg")

    # MQTT 통합구성요소에 등록되기 위한 추가 내용
    payload["device"] = DISCOVERY_DEVICE
    payload["uniq_id"] = f"{DISCOVERY_DEVICE['name']}_{payload['name']}".strip().replace(' ','_').replace('__','_')

    # discovery에 등록
    topic = f"homeassistant/{intg}/ezville_wallpad/{payload['name']}/config"
    logger.info("Add new device: %s\n%s", topic, json.dumps(payload))
    mqtt.publish(topic, json.dumps(payload))


def mqtt_debug(topics, payload):
    device = topics[2]
    command = topics[3]

    if device == "packet":
        if command == "send":
            # parity는 여기서 재생성
            packet = bytearray.fromhex(payload)
            packet[-2], packet[-1] = serial_generate_checksum(packet)
            packet = bytes(packet)

            logger.info("prepare packet: {}".format(packet.hex()))
            serial_queue[packet] = time.time()


def mqtt_device(topics, payload):
    device = topics[1]
    idn = topics[2]
    cmd = topics[3]

    # HA에서 잘못 보내는 경우 체크
    if device not in RS485_DEVICE:
        logger.error("unknown device!")
        return
    if cmd not in RS485_DEVICE[device]:
        logger.error("unknown command!")
        return
    if payload == "":
        logger.error("no payload!")
        return

    # 오류 체크 끝났으면 serial 메시지 생성
    cmd = RS485_DEVICE[device][cmd]
    packet = None

    if device == "light":
        if payload == "ON":
            payload = 0x01
        else:
            payload = 0x00
        length = 10
        packet = bytearray(length)
        packet[0] = 0xF7
        packet[1] = cmd["id"]
        packet[2] = int(idn.split("_")[0]) << 4 | int(idn.split("_")[1])
        packet[3] = cmd["cmd"]
        packet[4] = 0x03
        packet[5] = int(idn.split("_")[2])
        packet[6] = payload
        packet[7] = 0x00
        packet[8], packet[9] = serial_generate_checksum(packet)

    elif device == "plug":
        if payload == "ON":
            payload = 0x11
        else:
            payload = 0x10
        length = 8
        packet = bytearray(length)
        packet[0] = 0xF7
        packet[1] = cmd["id"]
        packet[2] = int(idn.split("_")[0]) << 4 | int(idn.split("_")[1])
        packet[3] = cmd["cmd"]
        packet[4] = 0x01
        packet[5] = payload
        packet[6], packet[7] = serial_generate_checksum(packet)

    elif device == "thermostat":
        if payload == "heat":
            payload = 0x01
        else:
            payload = 0x00
        length = 8
        packet = bytearray(length)
        packet[0] = 0xF7
        packet[1] = cmd["id"]
        packet[2] = int(idn.split("_")[0]) << 4 | int(idn.split("_")[1])
        packet[3] = cmd["cmd"]
        packet[4] = 0x01
        packet[5] = payload
        packet[6], packet[7] = serial_generate_checksum(packet)

    elif device == "fan":
        if payload == "1" or payload == "ON" or payload == "bypass":
            payload = 0x01
        elif payload == "2":
            payload = 0x02
        elif payload == "3" or payload == "heat":
            payload = 0x03
        else:
            payload = 0x00
        length = 8
        packet = bytearray(length)
        packet[0] = 0xF7
        packet[1] = cmd["id"]
        packet[2] = 0x01
        packet[3] = cmd["cmd"]
        packet[4] = 0x01
        packet[5] = payload
        packet[6], packet[7] = serial_generate_checksum(packet)

    elif device == "gas":
        if payload == "CLOSE":
            payload = 0x00
        else:
            payload = 0x00
        length = 8
        packet = bytearray(length)
        packet[0] = 0xF7
        packet[1] = cmd["id"]
        packet[2] = 0x01
        packet[3] = cmd["cmd"]
        packet[4] = 0x01
        packet[5] = payload
        packet[6], packet[7] = serial_generate_checksum(packet)

    elif device == "doorbell":
        if cmd["cmd"] == 0x93:  # 벨 눌림은 0x01, 나머지는 0x00
            payload = 0x01
        else:
            payload = 0x00
        if cmd["cmd"] in [0x93, 0x12, 0x22, 0x11]:
            length = 8
            packet = bytearray(length)
            packet[0] = 0xF7
            packet[1] = cmd["id"]
            packet[2] = 0x01
            packet[3] = cmd["cmd"]
            packet[4] = payload
            packet[5] = 0x00
            packet[6], packet[7] = serial_generate_checksum(packet)

    if packet:
        packet = bytes(packet)
        serial_queue[packet] = time.time()


def mqtt_on_connect(mqtt, userdata, flags, rc):
    if rc == 0:
        logger.info("MQTT connect successful!")
        global mqtt_connected
        mqtt_connected = True
    else:
        logger.error("MQTT connection return with: %s", paho_mqtt.connack_string(rc))

    mqtt_init_discovery()

    topic = "homeassistant/status"
    logger.info("subscribe %s", topic)
    mqtt.subscribe(topic, 0)

    prefix = Options["mqtt"]["prefix"]
    if Options["wallpad_mode"] != "off":
        command_suffix = Options["mqtt"]["command_topic_suffix"]
        topic = f"{prefix}/+/+/+{command_suffix}"
        logger.info("subscribe %s", topic)
        mqtt.subscribe(topic, 0)


def mqtt_on_disconnect(client, userdata, flags, rc):
    logger.warning("MQTT disconnected! (%s)", rc)
    global mqtt_connected
    mqtt_connected = False


def mqtt_on_message(mqtt, userdata, msg):
    topics = msg.topic.split("/")
    payload = msg.payload.decode()
    logger.info("recv. from HA: %s = %s", msg.topic, payload)

    device = topics[1]
    if device == "status":
        if payload == "online":
            mqtt_init_discovery()
    elif device == "debug":
        mqtt_debug(topics, payload)
    else:
        mqtt_device(topics, payload)


def start_mqtt_loop():
    logger.info("initialize mqtt...")

    mqtt.on_connect = mqtt_on_connect
    mqtt.on_message = mqtt_on_message
    mqtt.on_disconnect = mqtt_on_disconnect

    if Options["mqtt"]["need_login"]:
        mqtt.username_pw_set(Options["mqtt"]["user"], Options["mqtt"]["passwd"])

    try:
        mqtt.connect(Options["mqtt"]["server"], Options["mqtt"]["port"])
    except Exception as e:
        logger.error("MQTT server address/port may be incorrect! (%s)", e)
        sys.exit(1)

    mqtt.loop_start()

    delay = 1
    while not mqtt_connected:
        logger.info("waiting MQTT connected ...")
        time.sleep(delay)
        delay = min(delay * 2, 10)


def serial_new_device(device, packet, idn=None):
    prefix = Options["mqtt"]["prefix"]

    # 조명은 두 id를 조합해서 개수와 번호를 정해야 함
    if device == "light":
        grp_id = int(packet[2] >> 4)
        rm_id = int(packet[2] & 0x0F)
        light_count = int(packet[4])

        for light_id in range(1, light_count + 1):
            entity_id = f"{rm_id}_{light_id}"
            if entity_id not in registered_entities["light"]:
                payload = DISCOVERY_PAYLOAD[device][0].copy()
                payload["~"] = payload["~"].format(prefix=prefix, idn=entity_id)
                payload["name"] = payload["name"].format(room=rm_id, num=light_id)
                mqtt_discovery(payload)
                registered_entities["light"].add(entity_id)

    elif device == "plug":
        grp_id = int(packet[2] >> 4)
        plug_count = int(packet[4] / 3)

        for plug_id in range(1, plug_count + 1):
            entity_id = f"{grp_id}_{plug_id}"
            if entity_id not in registered_entities["plug"]:
                for index in range(len(DISCOVERY_PAYLOAD[device])):
                    payload = DISCOVERY_PAYLOAD[device][index].copy()
                    payload["~"] = payload["~"].format(prefix=prefix, idn=entity_id)
                    payload["name"] = payload["name"].format(room=grp_id, num=plug_id)
                    mqtt_discovery(payload)
                registered_entities["plug"].add(entity_id)

    elif device == "thermostat":
        grp_id = int(packet[2] >> 4)
        room_count = int((int(packet[4]) - 5) / 2)

        for room_id in range(1, room_count + 1):
            entity_id = str(room_id)
            if entity_id not in registered_entities["thermostat"]:
                payload = DISCOVERY_PAYLOAD[device][0].copy()
                payload["~"] = payload["~"].format(prefix=prefix, idn=entity_id)
                payload["name"] = payload["name"].format(room=room_id)
                mqtt_discovery(payload)
                registered_entities["thermostat"].add(entity_id)

    elif device in DISCOVERY_PAYLOAD:
        grp_id = int(packet[2] >> 4)

        for payloads in DISCOVERY_PAYLOAD[device]:
            payload = payloads.copy()
            payload["~"] = payload["~"].format(prefix=prefix, idn=idn)
            if device == "energy":
                if "type" in payload["name"]:
                    payload["name"] = payload["name"].format(type=("power","gas","water")[grp_id])
                else:
                    payload["name"] = payload["name"].format(idn=("power","gas","water")[grp_id])
                if grp_id > 0:
                    payload["val_tpl"] = "{{ value | float / 100 }}"
                    payload["unit_of_meas"] = ("W","m³/h","m³/h")[grp_id]
                    payload["dev_cla"] = ("power","gas","water")[grp_id]
            else:
                payload["name"] = payload["name"].format(prefix=prefix, idn=idn)

            mqtt_discovery(payload)


def serial_generate_checksum(packet):
    # 마지막 제외하고 모든 byte를 XOR
    checksum = 0
    for b in packet[:-1]:
        checksum ^= b

    # ADD 추가 생성
    add = (sum(packet) + checksum) & 0xFF
    return checksum, add


def serial_verify_checksum(packet):
    # 모든 byte를 마지막 ADD 빼고 XOR
    checksum = 0
    for b in packet[:-1]:
        checksum ^= b

    # ADD 계산
    add = sum(packet[:-1]) & 0xFF

    # checksum이 안맞으면 로그만 찍고 무시 ADD 까지 맞아야함.
    if checksum or add != packet[-1]:
        logger.warning("checksum fail! {}, {:02x}, {:02x}".format(packet.hex(), checksum, add))
        return False

    # 정상
    return True


def process_packet_buffer(conn):
    """버퍼에서 완전한 패킷을 찾아 처리합니다."""
    while conn.check_in_waiting() > 0:
        # 시작 F7 찾기
        start_index = -1
        for i in range(len(conn._recv_buf)):
            if conn._recv_buf[i] == 0xF7:
                start_index = i
                break
        
        if start_index == -1:
            # F7가 없으면 버퍼 비우기
            conn._recv_buf.clear()
            return
        
        # F7 이전 데이터 버리기
        if start_index > 0:
            del conn._recv_buf[0:start_index]
        
        # 최소 패킷 크기 확인 (F7 + header + length + checksum + add = 7)
        if len(conn._recv_buf) < 7:
            return
        
        # 헤더 확인
        header_1 = conn._recv_buf[1]
        header_2 = conn._recv_buf[2]
        header_3 = conn._recv_buf[3]
        
        # 길이 필드 위치 확인
        if header_1 in STATE_HEADER and header_3 in STATE_HEADER[header_1]:
            # state 패킷인 경우
            if len(conn._recv_buf) < 5:
                return
            data_length = conn._recv_buf[4]
            packet_length = 5 + data_length + 2  # F7 + 4 headers + data + checksum + add
        else:
            # 다른 패킷 타입 처리
            packet_length = 8  # 기본 패킷 길이
        
        # 완전한 패킷이 있는지 확인
        if len(conn._recv_buf) < packet_length:
            return
        
        # 패킷 추출
        packet = bytes(conn._recv_buf[0:packet_length])
        del conn._recv_buf[0:packet_length]
        
        # checksum 검증
        if not serial_verify_checksum(packet):
            continue
        
        # 패킷 처리
        if header_1 in STATE_HEADER and header_3 in STATE_HEADER[header_1]:
            device = STATE_HEADER[header_1][0]
            serial_receive_state(device, packet)
        elif header_1 in ACK_HEADER and header_3 in ACK_HEADER[header_1]:
            header = packet[0] << 24 | packet[1] << 16 | packet[2] << 8 | packet[3]
            if header in serial_ack:
                serial_ack_command(header)


def serial_get_header(conn):
    try:
        # 시작 F7 나올 때까지 대기
        while True:
            header_0 = conn.recv(1)[0]
            if header_0 == 0xF7:
                break

        # 연속 0xF7 무시
        while True:
            header_1 = conn.recv(1)[0]
            if header_1 != 0xF7:
                break
            header_0 = header_1

        header_2 = conn.recv(1)[0]
        header_3 = conn.recv(1)[0]

    except (OSError, serial.SerialException):
        logger.error("ignore exception!")
        header_0 = header_1 = header_2 = header_3 = 0

    # 헤더 반환
    return header_0, header_1, header_2, header_3


def serial_receive_state(device, packet):
    form = RS485_DEVICE[device]["state"]
    last = RS485_DEVICE[device]["last"]
    idn = (packet[1] << 8) | packet[2]

    # 해당 ID의 이전 상태와 같은 경우 바로 무시
    if last.get(idn) == packet:
        return

    # 처음 받은 상태인 경우, discovery 용도로 등록한다.
    if Options["mqtt"]["_discovery"] and not last.get(idn):
        serial_new_device(device, packet, idn)
        last[idn] = True

        # 장치 등록 먼저 하고, 상태 등록은 그 다음 턴에 한다. (난방 상태 등록 무시되는 현상 방지)
        return

    else:
        last[idn] = packet

    prefix = Options["mqtt"]["prefix"]
    state_suffix = Options["mqtt"]["state_topic_suffix"]

    if device == "light":
        grp_id = int(packet[2] >> 4)
        rm_id = int(packet[2] & 0x0F)
        light_count = int(packet[4])

        for light_id in range(1, light_count + 1):
            # 등록되지 않은 엔티티면 먼저 등록
            entity_id = f"{rm_id}_{light_id}"
            if entity_id not in registered_entities["light"]:
                serial_new_device(device, packet, idn)
            
            if packet[5 + light_id - 1] & 1:
                value = "ON"
            else:
                value = "OFF"

            topic = f"{prefix}/{device}/{entity_id}/power{state_suffix}"
            if last_topic_list.get(topic) != value:
                logger.debug("publish to HA: %s = %s (%s)", topic, value, packet.hex())
                mqtt.publish(topic, value)
                last_topic_list[topic] = value

    elif device == "plug":
        grp_id = int(packet[2] >> 4)
        plug_count = int(packet[4] / 3)

        for plug_id in range(1, plug_count + 1):
            # 등록되지 않은 엔티티면 먼저 등록
            entity_id = f"{grp_id}_{plug_id}"
            if entity_id not in registered_entities["plug"]:
                serial_new_device(device, packet, idn)
            
            for sub_topic, value in zip(
                ["power", "current"],
                [
                    "ON" if packet[plug_id * 3 + 3] & 0x10 else "OFF",
                    f"{format(packet[plug_id * 3 + 3] & 0x0F | packet[plug_id * 3 + 4] << 4 | packet[plug_id * 3 + 5] >> 4, 'x')}.{format(packet[plug_id * 3 + 5] & 0x0F, 'x')}",
                ],
            ):
                topic = f"{prefix}/{device}/{entity_id}/{sub_topic}{state_suffix}"
                if last_topic_list.get(topic) != value:
                    logger.debug("publish to HA: %s = %s (%s)", topic, value, packet.hex())
                    mqtt.publish(topic, value)
                    last_topic_list[topic] = value

    elif device == "thermostat":
        grp_id = int(packet[2] >> 4)
        room_count = int((int(packet[4]) - 5) / 2)

        for thermostat_id in range(1, room_count + 1):
            # 등록되지 않은 엔티티면 먼저 등록
            entity_id = str(thermostat_id)
            if entity_id not in registered_entities["thermostat"]:
                serial_new_device(device, packet, idn)
            
            if ((packet[6] & 0x1F) >> (thermostat_id - 1)) & 1:
                value1 = "heat"
            else:
                value1 = "off"
            if ((packet[7] & 0x1F) >> (thermostat_id - 1)) & 1:
                value2 = "heat"
            else:
                value2 = "off"

            for sub_topic, value in zip(
                ["mode", "away", "target", "current"],
                [
                    value1,
                    value2,
                    packet[8 + thermostat_id * 2],
                    packet[9 + thermostat_id * 2],
                ],
            ):
                topic = f"{prefix}/{device}/{entity_id}/{sub_topic}{state_suffix}"
                if last_topic_list.get(topic) != value:
                    logger.debug("publish to HA: %s = %s (%s)", topic, value, packet.hex())
                    mqtt.publish(topic, value)
                    last_topic_list[topic] = value

    elif device == "fan":
        if packet[6] & 0x01:
            value1 = "ON"
        else:
            value1 = "OFF"
        if (packet[8] & 0x03) == 0x01:
            value2 = "bypass"
        elif (packet[8] & 0x03) == 0x03:
            value2 = "heat"
        else:
            value2 = "unknown"

        for sub_topic, value in zip(
            ["power", "mode", "speed"],
            [
                value1,
                value2,
                int(packet[7]),
            ],
        ):
            topic = f"{prefix}/{device}/{idn}/{sub_topic}{state_suffix}"
            if last_topic_list.get(topic) != value:
                logger.debug("publish to HA: %s = %s (%s)", topic, value, packet.hex())
                mqtt.publish(topic, value)
                last_topic_list[topic] = value

    elif device == "gas":
        topic = f"{prefix}/{device}/{idn}/valve{state_suffix}"
        if ((packet[6] & 0x1F) >> 4) == 0x01:
            value = "open"
        elif ((packet[6] & 0x1F) >> 4) == 0x02:
            value = "opening"
        elif ((packet[6] & 0x1F) >> 4) == 0x03:
            value = "closing"
        else:
            value = "closed"

        if last_topic_list.get(topic) != value:
            logger.debug("publish to HA: %s = %s (%s)", topic, value, packet.hex())
            mqtt.publish(topic, value)
            last_topic_list[topic] = value

    elif device == "energy":
        topic = f"{prefix}/{device}/{idn}/power{state_suffix}"
        value = int(packet.hex()[12:18])
        if last_topic_list.get(topic) != value:
            logger.debug("publish to HA: %s = %s (%s)", topic, value, packet.hex())
            mqtt.publish(topic, value)
            last_topic_list[topic] = value

        topic = f"{prefix}/{device}/{idn}/usage{state_suffix}"
        value = f"{int(packet.hex()[20:26]) * 0.1 : .1f}"
        if last_topic_list.get(topic) != value:
            logger.debug("publish to HA: %s = %s (%s)", topic, value, packet.hex())
            mqtt.publish(topic, value)
            last_topic_list[topic] = value

    elif device == "elevator":
        topic = f"{prefix}/{device}/{idn}/power{state_suffix}"
        if (packet[6] >> 4) == 0:
            value = "off"
        elif (packet[6] & 0xF0) == 0x20:
            value = "on"
        elif (packet[6] & 0xF0) == 0x40:
            value = "cut"
        else:
            value = str(packet[6] >> 4)

        if last_topic_list.get(topic) != value:
            logger.debug("publish to HA: %s = %s (%s)", topic, value, packet.hex())
            mqtt.publish(topic, value)
            last_topic_list[topic] = value

    elif device == "doorbell":
        event = {
            0x82: "state",
            0x93: "ring",
            0x12: "talk",
            0x22: "open",
            0x11: "cancel",
        }.get(packet[3], "off")

        topic = f"{prefix}/{device}/{idn}/{event}"
        value = "on" if event == "ring" else str(packet[3])
        if last_topic_list.get(topic) != value:
            logger.debug("publish to HA: %s = %s (%s)", topic, value, packet.hex())
            mqtt.publish(topic, value)
            last_topic_list[topic] = value


def serial_send_command(conn):
    # 한번에 여러개 보내면 응답이랑 꼬여서 망함
    cmd = next(iter(serial_queue))
    if conn.capabilities != "ALL" and ACK_HEADER[cmd[1]][0] not in conn.capabilities:
        return
    conn.send(cmd)

    # Ezville은 4 Byte까지 확인 필요
    ack = bytearray(cmd[0:4])
    ack[3] = ACK_MAP[cmd[1]][cmd[3]]
    waive_ack = False
    if ack[3] == 0x00:
        waive_ack = True
    ack = int.from_bytes(ack, "big")

    # retry time 관리, 초과했으면 제거
    elapsed = time.time() - serial_queue[cmd]
    if elapsed > Options["rs485"]["max_retry"]:
        logger.error("send to device: %s max retry time exceeded!", cmd.hex())
        serial_queue.pop(cmd)
        serial_ack.pop(ack, None)
    elif elapsed > 3:
        logger.warning("send to device: {}, try another {:.01f} seconds...".format(cmd.hex(), Options["rs485"]["max_retry"] - elapsed))
        serial_ack[ack] = cmd
    elif waive_ack:
        logger.info("waive ack: %s", cmd.hex())
        serial_queue.pop(cmd)
        serial_ack.pop(ack, None)
    else:
        logger.info("send to device: %s", cmd.hex())
        serial_ack[ack] = cmd


def serial_ack_command(packet):
    logger.info("ack from device: {} ({:x})".format(serial_ack[packet].hex(), packet))

    # 성공한 명령을 지움
    serial_queue.pop(serial_ack[packet], None)
    serial_ack.pop(packet)


def daemon(conn):
    logger.info("start loop ...")
    send_aggressive = False

    while True:
        # 로그 출력
        sys.stdout.flush()

        # 버퍼에 있는 패킷 처리
        process_packet_buffer(conn)

        # 명령 전송이 필요한 경우
        if serial_queue and not conn.check_pending_recv():
            serial_send_command(conn=conn)
            conn.set_pending_recv()

        # 잠시 대기
        time.sleep(0.01)


def init_connect(conn):
    dump_time = Options["rs485"]["dump_time"]

    if dump_time > 0:
        start_time = time.time()
        logger.warning("packet dump for {} seconds!".format(dump_time))

        conn.set_timeout(2)
        logs = []
        while time.time() - start_time < dump_time:
            try:
                data = conn.recv(128)
            except:
                continue

            if data:
                for b in data:
                    if b == 0xF7 or len(logs) > 500:
                        logger.info("".join(logs))
                        logs = ["{:02X}".format(b)]
                    else:
                        logs.append(",  {:02X}".format(b))
        logger.info("".join(logs))
        logger.warning("dump done.")
        conn.set_timeout(None)


if __name__ == "__main__":
    # configuration 로드 및 로거 설정
    init_logger()
    init_option(sys.argv)
    init_logger_file()
    start_mqtt_loop()

    if Options["serial_mode"] == "sockets":
        for _socket in Options["sockets"]:
            conn = EzVilleSocket(_socket["address"], _socket["port"], _socket["capabilities"])
            init_connect(conn=conn)
            thread = threading.Thread(target=daemon, args=(conn,))
            thread.daemon = True
            thread.start()
        while True:
            time.sleep(10**8)
    elif Options["serial_mode"] == "socket":
        logger.info("initialize socket...")
        conn = EzVilleSocket(Options["socket"]["address"], Options["socket"]["port"])
    else:
        logger.info("initialize serial...")
        conn = EzVilleSerial()

    if Options["serial_mode"] != "sockets":
        init_connect(conn=conn)
        try:
            daemon(conn=conn)
        except:
            logger.exception("wallpad finished!")
