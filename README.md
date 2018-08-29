### Introduction

emf_hub_mon will display who is currently transmitting on the "EMF Hub", an Amateur Radio hub that connects several digital and analogue systems together in one place.

This app is designed for the EMF Camp Tilda v3 Badge that was issued in 2016. Due to resource limitations it may not function after EMF 2018.

More information on the EMF Hub is available at http://hub.emfhams.org

#### Installation

If you're not installing this app via the badge app store, plug the badge into a PC via USB where it will appear as USB Storage. You can then copy the contents of this repo/directory to apps/emf_hub_mon and restart the badge. The app should then appear in the menu

**note:** Always safely eject / unmount the file system. The badges are prone to corrupting if they are power cycled whilst mounted.

#### Configuration

It's possible to tweak the behaviour of the badge by editing the emf_hub_mon.json file in this directory.

* **mqtt_server:** FQDN of MQTT Broker. Must be listening on 1883!
* **mqtt_topic:** MQTT Topic to subscribe to
* **green_led:** Enable Green (B) LED on Tx (true/false)
* **torch_led:** Enable Torch LED on Tx (true/false)
* **neopixel:**  Enable Neopixel on Tx (true/false)
* **neo_colour:** Configure colour of Neopixel. Should be a list of [R, G, B], e.g [0, 100, 0],
* **idle_timeout:** Time in seconds to display Tx status until return
* **debug:** Enables printing debug logs to serial (true / false)
* **first_boot:** The app will show some information on first boot, then toggle this value so it doesn't reappear (true/false)
* **demo:** Force first_boot = true, always

#### Contributing

This app has been produced as a "reference" - Pull Requests or changes are welcome and encouraged