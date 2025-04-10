import os
import time
import sys
import json
import re
import random
import threading
import traceback
import logging
import psutil
import requests
import subprocess

import paho.mqtt.client as paho
import qrcode

import lvgl as lv


class JSONWithCommentsDecoder(json.JSONDecoder):
    def __init__(self, **kwgs):
        super().__init__(**kwgs)
    def decode(self, s: str):
        regex = r"""("(?:\\"|[^"])*?")|(\/\*(?:.|\s)*?\*\/|\/\/.*)"""
        s = re.sub(regex, r"\1", s)  # , flags = re.X | re.M)
        return super().decode(s)

cache_items = {}

def wrap(txt, width):
    tmp = ""
    for i in txt.split():
        if len(tmp) + len(i) < width:
            tmp += " " + i
        else:
            yield tmp.strip()
            tmp = i
    if tmp:
        yield tmp.strip()
def shell(command):
    if USING_SIMULATOR:
        result = subprocess.check_output(['sh', '-c', command])
        result = result.decode('utf-8').strip()
    else:
        temp_output = f'/tmp/rinkhals/output-{random.randint(1000, 9999)}'

        os.system(f'{command} > {temp_output}')
        if os.path.exists(temp_output):
            with open(temp_output) as f:
                result = f.read().strip()
            os.remove(temp_output)
        else:
            result = ''

    logging.info(f'Shell "{command}" => "{result}"')
    return result
def shell_async(command, callback):
    def thread():
        result = shell(command)
        if callback:
            callback(result)
    t = threading.Thread(target=thread)
    t.start()
def run_async(callback):
    t = threading.Thread(target=callback)
    t.start()
def ellipsis(text, length):
    if len(text) > length:
        text = text[:int(length / 2)] + '...' + text[-int(length / 2):]
    return text
def cache(getter, key = None):
    key = key or ''
    key = f'line:{sys._getframe().f_back.f_lineno}|{key}'
    item = cache_items.get(key)
    if item is None:
        item = getter()
        cache_items[key] = item
    return item


DEBUG = os.getenv('DEBUG')
DEBUG = not not DEBUG
#DEBUG = True

# Setup logging
logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG if DEBUG else logging.INFO)

# Detect Rinkhals root
SCRIPT_PATH = os.path.dirname(os.path.realpath(__file__))
RINKHALS_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(SCRIPT_PATH)))

USING_SIMULATOR = lv.helpers.is_windows()
USING_SHELL = True
if USING_SIMULATOR:
    if os.system('sh -c "echo"') != 0:
        USING_SHELL = False
    else:
        RINKHALS_ROOT = RINKHALS_ROOT.replace('\\', '/')
    if os.system('sh -c "ls /mnt/c"') == 0:
        RINKHALS_ROOT = '/mnt/' + RINKHALS_ROOT[0].lower() + RINKHALS_ROOT[2:]

# Detect environment and tools
if USING_SIMULATOR:
    RINKHALS_HOME = f'{RINKHALS_ROOT}/../4-apps/home/rinkhals'
    RINKHALS_VERSION = 'dev'
    KOBRA_MODEL = 'Anycubic Kobra'
    KOBRA_MODEL_CODE = 'KS1'
    #KOBRA_MODEL_CODE = 'K3'
    KOBRA_VERSION = '1.2.3.4'

    if KOBRA_MODEL_CODE == 'KS1':
        QT_QPA_PLATFORM = 'linuxfb:fb=/dev/fb0:size=800x480:rotation=180:offset=0x0:nographicsmodeswitch'
    else:
        QT_QPA_PLATFORM = 'linuxfb:fb=/dev/fb0:size=480x272:rotation=90:offset=0x0:nographicsmodeswitch'

    def list_apps():
        system_apps = [ f.name for f in os.scandir(f'{RINKHALS_HOME}/apps') if f.is_dir() ]
        user_apps = [ f.name for f in os.scandir(f'{RINKHALS_ROOT}/../../../Rinkhals.apps/apps') if f.is_dir() ] if os.path.exists(f'{RINKHALS_ROOT}/../../../Rinkhals.apps/apps') else []
        additional_apps = [ 'test-1', 'test-2', 'test-3', 'test-4', 'test-5', 'test-6', 'test-7', 'test-8' ]
        return ' '.join(system_apps + user_apps + additional_apps)
    def get_app_root(app):
        if os.path.exists(f'{RINKHALS_HOME}/apps/{app}'): return f'{RINKHALS_HOME}/apps/{app}'
        if os.path.exists(f'{RINKHALS_ROOT}/../../../Rinkhals.apps/apps/{app}'): return f'{RINKHALS_ROOT}/../../../Rinkhals.apps/apps/{app}'
        return ''
    def is_app_enabled(app): return '1' if os.path.exists(f'{RINKHALS_HOME}/apps/{app}/.enabled') else '0'
    def get_app_status(app): return 'started' if is_app_enabled(app) == '1' else 'stopped'
    def get_app_pids(app): return str(os.getpid()) if get_app_status(app) == 'started' else ''
    def enable_app(app): pass
    def disable_app(app): pass
    def start_app(app): pass
    def stop_app(app): pass
    def get_app_property(app, property): return 'https://github.com/jbatonnet/Rinkhals' if property == 'link_output' else ''
    def set_app_property(app, property, value): pass
    def set_temporary_app_property(app, property, value): pass

    def are_apps_enabled(): return { a: is_app_enabled(a) for a in list_apps().split(' ') }
else:
    environment = shell(f'. /useremain/rinkhals/.current/tools.sh && python -c "import os, json; print(json.dumps(dict(os.environ)))"')
    environment = json.loads(environment)

    RINKHALS_ROOT = environment['RINKHALS_ROOT']
    RINKHALS_HOME = environment['RINKHALS_HOME']
    RINKHALS_VERSION = environment['RINKHALS_VERSION']
    KOBRA_MODEL_ID = environment['KOBRA_MODEL_ID']
    KOBRA_MODEL = environment['KOBRA_MODEL']
    KOBRA_MODEL_CODE = environment['KOBRA_MODEL_CODE']
    KOBRA_VERSION = environment['KOBRA_VERSION']
    KOBRA_DEVICE_ID = environment['KOBRA_DEVICE_ID']
    QT_QPA_PLATFORM = environment['QT_QPA_PLATFORM']

    def load_tool_function(function_name):
        def tool_function(*args):
            return shell(f'. /useremain/rinkhals/.current/tools.sh && {function_name} ' + ' '.join([ str(a) for a in args ]))
        return tool_function

    list_apps = load_tool_function('list_apps')
    get_app_root = load_tool_function('get_app_root')
    get_app_status = load_tool_function('get_app_status')
    get_app_pids = load_tool_function('get_app_pids')
    is_app_enabled = load_tool_function('is_app_enabled')
    enable_app = load_tool_function('enable_app')
    disable_app = load_tool_function('disable_app')
    start_app = load_tool_function('start_app')
    stop_app = load_tool_function('stop_app')
    get_app_property = load_tool_function('get_app_property')
    set_app_property = load_tool_function('set_app_property')
    set_temporary_app_property = load_tool_function('set_temporary_app_property')

    def are_apps_enabled():
        result = shell('. /useremain/rinkhals/.current/tools.sh && for a in $(list_apps); do echo "$a $(is_app_enabled $a)"; done')
        apps = result.splitlines()
        apps = [ a.split(' ') for a in apps ]
        return { a[0]: a[1] for a in apps }
        
# Detect screen parameters
screen_options = QT_QPA_PLATFORM.split(':')
screen_options = [ o.split('=') for o in screen_options ]
screen_options = { o[0]: o[1] if len(o) > 1 else None for o in screen_options }

resolution_match = re.search('^([0-9]+)x([0-9]+)$', screen_options['size'])

SCREEN_WIDTH = int(resolution_match[1])
SCREEN_HEIGHT = int(resolution_match[2])
SCREEN_ROTATION = int(screen_options['rotation'])

if SCREEN_ROTATION % 180 == 90:
    (SCREEN_WIDTH, SCREEN_HEIGHT) = (SCREEN_HEIGHT, SCREEN_WIDTH)

if KOBRA_MODEL_CODE == 'KS1':
    TOUCH_CALIBRATION_MIN_X = 800
    TOUCH_CALIBRATION_MAX_X = 0
    TOUCH_CALIBRATION_MIN_Y = 480
    TOUCH_CALIBRATION_MAX_Y = 0
else:
    TOUCH_CALIBRATION_MIN_X = 235
    TOUCH_CALIBRATION_MAX_X = 25
    TOUCH_CALIBRATION_MIN_Y = 460
    TOUCH_CALIBRATION_MAX_Y = 25

# Detect LAN mode
REMOTE_MODE = 'cloud'
if os.path.isfile('/useremain/dev/remote_ctrl_mode'):
    with open('/useremain/dev/remote_ctrl_mode', 'r') as f:
        REMOTE_MODE = f.read().strip()


class Program:
    display = None

    def __init__(self):
        lv.init()

        if lv.helpers.is_windows():
            self.display = lv.windows_create_display('Rinkhals', SCREEN_WIDTH, SCREEN_HEIGHT, 100, False, True)
            touch = lv.windows_acquire_pointer_indev(self.display)
            touch.set_display(self.display)

        elif lv.helpers.is_linux():
            self.display = lv.linux_fbdev_create()
            lv.linux_fbdev_set_file(self.display, '/dev/fb0')

            if SCREEN_ROTATION == 0: self.display.set_rotation(lv.DISPLAY_ROTATION._0)
            elif SCREEN_ROTATION == 90: self.display.set_rotation(lv.DISPLAY_ROTATION._90)
            elif SCREEN_ROTATION == 180: self.display.set_rotation(lv.DISPLAY_ROTATION._180)
            elif SCREEN_ROTATION == 270 or SCREEN_ROTATION == -90: self.display.set_rotation(lv.DISPLAY_ROTATION._270)

            touch = lv.evdev_create(lv.INDEV_TYPE.POINTER, '/dev/input/event0')
            touch.set_display(self.display)

            lv.evdev_set_calibration(touch, TOUCH_CALIBRATION_MIN_X, TOUCH_CALIBRATION_MIN_Y, TOUCH_CALIBRATION_MAX_X, TOUCH_CALIBRATION_MAX_Y)

        if KOBRA_MODEL_CODE == 'KS1':
            self.display.set_dpi(180)
        else:
            self.display.set_dpi(130)

        logging.debug(f'Root: {RINKHALS_ROOT}')
        logging.debug(f'Home: {RINKHALS_HOME}')

        # Subscribe to print event to exit in case of print
        if not lv.helpers.is_linux() and REMOTE_MODE == 'lan':
            self.monitor_mqtt()

        # Monitor K3SysUi process to exit if it dies
        if lv.helpers.is_linux():
            monitor_thread = threading.Thread(target = self.monitor_k3sysui)
            monitor_thread.start()

        # Layout and draw
        global lvr
        import lvgl_rinkhals as lvr

        self.layout()

    def monitor_k3sysui(self):
        pid = shell("ps | grep K3SysUi | grep -v grep | awk '{print $1}'")
        pid = int(pid)

        logging.info(f'Monitoring K3SysUi (PID: {pid})')

        while True:
            time.sleep(5)

            try:
                os.kill(pid, 0)
            except OSError:
                logging.info('K3SysUi is gone, exiting...')
                self.quit()
    def monitor_mqtt(self):
        def mqtt_on_connect(client, userdata, flags, reason_code, properties):
            client.subscribe(f'anycubic/anycubicCloud/v1/+/printer/{KOBRA_MODEL_ID}/{KOBRA_DEVICE_ID}/print')
            logging.info('Monitoring MQTT...')
        def mqtt_on_connect_fail(client, userdata):
            logging.info('MQTT connection failed')
        def mqtt_on_log(client, userdata, level, buf):
            logging.debug(buf)
        def mqtt_on_message(client, userdata, msg):
            logging.info('Received print event, exiting...')
            self.quit()

        with open('/userdata/app/gk/config/device_account.json', 'r') as f:
            json_data = f.read()
            data = json.loads(json_data)

            mqtt_username = data['username']
            mqtt_password = data['password']

        client = paho.Client(protocol = paho.MQTTv5)
        client.on_connect = mqtt_on_connect
        client.on_connect_fail = mqtt_on_connect_fail
        client.on_message = mqtt_on_message
        client.on_log = mqtt_on_log

        client.username_pw_set(mqtt_username, mqtt_password)
        client.connect('127.0.0.1', 2883)
        client.loop_start()

    def layout(self):

        self.screen_rinkhals = lvr.screen()
        if self.screen_rinkhals:
            self.screen_rinkhals.set_flex_flow(lv.FLEX_FLOW.COLUMN)
            self.screen_rinkhals.set_flex_align(lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)
            self.screen_rinkhals.set_style_pad_row(-lv.dpx(3), lv.STATE_DEFAULT)

            rinkhals_icon = lvr.image(self.screen_rinkhals)
            rinkhals_icon.set_src(SCRIPT_PATH + '/icon.png')
            lvr.scale_image(rinkhals_icon, lv.dpx(90))

            label_rinkhals = lvr.title(self.screen_rinkhals)
            label_rinkhals.set_text('Rinkhals')
            label_rinkhals.set_style_pad_top(lv.dpx(20), lv.STATE_DEFAULT)
            label_rinkhals.set_style_pad_bottom(lv.dpx(10), lv.STATE_DEFAULT)
            
            self.screen_rinkhals.label_firmware = lvr.subtitle(self.screen_rinkhals)
            self.screen_rinkhals.label_firmware.set_text('Firmware:')

            self.screen_rinkhals.label_version = lvr.subtitle(self.screen_rinkhals)
            self.screen_rinkhals.label_version.set_text('Version:')
            
            self.screen_rinkhals.label_root = lvr.subtitle(self.screen_rinkhals)
            self.screen_rinkhals.label_root.set_text('Root: ?')
            
            self.screen_rinkhals.label_home = lvr.subtitle(self.screen_rinkhals)
            self.screen_rinkhals.label_home.set_text('Home: ?')
            
            self.screen_rinkhals.label_disk = lvr.subtitle(self.screen_rinkhals)
            self.screen_rinkhals.label_disk.set_text('Disk usage: ?')

            button_exit = lvr.button_icon(self.screen_rinkhals)
            button_exit.add_flag(lv.OBJ_FLAG.IGNORE_LAYOUT)
            button_exit.align(lv.ALIGN.TOP_LEFT, -lvr.GLOBAL_PADDING, -lvr.GLOBAL_PADDING)
            button_exit.set_style_border_width(0, lv.STATE_DEFAULT)
            button_exit.set_style_bg_color(lvr.COLOR_BACKGROUND, lv.STATE_DEFAULT)
            button_exit.add_event_cb(lambda e: self.quit(), lv.EVENT_CODE.CLICKED, None)
            button_exit_label = lvr.label(button_exit)
            button_exit_label.center()
            button_exit_label.set_text('')

        self.screen_main = lvr.screen()
        if self.screen_main:
            self.screen_main.set_flex_flow(lv.FLEX_FLOW.COLUMN)
            self.screen_main.set_flex_align(lv.FLEX_ALIGN.START, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)
            self.screen_main.set_style_pad_row(lvr.GLOBAL_PADDING, lv.STATE_DEFAULT)

            self.screen_main.button_apps = lvr.button(self.screen_main)
            self.screen_main.button_apps.set_width(lv.pct(100))
            button_apps_label = lv.label(self.screen_main.button_apps)
            button_apps_label.set_text('Manage apps')
            button_apps_label.center()
            
            self.screen_main.button_ota = lvr.button(self.screen_main)
            self.screen_main.button_ota.set_width(lv.pct(100))
            button_ota_label = lv.label(self.screen_main.button_ota)
            button_ota_label.set_text('Check for updates')
            button_ota_label.center()

            self.screen_main.button_settings = lvr.button(self.screen_main)
            self.screen_main.button_settings.set_width(lv.pct(100))
            button_settings_label = lv.label(self.screen_main.button_settings)
            button_settings_label.set_style_text_color(lvr.COLOR_DANGER, lv.STATE_DEFAULT)
            button_settings_label.set_text('Advanced settings')
            button_settings_label.center()
            
        self.screen_container = lvr.screen()

        if SCREEN_WIDTH > SCREEN_HEIGHT:
            self.screen_composition = lvr.screen()

            self.screen_rinkhals.set_parent(self.screen_composition)
            self.screen_container.set_parent(self.screen_composition)

            lvr.label(self.screen_composition).set_text('dede')

            self.screen_rinkhals.set_align(lv.ALIGN.LEFT_MID)
            self.screen_rinkhals.set_width(lv.pct(50))
            self.screen_rinkhals.set_height(lv.pct(100))
            self.screen_rinkhals.center()

            self.screen_container.set_align(lv.ALIGN.RIGHT_MID)
            self.screen_container.set_width(lv.pct(50))
            self.screen_container.set_height(lv.pct(100))
            self.screen_container.set_style_bg_opa(lv.OPA_30, 0)

            lv.screen_load(self.screen_rinkhals)

        else:
            self.screen_rinkhals.set_align(lv.ALIGN.TOP_MID)
            self.screen_rinkhals.set_width(lv.pct(100))
            self.screen_rinkhals.set_height(lv.pct(50))

            self.screen_main.set_align(lv.ALIGN.BOTTOM_MID)
            self.screen_main.set_width(lv.pct(100))
            self.screen_main.set_height(lv.pct(50))
            
            screen_composition = lvr.screen()
            self.screen_rinkhals.set_parent(screen_composition)
            self.screen_main.set_parent(screen_composition)

            self.screen_main = screen_composition
            lv.screen_load(self.screen_container)


        #self.screen_main.set_parent(self.screen_container)
        return

        # Rinkhals logo and general information
        self.panel_rinkhals = myPanel(left=0, top=0, bottom=0, components=[
            myStackPanel(left=0, right=0, top=0, bottom=0, background_color=None, components=[
                Picture(SCRIPT_PATH + '/icon.png', top=40, height=64),
                myLabel('Rinkhals', font_size=FONT_TITLE_SIZE, top=20),
                firmware_label := myLabel('Firmware:', font_size=FONT_SUBTITLE_SIZE, text_color=COLOR_SUBTITLE, top=8),
                version_label := myLabel('Version:', font_size=FONT_SUBTITLE_SIZE, text_color=COLOR_SUBTITLE, top=2),
                root_label := myLabel('Root:', font_size=FONT_SUBTITLE_SIZE, text_color=COLOR_SUBTITLE, top=2),
                home_label := myLabel('Home:', font_size=FONT_SUBTITLE_SIZE, text_color=COLOR_SUBTITLE, top=2),
                disk_label := myLabel('Disk usage:', font_size=FONT_SUBTITLE_SIZE, text_color=COLOR_SUBTITLE, top=2)
            ]),
            myButton('', font_path=ICON_FONT_PATH, font_size=24, left=0, right=None, width=48, top=0, background_color=None, border_width=0, callback=lambda: self.quit())
        ])
        self.panel_rinkhals.firmware_label = firmware_label
        self.panel_rinkhals.version_label = version_label
        self.panel_rinkhals.root_label = root_label
        self.panel_rinkhals.home_label = home_label
        self.panel_rinkhals.disk_label = disk_label

        # Main menu
        self.panel_main = myStackPanel(left=0, right=0, bottom=0, components=[
            myButton('Manage apps', left=8, right=8, callback=lambda: self.set_screen_panel(self.panel_apps)),
            #myButton('Settings', left=8, right=8, callback=lambda: self.set_screen_panel(self.panel_apps)),
            myButton('Check for updates', left=8, right=8, callback=self.layout_ota),
            myButton('Advanced settings', left=8, right=8, text_color=COLOR_DANGER, callback=lambda: self.set_screen_panel(self.panel_advanced)),
        ])

        # Advanced menu
        self.panel_advanced = myStackPanel(left=0, right=0, top=0, bottom=0, components=[
            myPanel(left=0, right=0, top=0, height=48, components=[
                myLabel('Advanced', font_size=FONT_TITLE_SIZE, auto_size=False, left=0, right=0, top=0, bottom=0),
                myButton('', font_path=ICON_FONT_PATH, font_size=24, left=0, right=None, width=48, top=0, bottom=0, background_color=None, border_width=0, callback=lambda: self.set_screen_panel(self.panel_main)),
            ]),

            myButton('Reboot printer', left=8, right=8, callback=lambda: self.show_text_dialog('Are you sure you want\nto reboot your printer?', action='Yes', callback=lambda: self.reboot_printer())),
            myButton('Restart Rinkhals', left=8, right=8, callback=lambda: self.show_text_dialog('Are you sure you want\nto restart Rinkhals?', action='Yes', callback=lambda: self.restart_rinkhals())),
            myButton('Switch to stock', left=8, right=8, callback=lambda: self.show_text_dialog('Are you sure you want\nto switch to stock firmware?\n\nYou can reboot your printer\nto start Rinkhals again', action='Yes', callback=lambda: self.stop_rinkhals())),
            myButton('Disable Rinkhals', text_color=COLOR_DANGER, left=8, right=8, callback=lambda: self.show_text_dialog('Are you sure you want\nto disable Rinkhals?\n\nYou will need to reinstall\nRinkhals to start it again', action='Yes', action_color=COLOR_DANGER, callback=lambda: self.disable_rinkhals()))
        ])

        # App list and quick toggle
        self.panel_apps = myPanel(left=0, right=0, top=0, bottom=0, components=[
            apps_panel := ScrollPanel(left=0, right=0, top=48, bottom=0),
            myPanel(left=0, right=0, top=0, height=48, components=[
                myLabel('Manage apps', font_size=FONT_TITLE_SIZE, auto_size=False, left=0, right=0, top=0, bottom=0),
                myButton('', font_path=ICON_FONT_PATH, font_size=24, left=0, right=None, width=48, top=0, bottom=0, background_color=None, border_width=0, callback=lambda: self.set_screen_panel(self.panel_main)),
                myButton('', font_path=ICON_FONT_PATH, font_size=24, left=None, right=0, width=48, top=0, bottom=0, background_color=None, border_width=0, callback=lambda: self.set_screen_panel(self.panel_apps))
            ])
        ])
        self.panel_apps.apps_panel = apps_panel

        # Detailed app screen
        self.panel_app = myPanel(left=0, right=0, top=0, bottom=0, components=[
            myScrollPanel(left=0, right=0, top=48, bottom=0, components=[
                app_version := myLabel(top=0, font_size=FONT_SUBTITLE_SIZE, text_color=COLOR_SUBTITLE),
                app_path := myLabel(top=2, font_size=FONT_SUBTITLE_SIZE, text_color=COLOR_SUBTITLE),
                app_description := myLabel(top=6, font_size=FONT_SUBTITLE_SIZE, text_align='mm'),
                myPanel(left=0, right=0, top=16, height=48, components=[
                    myPanel(left=0, width=96, top=0, bottom=0, background_color=None, components=[
                        myLabel('Disk', left=0, right=0, top=0, height=20, auto_size=False, font_size=FONT_SUBTITLE_SIZE, text_color=COLOR_SUBTITLE),
                        app_size := myLabel('?', left=0, right=0, top=18, height=24, auto_size=False),
                    ]),
                    myPanel(left=0, right=0, top=0, bottom=0, background_color=None, components=[
                        myLabel('Memory', left=0, right=0, top=0, height=20, auto_size=False, font_size=FONT_SUBTITLE_SIZE, text_color=COLOR_SUBTITLE),
                        app_memory := myLabel('?', left=0, right=0, top=18, height=24, auto_size=False),
                    ]),
                    myPanel(right=0, width=96, top=0, bottom=0, background_color=None, components=[
                        myLabel('CPU', left=0, right=0, top=0, height=20, auto_size=False, font_size=FONT_SUBTITLE_SIZE, text_color=COLOR_SUBTITLE),
                        app_cpu :=myLabel('?', left=0, right=0, top=18, height=24, auto_size=False),
                    ])
                ]),
                myPanel(left=0, right=0, top=8, height=48, components=[
                    app_enable := myButton('Enable', left=8, right=120, top=0, height=48),
                    app_settings := myButton('', font_path=ICON_FONT_PATH, font_size=28, left=None, right=64, top=0, height=48, width=48),
                    app_qr_code := myButton('', font_path=ICON_FONT_PATH, font_size=28, left=None, right=8, top=0, height=48, width=48)
                ]),
                app_start := myButton('Start', left=8, right=8, top=8, bottom=8, height=48)
            ]),
            myPanel(left=0, right=0, top=0, height=48, components=[
                app_title := myLabel('', font_size=FONT_TITLE_SIZE, auto_size=False, left=0, right=0, top=0, bottom=0),
                myButton('', font_path=ICON_FONT_PATH, font_size=24, left=0, right=None, width=48, top=0, bottom=0, background_color=None, border_width=0, callback=lambda: self.set_screen_panel(self.panel_apps)),
                app_refresh := myButton('', font_path=ICON_FONT_PATH, font_size=24, left=None, right=0, width=48, top=0, bottom=0, background_color=None, border_width=0)
            ])
        ])
        self.panel_app.app_title = app_title
        self.panel_app.app_refresh = app_refresh
        self.panel_app.app_version = app_version
        self.panel_app.app_path = app_path
        self.panel_app.app_description = app_description
        self.panel_app.app_size = app_size
        self.panel_app.app_memory = app_memory
        self.panel_app.app_cpu = app_cpu
        self.panel_app.app_settings = app_settings
        self.panel_app.app_qr_code = app_qr_code
        self.panel_app.app_enable = app_enable
        self.panel_app.app_start = app_start

        # OTA dialog
        self.panel_ota = StackPanel(left=0, right=0, top=0, bottom=0, background_color=(0, 0, 0, 192), layout_mode=Component.LayoutMode.Absolute, components=[
            StackPanel(width=min(360, self.screen.width - 24), top=0, height=self.screen.height, background_color=None, layout_mode=Component.LayoutMode.Absolute, orientation=StackPanel.Orientation.Horizontal, components=[
                myStackPanel(auto_size=True, left=0, right=0, components=[
                    myLabel('Check for updates', font_size=FONT_TITLE_SIZE, top=8),
                    # myPanel(left=8, right=8, top=16, height=56, components=[
                    #     myLabel('Firmware', left=8, right=0, top=4, bottom=0, auto_size=False, text_align='mt'),
                    #     myPanel(left=12, width=96, top=0, bottom=0, background_color=None, components=[
                    #         myLabel('Current', left=0, right=0, top=18, height=20, auto_size=False, font_size=FONT_SUBTITLE_SIZE, text_color=COLOR_SUBTITLE),
                    #         myLabel(f'{KOBRA_VERSION}', left=0, right=0, bottom=0, height=20, auto_size=False),
                    #     ]),
                    #     myPanel(right=12, width=96, top=0, bottom=0, background_color=None, components=[
                    #         myLabel('Latest', left=0, right=0, top=18, height=20, auto_size=False, font_size=FONT_SUBTITLE_SIZE, text_color=COLOR_SUBTITLE),
                    #         ota_latest_firmware := myLabel('-', left=0, right=0, bottom=0, height=20, auto_size=False),
                    #     ])
                    # ]),
                    myPanel(left=8, right=8, top=16, height=56, components=[
                        myLabel('Rinkhals', left=8, right=0, top=4, bottom=0, auto_size=False, text_align='mt'),
                        myPanel(left=12, width=96, top=0, bottom=0, background_color=None, components=[
                            myLabel('Current', left=0, right=0, top=18, height=20, auto_size=False, font_size=FONT_SUBTITLE_SIZE, text_color=COLOR_SUBTITLE),
                            myLabel(f'{ellipsis(RINKHALS_VERSION, 16)}', left=0, right=0, bottom=0, height=20, auto_size=False),
                        ]),
                        myPanel(right=12, width=96, top=0, bottom=0, background_color=None, components=[
                            myLabel('Latest', left=0, right=0, top=18, height=20, auto_size=False, font_size=FONT_SUBTITLE_SIZE, text_color=COLOR_SUBTITLE),
                            ota_latest_rinkhals := myLabel('-', left=0, right=0, bottom=0, height=20, auto_size=False),
                        ])
                    ]),
                    ota_progress_panel := myStackPanel(left=0, right=0, auto_size=True, components=[
                        myPanel(width=192, top=16, height=8, background_color=(64, 64, 64), components=[
                            ota_progress_bar := myPanel(left=0, width=48, top=0, bottom=0, background_color=COLOR_PRIMARY)
                        ]),
                        ota_progress_text := myLabel('24%', top=4)
                    ]),
                    myPanel(left=20, right=20, top=16, height=48, bottom=8, components=[
                        ota_cancel := myButton('Cancel', left=0, width=96, top=0),
                        ota_action := myButton('Refresh', left=None, right=0, width=96, top=0)
                    ])
                ])
            ])
        ])
        #self.panel_ota.ota_latest_firmware = ota_latest_firmware
        self.panel_ota.ota_latest_rinkhals = ota_latest_rinkhals
        self.panel_ota.ota_progress_panel = ota_progress_panel
        self.panel_ota.ota_progress_bar = ota_progress_bar
        self.panel_ota.ota_progress_text = ota_progress_text
        self.panel_ota.ota_cancel = ota_cancel
        self.panel_ota.ota_action = ota_action
        self.panel_ota.visible = False

        # Dialog overlay
        def dismiss_dialog():
            self.panel_dialog.visible = False
            self.screen.layout()
            self.screen.draw()

        self.panel_dialog = StackPanel(left=0, right=0, top=0, bottom=0, background_color=(0, 0, 0, 192), layout_mode=Component.LayoutMode.Absolute, touch_callback=dismiss_dialog, components=[
            StackPanel(width=min(360, self.screen.width - 48), top=0, height=self.screen.height, background_color=None, layout_mode=Component.LayoutMode.Absolute, orientation=StackPanel.Orientation.Horizontal, touch_callback=dismiss_dialog, components=[
                myStackPanel(auto_size=True, left=0, right=0, components=[
                    dialog_text := myLabel('', top=12, bottom=0),
                    dialog_qr := Picture(top=12, bottom=0, height=160, width=160),
                    dialog_button := myButton('', top=16, bottom=12, height=48, width=96)
                ])
            ])
        ])
        self.panel_dialog.dialog_text = dialog_text
        self.panel_dialog.dialog_qr = dialog_qr
        self.panel_dialog.dialog_button = dialog_button
        self.panel_dialog.visible = False

        # Screen setup, responsive design
        self.panel_screen = myPanel(right=0, top=0, bottom=0, background_color=None, layout_mode=Component.LayoutMode.Absolute)

        if self.screen.width > self.screen.height:
            self.panel_rinkhals.right = self.screen.width / 2
            self.panel_rinkhals.bottom = 0
            self.panel_screen.left = self.screen.width / 2
            self.panel_main.top = 0

            self.screen.components.append(self.panel_rinkhals)
            self.screen.components.append(self.panel_screen)
        else:
            self.panel_rinkhals.right = 0
            self.panel_rinkhals.bottom = 0
            self.panel_screen.left = 0
            self.panel_screen.top = 24
            self.panel_dialog.top = 24
            self.panel_ota.top = 24
            self.panel_main.top = self.screen.height - 210

            self.panel_main = Panel(left=0, right=0, top=0, bottom=0, components=[
                self.panel_rinkhals,
                self.panel_main
            ])

            self.screen.components.append(self.panel_screen)

        # On K2P and K3 redraw the title bar to keep information
        if KOBRA_MODEL_CODE != 'KS1':
            def draw_callback(draw, offset_x, offset_y):
                buffer = self.screen.capture()
                buffer = buffer.crop((0, 0, buffer.width, 24))
                draw._image.paste(buffer, (0, 0))

            self.screen.components.append(CallbackComponent(draw_callback=draw_callback, left=0, top=0, right=0, height=24))
        
        self.screen.components.append(self.panel_ota)
        self.screen.components.append(self.panel_dialog)
        self.screen.layout_mode = Component.LayoutMode.Absolute
        self.screen.layout()

        self.set_screen_panel(self.panel_main)

    def layout_main(self):
        self.panel_rinkhals.firmware_label.text = f'Firmware: {KOBRA_VERSION}'
        self.panel_rinkhals.version_label.text = f'Version: {RINKHALS_VERSION}'
        self.panel_rinkhals.root_label.text = f'Root: {ellipsis(RINKHALS_ROOT, 32)}'
        self.panel_rinkhals.home_label.text = f'Home: {ellipsis(RINKHALS_HOME, 32)}'
        self.panel_rinkhals.disk_label.text = f'Disk usage: ?'

        def update_disk_usage(result):
            self.panel_rinkhals.disk_label.text = f'Disk usage: {result}'
            
            with self.screen.draw_lock:
                self.panel_rinkhals.layout()
            self.screen.draw()

        if USING_SHELL:
            shell_async(f'df -Ph {RINKHALS_ROOT} | tail -n 1 | awk \'{{print $3 " / " $2 " (" $5 ")"}}\'', update_disk_usage)
    def layout_apps(self):
        def show_app(app):
            logging.info(f'Navigating to {app}...')
            self.set_screen_panel(self.panel_app)
            self.layout_app(app)
            self.screen.layout()
        def toggle_app(app, checked):
            if checked:
                logging.info(f'Enabling {app}...')
                enable_app(app)
                if get_app_status(app) != 'started':
                    logging.info(f'Starting {app}...')
                    start_app(app, 5)
            else:
                logging.info(f'Disabling {app}...')
                disable_app(app)
                if get_app_status(app) == 'started':
                    logging.info(f'Stopping {app}...')
                    stop_app(app)
            self.app_checkboxes[app].checked = is_app_enabled(app) == '1'
            
        self.panel_apps.apps_panel.components.clear()
        self.app_checkboxes = {}

        apps_enabled = are_apps_enabled()

        apps = list_apps().split(' ')
        for app in apps:
            enabled = apps_enabled[app] == '1'
            logging.info(f'Found {app}: {enabled}')

            component = myPanel(left=0, right=0, top=4, bottom=4, height=48, components=[
                myButton(app, top=0, text_align='lm', callback=lambda app=app: show_app(app)),
                app_checkbox := myCheckBox(right=12, top=4, checked=enabled, callback=lambda checked, app=app: toggle_app(app, checked))
            ])

            self.app_checkboxes[app] = app_checkbox
            self.panel_apps.apps_panel.components.append(component)
    def layout_app(self, app):
        def refresh_app(app):
            self.layout_app(app)
            self.screen.layout()
        def toggle_app(app):
            if is_app_enabled(app) == '1':
                logging.info(f'Disabling {app}...')
                disable_app(app)
            else:
                logging.info(f'Enabling {app}...')
                enable_app(app)
            self.layout_app(app)
            self.screen.layout()
        def _start_app(app):
            logging.info(f'Starting {app}...')
            start_app(app, 5)
            self.layout_app(app)
            self.panel_app.layout()
            self.screen.draw()
        def _stop_app(app):
            logging.info(f'Stopping {app}...')
            stop_app(app)
            self.layout_app(app)
            self.panel_app.layout()
            self.screen.draw()
   
        app_root = get_app_root(app)
        if not os.path.exists(f'{app_root}/app.sh'):
            self.panel_screen.components = [ self.panel_apps ]
            self.layout_apps()
            self.screen.layout()

        app_manifest = None
        if os.path.exists(f'{app_root}/app.json'):
            try:
                with open(f'{app_root}/app.json', 'r') as f:
                    app_manifest = json.loads(f.read(), cls = JSONWithCommentsDecoder)
            except Exception as e:
                pass

        app_name = app_manifest.get('name') if app_manifest else app
        app_description = app_manifest.get('description') if app_manifest else ''
        app_version = app_manifest.get('version') if app_manifest else ''
        app_enabled = is_app_enabled(app) == '1'
        app_status = get_app_status(app)
        app_properties = app_manifest.get('properties', []) if app_manifest else []

        self.panel_app.app_title.text = ellipsis(app_name, 24)
        self.panel_app.app_refresh.callback = lambda app=app: refresh_app(app)
        self.panel_app.app_version.text = f'Version: {app_version}'
        self.panel_app.app_path.text = ellipsis(app_root, 40)
        self.panel_app.app_description.text = '\n'.join(i for i in wrap(app_description, 48))
        self.panel_app.app_size.text = '-'
        self.panel_app.app_memory.text = '-'
        self.panel_app.app_cpu.text = '-'
        self.panel_app.app_enable.text = 'Disable app' if app_enabled else 'Enable app'
        self.panel_app.app_enable.callback = lambda app=app: toggle_app(app)

        if True:
            self.panel_app.app_settings.visible = False

        self.panel_app.app_qr_code.visible = False

        qr_properties = [ p for p in app_properties if app_properties[p]['type'] == 'qr' ]
        if qr_properties:
             qr_property = qr_properties[0]
             display = app_properties[qr_property].get('display')
             content = get_app_property(app, qr_property)
             if content:
                self.panel_app.app_qr_code.visible = True
                self.panel_app.app_qr_code.callback = lambda content=content: self.show_qr_dialog(content, display)

        self.panel_app.app_enable.right = 8 + (56 if self.panel_app.app_qr_code.visible else 0) + (56 if self.panel_app.app_settings.visible else 0)
        self.panel_app.app_settings.right = 8 + (56 if self.panel_app.app_qr_code.visible else 0)

        # self.panel_app.app_settings = app_settings
        # self.panel_app.app_qr_code = app_qr_code
        # self.panel_app.app_enable = app_enable
        # self.panel_app.app_start = app_start
        
        self.panel_screen.layout()

        def update_app_size(result):
            self.panel_app.app_size.text = result
            with self.screen.draw_lock:
                self.panel_app.layout()
            self.screen.draw()
        if USING_SHELL:
            shell_async(f"du -sh {app_root} | awk '{{print $1}}'", update_app_size)
            
        def update_memory():
            app_pids = get_app_pids(app)
            if not app_pids:
                return
            
            app_pids = app_pids.split(' ')
            app_memory = 0
            app_cpu = 0

            for pid in app_pids:
                p = psutil.Process(int(pid))
                app_memory += p.memory_info().rss / 1024 / 1024

            self.panel_app.app_memory.text = f'{round(app_memory, 1)}M'
            with self.screen.draw_lock:
                self.panel_app.layout()
            self.screen.draw()

            for pid in app_pids:
                p = psutil.Process(int(pid))
                app_cpu += p.cpu_percent(interval=1)

            self.panel_app.app_cpu.text = f'{round(app_cpu, 1)}%'
            with self.screen.draw_lock:
                self.panel_app.layout()
            self.screen.draw()
        run_async(update_memory)

        if app_status == 'stopped':
            self.panel_app.app_start.visible = True
            self.panel_app.app_start.text = 'Start app'
            self.panel_app.app_start.text_color = COLOR_TEXT
            self.panel_app.app_start.callback = lambda app=app: _start_app(app)
        else:
            self.panel_app.app_start.visible = True
            self.panel_app.app_start.text = 'Stop app'
            self.panel_app.app_start.text_color = COLOR_DANGER
            self.panel_app.app_start.callback = lambda app=app: _stop_app(app)
    def layout_ota(self):
        def cancel_ota():
            if not USING_SIMULATOR:
                if os.path.exists('/useremain/update.swu'):
                    os.remove('/useremain/update.swu')

            self.panel_ota.visible = False
            time.sleep(0.25)
            
            self.screen.layout()
            self.screen.draw()

        #self.panel_ota.ota_latest_firmware.text = '-'
        self.panel_ota.ota_latest_rinkhals.text = '-'
        self.panel_ota.ota_progress_panel.visible = False
        self.panel_ota.ota_progress_bar.width = 0
        self.panel_ota.ota_progress_text.text = '0%'
        self.panel_ota.ota_action.text = 'Refresh'
        self.panel_ota.ota_action.callback = lambda: run_async(check_rinkhals_update)
        self.panel_ota.ota_action.disabled = False
        self.panel_ota.ota_cancel.disabled = False
        self.panel_ota.ota_cancel.callback = cancel_ota
        self.panel_ota.visible = True

        self.screen.layout()
        self.screen.draw()

        def install_rinkhals_update():
            self.panel_ota.ota_action.disabled = True
            self.panel_ota.ota_cancel.disabled = True
            self.panel_ota.ota_progress_text.text = 'Extracting...'
            with self.screen.draw_lock:
                self.panel_ota.layout()
            self.screen.draw()

            if KOBRA_MODEL_CODE == 'K2P' or KOBRA_MODEL_CODE == 'K3':
                password = 'U2FsdGVkX19deTfqpXHZnB5GeyQ/dtlbHjkUnwgCi+w='
            elif KOBRA_MODEL_CODE == 'KS1':
                password = 'U2FsdGVkX1+lG6cHmshPLI/LaQr9cZCjA8HZt6Y8qmbB7riY'

            logging.info(f'Extracting Rinkhals update...')

            for i in range(1):
                if not USING_SIMULATOR:
                    if os.system('rm -rf /useremain/update_swu') != 0:
                        break
                    if os.system(f'unzip -P {password} /useremain/update.swu -d /useremain') != 0:
                        break
                    if os.system('rm /useremain/update.swu') != 0:
                        break
                    if os.system('tar zxf /useremain/update_swu/setup.tar.gz -C /useremain/update_swu') != 0:
                        break
                    if os.system('chmod +x /useremain/update_swu/update.sh') != 0:
                        break
                else:
                    time.sleep(1)

                self.panel_ota.ota_progress_text.text = 'Installing...'
                with self.screen.draw_lock:
                    self.panel_ota.layout()
                self.screen.draw()

                # TODO: Replace reboot by something we control (like start.sh maybe?)

                if not USING_SIMULATOR:
                    logging.info('Starting Rinkhals update...')
                    os.system('/useremain/update_swu/update.sh &')
                else:
                    time.sleep(1)
                    self.quit()
                return
            
            self.panel_ota.ota_progress_bar.background_color = COLOR_DANGER
            self.panel_ota.ota_progress_text.text = 'Extraction failed'
            self.panel_ota.ota_action.disabled = False
            self.panel_ota.ota_cancel.disabled = False
            
            with self.screen.draw_lock:
                self.panel_ota.layout()
            self.screen.draw()

        def download_rinkhals_update():
            self.panel_ota.ota_action.disabled = True
            self.panel_ota.ota_progress_panel.visible = True
            self.panel_ota.ota_progress_bar.background_color = COLOR_PRIMARY
            self.panel_ota.ota_progress_bar.width = 0
            self.panel_ota.ota_progress_text.text = 'Starting...'
            with self.screen.draw_lock:
                self.panel_ota.layout()

            target_path = f'{RINKHALS_ROOT}/../../build/dist/update-download.swu' if USING_SIMULATOR else '/useremain/update.swu'

            try:
                logging.info(f'Downloading Rinkhals {self.panel_ota.latest_version} from {self.panel_ota.latest_release_url}...')

                with requests.get(self.panel_ota.latest_release_url, stream=True) as r:
                    r.raise_for_status()
                    with open(target_path, 'wb') as f:
                        total_length = int(r.headers.get('content-length', 0))
                        downloaded = 0
                        last_update_time = 0

                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk:
                                if not self.panel_ota.visible:
                                    logging.info('Download canceled.')
                                    return
                                
                                f.write(chunk)
                                downloaded += len(chunk)
                                progress = int(downloaded / total_length * 100)

                                current_time = time.time()
                                if current_time - last_update_time >= 0.75:
                                    last_update_time = current_time

                                    self.panel_ota.ota_progress_bar.width = int(192 * progress / 100)
                                    downloaded_mb = downloaded / (1024 * 1024)
                                    total_mb = total_length / (1024 * 1024)
                                    self.panel_ota.ota_progress_text.text = f'{progress}% ({downloaded_mb:.1f}M / {total_mb:.1f}M)'

                                    with self.screen.draw_lock:
                                        self.panel_ota.layout()
                                    self.screen.draw()

                logging.info('Download completed.')

                self.panel_ota.ota_progress_bar.width = 192
                self.panel_ota.ota_progress_text.text = 'Ready to install'

                self.panel_ota.ota_action.text = 'Install'
                self.panel_ota.ota_action.callback = lambda: run_async(install_rinkhals_update)
            except Exception as e:
                logging.info(f'Download failed. {e}')

                self.panel_ota.ota_progress_bar.background_color = COLOR_DANGER
                self.panel_ota.ota_progress_text.text = 'Failed'
                
            self.panel_ota.ota_action.disabled = False

            with self.screen.draw_lock:
                self.panel_ota.layout()
            self.screen.draw()

        def check_rinkhals_update():
            self.panel_ota.latest_release = None
            self.panel_ota.latest_version = None
            self.panel_ota.latest_release_url = None
            
            try:
                logging.info('Checking latest Rinkhals update...')
                response = requests.get('https://api.github.com/repos/jbatonnet/Rinkhals/releases/latest')

                if response.status_code == 200:
                    self.panel_ota.latest_release = response.json()
                    self.panel_ota.latest_version = self.panel_ota.latest_release.get('tag_name')

                    assets = self.panel_ota.latest_release.get('assets', [])
                    for asset in assets:
                        if (KOBRA_MODEL_CODE == 'K2P' or KOBRA_MODEL_CODE == 'K3') and asset['name'] == 'update-k2p-k3.swu':
                            self.panel_ota.latest_release_url = asset['browser_download_url']
                        elif KOBRA_MODEL_CODE == 'KS1' and asset['name'] == 'update-ks1.swu':
                            self.panel_ota.latest_release_url = asset['browser_download_url']

                    logging.info(f'Found update {self.panel_ota.latest_version} from {self.panel_ota.latest_release_url}')
                else:
                    logging.error(f'Failed to fetch latest release: {response.status_code}')
            except Exception as e:
                logging.error(f'Error checking Rinkhals update: {e}')

            if self.panel_ota.latest_version and self.panel_ota.latest_release_url:
                self.panel_ota.ota_latest_rinkhals.text = ellipsis(self.panel_ota.latest_version, 16)
                self.panel_ota.ota_action.text = 'Download' if self.panel_ota.latest_version != RINKHALS_VERSION else 'Refresh'
                self.panel_ota.ota_action.callback = lambda: run_async(download_rinkhals_update) if self.panel_ota.latest_version != RINKHALS_VERSION else lambda: run_async(check_rinkhals_update)
            else:
                self.panel_ota.ota_latest_rinkhals.text = '-'
                self.panel_ota.ota_action.text = 'Refresh'
                self.panel_ota.ota_action.callback = lambda: run_async(check_rinkhals_update)

            with self.screen.draw_lock:
                self.panel_ota.layout()
            self.screen.draw()

        run_async(check_rinkhals_update)

    def set_screen_panel(self, panel):
        self.panel_screen.components = [ panel ]

        if panel == self.panel_main: self.layout_main()
        if panel == self.panel_apps: self.layout_apps()

        self.panel_screen.layout()
    def show_text_dialog(self, text, action='OK', action_color=None, callback=None):
        def button_callback():
            self.panel_dialog.visible = False
            self.screen.layout()
            self.screen.draw()

            if callback:
                callback()
        
        self.panel_dialog.dialog_text.visible = True
        self.panel_dialog.dialog_text.text = text
        self.panel_dialog.dialog_qr.visible = False
        self.panel_dialog.dialog_button.text = action
        self.panel_dialog.dialog_button.text_color = action_color
        self.panel_dialog.dialog_button.callback = button_callback

        self.panel_dialog.visible = True
        self.screen.layout()
        self.screen.draw()
    def show_qr_dialog(self, content, text=None):
        def button_callback():
            self.panel_dialog.visible = False
            self.screen.layout()
            self.screen.draw()
        
        self.panel_dialog.dialog_qr.visible = True
        self.panel_dialog.dialog_qr.image = qrcode.make(content, border=2, box_size=8).convert('RGBA')
        self.panel_dialog.dialog_text.visible = not not text
        self.panel_dialog.dialog_text.text = text
        self.panel_dialog.dialog_button.text = 'OK'
        self.panel_dialog.dialog_button.text_color = COLOR_TEXT
        self.panel_dialog.dialog_button.callback = button_callback

        self.panel_dialog.visible = True
        self.screen.layout()
        self.screen.draw()

    def reboot_printer(self):
        logging.info('Rebooting printer...')

        if not USING_SIMULATOR:
            self.clear()
            os.system('sync && reboot')
        else:
            self.quit()
    def restart_rinkhals(self):
        logging.info('Restarting Rinkhals...')

        if not USING_SIMULATOR:
            self.clear()
            os.system(RINKHALS_ROOT + '/start.sh')

        self.quit()
    def stop_rinkhals(self):
        logging.info('Stopping Rinkhals...')

        if not USING_SIMULATOR:
            self.clear()
            os.system(RINKHALS_ROOT + '/stop.sh')

        self.quit()
    def disable_rinkhals(self):
        logging.info('Disabling Rinkhals...')

        if not USING_SIMULATOR:
            self.clear()
            with open('/useremain/rinkhals/.disable-rinkhals', 'wb'):
                pass
            os.system('reboot')

        self.quit()

    def clear(self):
        if not USING_SIMULATOR:
            os.system(f'dd if=/dev/zero of=/dev/fb0 bs={self.screen.width * 4} count={self.screen.height}')
    def run(self):
        while True:
            lv.tick_inc(16)
            lv.timer_handler()
            time.sleep(0.016)
    def quit(self):
        logging.info('Exiting Rinkhals UI...')
        time.sleep(0.25)
        os.kill(os.getpid(), 9)


if __name__ == "__main__":
    if USING_SIMULATOR:
        program = Program()
        program.run()
    else:
        try:
            program = Program()
            program.run()
        except:
            frames = sys._current_frames()
            threads = {}
            for thread in threading.enumerate():
                threads[thread.ident] = thread
            for thread_id, stack in frames.items():
                if thread_id == threading.main_thread().ident:
                    print(traceback.format_exc())
                elif thread_id in threads:
                    print(f'-- Thread {thread_id}: {threads[thread_id]} --')
                    print(' '.join(traceback.format_list(traceback.extract_stack(stack))))
            
    print('', flush=True)
    os.kill(os.getpid(), 9)
