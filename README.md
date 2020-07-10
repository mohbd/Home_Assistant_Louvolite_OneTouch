# Custom Component for NeoSmartBlinds Integration on Home Assistant

The NeoSmartBlinds platform allows you to control a NeoSmartBlind / group of NeoSmartBlinds via a NeoSmartBlinds controller.

There is currently support for the following device types within Home Assistant:

-   Cover

## Installation

To begin with it is recommended you ensure your NeoSmartBlinds controller has a static IP addresses, you may need to configure this via your routers DHCP options.

1. Download the latest release from: https://github.com/mtgeekman/Home_Assistant_NeoSmartBlinds/releases
2. Extract the file
3. Copy the **neosmartblinds** folder to your **config/custom_components/** directory
4. Go to Config -> Server Controls -> Under "Server Management" click restart
5. Go to configuration example for how to setup your config.


# Cover Configuration 

### Example of basic configuration.yaml
```
cover:
  - platform: neosmartblinds
    name: Blind One
    host: 192.168.0.13
    hub_id: 000000000000000000000000
    protocol: http
    port: 8838
    blind_code: 021.230-04
    close_time: 65
```

## Configuration variables

cover:

**platform** (String)(Required) <br>
Must be set to neosmartblinds

**host** _(String)(Required)_<br>
The IP of the NeoSmartBlinds controller, e.g., 192.168.0.10.

**hub_id** _(String)(Required)_<br>
The 24 character device ID of the Smart Blinds Hub, found in the APP

**protocol** _(String)(Required)_<br>
The protocol to use for sending commands. (http, tcp)

**port** _(String)(Required)_<br>
Port use for the connection.  for TCP use 8839, for HTTP use 8838

**name** _(String)(Required)_<br>
The name you would like to give to the NeoSmartBlind.

**blind_code** _(String)(Required)_<br>
The blind code. - This is available from the NeoSmartBlind app

**close_time** _(String)(Required)_<br>
Time taken in seconds to close this blind (use a stop watch to measure)


## Supported features

**Open**
Up

**Close**
Down

**Tilt-Up**
Micro-Up

**Tilt-Down**
Micro-Down

**Set-Position & Favourite Position** - please note this is calculated using the close_time

   Setting the position: 
   
   **<= 49** will move the blind down, this means set position 25, moves the blind down and stops after 50% of your close_time
      
   **>=51** will move the blind up, this means set position 75, moves the blind up and stops after 50% of your close_time
   
   **==50** will set your blind to its stored favourite position 
