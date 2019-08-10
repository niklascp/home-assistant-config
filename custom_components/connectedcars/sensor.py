"""Support for ConnectedCars sensors."""
import logging

#from homeassistant.consts import VOLUME_LITERS
from homeassistant.util import dt
from homeassistant.const import LENGTH_KILOMETERS, VOLUME_LITERS

from . import (DOMAIN, ATTR_UPDATED, ConnectedCarsEntity)

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the ConnectedCars platform."""

    # We only want this platform to be set up via discovery.
    if discovery_info is None:
        return

    sensors = []
    data = hass.data[DOMAIN]

    sensors.extend([
        ConnectedCarsFuelLevel(vehicle_overview)
        for vehicle_overview in data.overview])

    sensors.extend([
        ConnectedCarsOdometer(vehicle_overview)
        for vehicle_overview in data.overview])

    async_add_entities(sensors)

class ConnectedCarsFuelLevel(ConnectedCarsEntity):
    """Representation of a ConnectedCars fuel level."""

    def __init__(self, _vehicle_data):
        """Initialize the sensor."""
        super().__init__(_vehicle_data, "Fuel Level", "fuel_level")

    @property
    def state(self):
        """Return the state of the device."""
        return self._vehicle_data.fuelLevel.liter

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_UPDATED: dt.as_local(self._vehicle_data.fuelLevel.time)
        }

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return VOLUME_LITERS 

class ConnectedCarsOdometer(ConnectedCarsEntity):
    """Representation of a ConnectedCars odometer."""

    def __init__(self, _vehicle_data):
        """Initialize the sensor."""
        super().__init__(_vehicle_data, "Odometer", "odometer")

    @property
    def state(self):
        """Return the state of the device."""
        return self._vehicle_data.odometer.odometer

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_UPDATED: dt.as_local(self._vehicle_data.odometer.time)
        }

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return LENGTH_KILOMETERS
