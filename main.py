### Category: Comms
### Author: Marrold - 2E0SIP
### License: MIT
### Appname: emf_hub_mon
### Description: Show who's talking on the EMF Hub

import ugfx
import buttons
import wifi
import mqtt
import json
import ubinascii
import pyb
import machine
import onboard
import dialogs
import database


class mon_display():
    def __init__(self, config, status, led):

        self.__config = config
        self.__debug = self.__config.get('debug')
        self.__idle_timeout = self.__config.get('idle_timeout') * 1000

        self.__status = status
        self.__led = led

        self.__pending_idle = False
        self.__next_idle = 0
        self.__lh_call = ""
        self.__lh_name = ""

    # Attempts to centre text horizontally. As the font is not monospaced, its a bit dodgy - Fix Me!
    def __text_centre(self, text, size, color, y):

        if size == ugfx.FONT_TITLE:
            font_size = 13
        elif size == ugfx.FONT_MEDIUM_BOLD:
            font_size = 9
        elif size == ugfx.FONT_MEDIUM:
            font_size = 8
        else:
            font_size = 7

        ugfx.set_default_font(size)
        x = int((ugfx.width() - (len(text) * font_size)) / 2)
        ugfx.text(x, y, text, color)

    # Writes last heard on display if available
    def __display_lh(self, lh_call, lh_name):

        if lh_call:

            if lh_name == "":
                lh_name = "unknown"

            LH = "LH: %s (%s)" % (lh_call, lh_name)

            if len(LH) <= 22:
                font_size = ugfx.FONT_TITLE
            elif len(LH) <= 32:
                font_size = ugfx.FONT_MEDIUM_BOLD
            else:
                font_size = ugfx.FONT_SMALL

            self.__text_centre(LH, font_size, ugfx.GREY, 210)

    def draw_background(self, colour):

        logo = 'apps/emf_hub_mon/emf_hub_mon.gif'

        ugfx.area(0, 0, ugfx.width(), ugfx.height(), colour)
        ugfx.area(0, 0, ugfx.width(), 25, ugfx.GREY)

        ugfx.display_image(10, 30, logo)

    # Alias for display_idle()
    def init(self):

        self.display_idle()

    # Draw the idle display
    def display_idle(self, lh_call="", lh_name=""):

        if self.__debug:
            print("emf_hub_mon: Drawing Idle Screen")

        self.__pending_idle = False

        ugfx.backlight(40)
        self.draw_background(ugfx.html_color(0xf7f4f4))
        ugfx.set_default_font(ugfx.FONT_TITLE)

        self.__text_centre("IDLE", ugfx.FONT_TITLE, ugfx.GREY, 120)
        self.__display_lh(lh_call, lh_name)
        self.__led.off()

    # Reset the display to idle if required
    def update(self):

        if self.__debug:
            print("emf_hub_mon: Checking if display needs to return to idle")

        if self.__pending_idle and pyb.millis() > self.__next_idle:
            self.display_idle(self.__lh_call, self.__lh_name)

        # Update the status bar if required
        self.__status.update()

    # Schedule the display to return to idle
    def idle(self, lh_call="", lh_name=""):

        if self.__debug:
            print("emf_hub_mon: Scheduling display to return to idle in %d ms" % self.__idle_timeout)

        self.__lh_call = lh_call
        self.__lh_name = lh_name

        self.__pending_idle = True
        self.__next_idle = pyb.millis() + self.__idle_timeout

    # Draw the TX display
    def tx(self, call, name):

        if self.__debug:
            print("emf_hub_mon: Drawing the Tx display")

        ugfx.backlight(100)

        self.draw_background(ugfx.html_color(0xaefcbd))

        ugfx.set_default_font(ugfx.FONT_TITLE)

        self.__text_centre(call, ugfx.FONT_TITLE, ugfx.BLACK, 110)
        self.__text_centre(name, ugfx.FONT_MEDIUM_BOLD, ugfx.BLACK, 140)

        self.__led.on()

    def welcome(self):

        exit_welcome = pyb.millis() + 30000

        if self.__debug:
            print("emf_hub_mon: Drawing the welcome display")

        self.draw_background(ugfx.WHITE)

        self.__text_centre("Shows who is transmitting on the", ugfx.FONT_MEDIUM, ugfx.BLACK, 115)
        self.__text_centre("\"EMF HUB\", a hub for amateur radio!", ugfx.FONT_MEDIUM, ugfx.BLACK, 135)

        self.__text_centre("Press A or B to continue", ugfx.FONT_MEDIUM, ugfx.BLACK, 220)

        while pyb.millis() < exit_welcome:

            self.__status.update()

            if buttons.is_triggered('BTN_A') or buttons.is_triggered('BTN_B'):
                print("emf_hub_mon: Button pressed - exiting welcome screen")
                break

        self.draw_background(ugfx.WHITE)

        ugfx.set_default_font(ugfx.FONT_MEDIUM)
        ugfx.text(20, 115, "More Info: http://hub.emfhams.org", ugfx.BLACK)
        ugfx.text(60, 155, "Brought to you by:", ugfx.BLACK)
        ugfx.text(15, 175, "2E0SIP, MM0MRU and the EMF Hams", ugfx.BLACK)

        self.__text_centre("Press A or B to continue", ugfx.FONT_MEDIUM, ugfx.BLACK, 220)

        exit_welcome = pyb.millis() + 30000

        while pyb.millis() < exit_welcome:

            self.__status.update()

            if buttons.is_triggered('BTN_A') or buttons.is_triggered('BTN_B'):
                print("emf_hub_mon: Button pressed - exiting welcome screen")
                break

        if not self.__config.get('demo'):
            print("emf_hub_mon: Setting first_boot false")
            self.__config.set('first_boot', False)
            self.__config.flush()
        else:
            print("emf_hub_mon: Demo mode, skipping setting first_boot")


class mqtt_handler():
    def __init__(self, config, display):

        self.__debug = config.get('debug')
        self.__display = display
        self.__server = config.get('mqtt_server')
        self.__topic = "emf_hub/ptt"
        self._id = str(ubinascii.hexlify(pyb.unique_id()), 'ascii')
        self.__next_ping = pyb.millis() + 60000

        self.__c = mqtt.MQTTClient(self._id, self.__server)

        # Connect to server
        self.__connect()

    def handle(self):

        # Check for messages
        try:
            self.__check_msg()
        except:
            pass

        # Ping if required
        self.__ping()

    # Ping the broker and reconnect if it fails
    def __ping(self):

        if pyb.millis() > self.__next_ping:

            if self.__debug:
                print("emf_hub_mon: Pinging MQTT Broker")

            self.__next_ping = pyb.millis() + 60000

            try:
                self.__c.sock.send(b"\xc0\0")  # ping
            except:
                print("emf_hub_mon: Reconnecting to MQTT")
                self.__connect(reconnect=True)

    # Connect to the broker
    def __connect_mqtt(self):
        try:
            print("emf_hub_mon: Connecting to MQTT Broker")
            self.__c.connect()
        except OSError:
            pyb.delay(200)
            self.__connect_mqtt()
            return
        self.__c.set_callback(self.__callback)
        print("emf_hub_mon: Subscribing to %s" % self.__topic)
        self.__c.subscribe(self.__topic)

    # Disconnect from the broker
    def __disconnect_mqtt(self):

        print("emf_hub_mon: Disconnecting from MQTT Broker")

        if self.__c:
            try:
                self.__c.disconnect()
            except:
                pass

    # Connect to the Wifi and MQTT Broker
    def __connect(self, reconnect=False):

        self.__display.draw_background(ugfx.WHITE)

        ugfx.set_default_font(ugfx.FONT_SMALL)
        ugfx.text(10, 120, "Connecting to Wifi...", ugfx.BLACK)
        print("emf_hub_mon: Connecting to Wifi")

        if reconnect:
            self.__disconnect_mqtt()
            wifi.nic().disconnect()
        while not wifi.is_connected():
            try:
                wifi.connect(wait=True, timeout=15)
            except:
                pyb.delay(200)

        ugfx.set_default_font(ugfx.FONT_SMALL)
        ugfx.text(10, 140, "Connecting to MQTT...", ugfx.BLACK)
        self.__connect_mqtt()
        pyb.delay(1000)

    # Check the buffer for new messages
    def __check_msg(self):

        if self.__debug:
            print("emf_hub_mon: Checking MQTT buffer for new messages")

        self.__c.check_msg()

    # Handle new messages
    def __callback(self, topic, msg):

        # If debug is enabled print the message to serial
        if self.__debug:
            print("emf_hub_mon: Message received - %s" % msg.decode("utf-8"))

        # Decode the json payload
        data = json.loads(msg)

        # If this is a key event, draw the Tx display
        if data['type'] == "key":

            if self.__debug:
                print("emf_hub_mon: Received key event")

            self.__display.tx(data['call'], data['nick'])

        # If this is an unkey event, schedule the idle display
        elif data['type'] == "unkey":

            if self.__debug:
                print("emf_hub_mon: Received unkey event")

            self.__display.idle(data['call'], data['nick'])


class status_bar():
    def __init__(self, config):

        # Get the config
        self.__debug = config.get('debug')

        # Configure the style and layout
        ugfx.set_default_font(ugfx.FONT_MEDIUM)
        ugfx.set_default_style(dialogs.default_style_badge)
        self.__sty_tb = ugfx.Style(dialogs.default_style_badge)
        self.__sty_tb.set_enabled([ugfx.WHITE, ugfx.html_color(0xA66FB0), ugfx.html_color(0x5e5e5e), ugfx.RED])
        self.__sty_tb.set_background(ugfx.GREY)
        self.__win_bv = ugfx.Container(0, 0, 80, 25, style=self.__sty_tb)
        self.__win_wifi = ugfx.Container(82, 0, 60, 25, style=self.__sty_tb)
        self.__win_clock = ugfx.Container(250, 0, 70, 25, style=self.__sty_tb)
        self.__win_wifi.show()
        self.__win_bv.show()
        self.__win_clock.show()

        # Init var for last RSSI
        self.__last_rssi = 0

        # Schedule next status update
        self.__next_status_update = pyb.millis() + 500

    # Draw the battery sttus
    def __draw_battery(self, back_colour, percent, win_bv):
        percent = max(0, percent)
        ugfx.set_default_font("c*")
        main_c = ugfx.WHITE
        x = 3
        y = 3
        win_bv.area(x + 35, y, 40, 19, back_colour)
        if percent <= 120:
            win_bv.text(x + 35, y, str(int(min(percent, 100))), main_c)
        y += 2
        win_bv.area(x, y, 30, 11, main_c)
        win_bv.area(x + 30, y + 3, 3, 5, main_c)

        if percent > 120:
            win_bv.area(x + 2, y + 2, 26, 7, ugfx.YELLOW)
        elif percent > 2:
            win_bv.area(x + 2, y + 2, 26, 7, ugfx.GREY)
            win_bv.area(x + 2, y + 2, int(min(percent, 100) * 26 / 100), 7, main_c)
        else:
            win_bv.area(x + 2, y + 2, 26, 7, ugfx.RED)

    # Drae the WiFi status
    def __draw_wifi(self, back_colour, rssi, connected, connecting, win_wifi):
        x = int((rssi + 100) / 14)
        x = min(5, x)
        x = max(1, x)
        y = x * 4
        x = x * 5

        outline = [[0, 20], [25, 20], [25, 0]]
        outline_rssi = [[0, 20], [x, 20], [x, 20 - y]]

        if connected:
            win_wifi.fill_polygon(0, 0, outline, ugfx.html_color(0xC4C4C4))
            win_wifi.fill_polygon(0, 0, outline_rssi, ugfx.WHITE)
        elif connecting:
            win_wifi.fill_polygon(0, 0, outline, ugfx.YELLOW)
        else:
            win_wifi.fill_polygon(0, 0, outline, ugfx.RED)

    # Draw the clock
    def __draw_time(self, bg_colour, datetime, win_clock):

        win_clock.area(0, 0, win_clock.width(), win_clock.height(), bg_colour)

        digit_width = 9
        right_padding = 5
        time_text = "%02d:%02d" % (datetime[4], datetime[5])
        start_x = win_clock.width() - (digit_width * len(time_text)) - right_padding
        start_y = 5
        win_clock.text(start_x, start_y, time_text, ugfx.WHITE)

    # Update wifi status
    def __update_wifi(self):

        ugfx.set_default_font("c*")

        try:
            rssi = wifi.nic().get_rssi()
        except:
            rssi = 0

        if rssi == 0:
            rssi = self.__last_rssi
        else:
            self.__last_rssi = rssi

        wifi_is_connected = wifi.nic().is_connected()
        wifi_timeout = 1
        self.__draw_wifi(self.__sty_tb.background(), rssi, wifi_is_connected, wifi_timeout > 0, self.__win_wifi)

    # Update battery status
    def __update_battery(self):

        battery_percent = onboard.get_battery_percentage()
        self.__draw_battery(self.__sty_tb.background(), battery_percent, self.__win_bv)

    # Update clock
    def __update_clock(self):

        self.__draw_time(self.__sty_tb.background(), pyb.RTC().datetime(), self.__win_clock)

    # Update all status bar elements
    def update(self):

        if pyb.millis() > self.__next_status_update:

            if self.__debug:
                print("emf_hub_mon: Updating Status Bar")
            self.__update_battery()
            self.__update_wifi()
            self.__update_clock()

            self.__next_status_update = pyb.millis() + 500


class led:
    def __init__(self, config):

        # If green LED is enabled, configure it
        if config.get('green_led'):
            self.__green = pyb.LED(2)
        else:
            self.__green = None

        # If torch LED is enabled, configure it
        if config.get('torch_led'):
            self.__torch = pyb.Pin("LED_TORCH")
        else:
            self.__torch = None

        # If Neopixel is enabled, configure it
        if config.get('neopixel'):
            self.__neo_colour = self.__build_neo_colour(config)
            self.__neo = pyb.Neopix(machine.Pin("PB13", machine.Pin.OUT))
        else:
            self.__neo = None

    # Builds Neopixel colour from list
    def __build_neo_colour(self, config):

        neo_list = config.get('neo_colour')
        colour = (neo_list[0] << 16) | (neo_list[1] << 8) | neo_list[2]

        return colour

    # Switch green (B) LED on
    def __green_on(self):

        self.__green.on()

    # Switch green (B) LED off
    def __green_off(self):

        self.__green.off()

    # Switch torch LED on
    def __torch_on(self):

        self.__torch.high()

    # Switch torch LED off
    def __torch_off(self):

        self.__torch.low()

    # Switch Neopixel on
    def __neo_on(self):

        self.__neo.display(self.__neo_colour)

    # Switch Neopixel off
    def __neo_off(self):

        self.__neo.display(0x000000)

    # Switch all enabled LEDs on
    def on(self):

        if self.__green:
            self.__green_on()

        if self.__torch:
            self.__torch_on()

        if self.__neo:
            self.__neo_on()

    # Switch all enabled LEDs off
    def off(self):

        if self.__green:
            self.__green_off()

        if self.__torch:
            self.__torch_off()

        if self.__neo:
            self.__neo_off()


def main():
    print("emf_hub_mon: Starting emf_hub_mon")

    # Init GFX and Buttons
    ugfx.init()
    buttons.init()

    # Config
    config = database.Database(filename='apps/emf_hub_mon/emf_hub_mon.json')

    # Status bar service
    status_service = status_bar(config)

    # LED service
    led_service = led(config)

    # Display service
    mon_service = mon_display(config, status_service, led_service)

    # Display welcome screen on first boot
    if config.get('first_boot'):
        mon_service.welcome()

    # MQTT service
    mqtt_service = mqtt_handler(config, mon_service)

    # Initialise the monitor display
    mon_service.init()

    while True:
        # Handle MQTT operations
        mqtt_service.handle()

        # Handle Display operations
        mon_service.update()

        # Give the CPU a break
        pyb.delay(200)

    # clean up some stuff, not sure if this is required but w/e
    ugfx.clear()
    led_service.off()


if __name__ == "__main__":
    main()
