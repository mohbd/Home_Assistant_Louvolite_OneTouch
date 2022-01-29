# Custom Component for Louvolite One Touch Integration on Home Assistant

Crudely customized fork of https://github.com/mtgeekman/Home_Assistant_NeoSmartBlinds/releases for use with k2 motors and a Louvolite hub. This repository is intended only as a way to keep track of my changes to this component for use within my HA environment.

Removed the ability to set position and tilt position as the implementation was not usable for k2 motors. Favourite positions are not supported with these motors, but it is possible to move up and down between a number of set limits inside of the start and end positions. This functionality is available in HA with the open/close cover tilt buttons.

## Supported features

**Open**
Up

**Close**
Down

**Tilt-Up**
Next Limit Up

**Tilt-Down**
Next Limit Down
