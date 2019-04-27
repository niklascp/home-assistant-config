"""Support for the GPSLogger device tracking."""
import logging

from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util import dt

from . import DOMAIN, SIGNAL_UPDATE_VEHICLE_FORMAT, ATTR_UPDATED

_LOGGER = logging.getLogger(__name__)

async def async_setup_scanner(hass: HomeAssistantType, config,
                              async_see, discovery_info=None):

    # We only want this platform to be set up via discovery.
    if discovery_info is None:
        return

    # Configure a dispatcher connection based on a config entry.
    async def _update(vehicle_data):
        # Fire HA event to set location.
        await async_see(
            mac="{}.{}".format(DOMAIN, vehicle_data.id),
            dev_id="{} {}".format(vehicle_data.make, vehicle_data.model),
            gps=(vehicle_data.position.latitude, vehicle_data.position.longitude),
            attributes={
                ATTR_UPDATED: dt.as_local(vehicle_data.position.time)
            }
        )

    for vehicle_id, vehicle_data in hass.data[DOMAIN].vehicles.items():
        signal = SIGNAL_UPDATE_VEHICLE_FORMAT.format(DOMAIN, vehicle_id)
        async_dispatcher_connect(
            hass, signal, _update
        )
        await _update(vehicle_data)

    return True
