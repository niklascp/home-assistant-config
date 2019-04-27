"""Support for Verisure devices."""
import logging
import threading
from datetime import timedelta

import voluptuous as vol

from homeassistant.const import (CONF_PASSWORD, CONF_SCAN_INTERVAL,
                                 CONF_USERNAME)
from homeassistant.core import callback
from homeassistant.helpers import discovery, dispatcher
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_time_interval

# Home Assistant depends on 3rd party packages for API specific code.
REQUIREMENTS = ['connectedcars==0.1.0']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'connectedcars'
SIGNAL_UPDATE_VEHICLE_FORMAT = '{}_update_{}'

ATTR_UPDATED = 'updated'

MIN_SCAN_INTERVAL = timedelta(minutes=1)
DEFAULT_SCAN_INTERVAL = timedelta(minutes=1)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): (
            vol.All(cv.time_period, vol.Clamp(min=MIN_SCAN_INTERVAL))),
    }),
}, extra=vol.ALLOW_EXTRA)

async def async_setup(hass, config):
    """Set up the ConnectedCars component."""
    data = ConnectedCarsData(hass, config[DOMAIN])
    await data.async_update_overview()
    hass.data[DOMAIN] = data
    
    hass.async_create_task(
        discovery.async_load_platform(hass, 'sensor', DOMAIN, {}, config))
    hass.async_create_task(
        discovery.async_load_platform(hass, 'device_tracker', DOMAIN, {}, config))

    async def async_update(event_time):
        await data.async_update_overview()

    async_track_time_interval(hass, async_update, config[DOMAIN][CONF_SCAN_INTERVAL])

    return True

class ConnectedCarsData:
    """A ConnectedCars client wrapper class."""

    def __init__(self, hass, domain_config):
        import connectedcars        
        """Initialize the ConnectedCars hub."""
        self.hass = hass
        self.overview = None
        self.vehicles = {}
        self.config = domain_config
        self._connectedcars = connectedcars
        self.client = connectedcars.ConnectedCarsClient(
            domain_config[CONF_USERNAME],
            domain_config[CONF_PASSWORD])

    async def async_update_overview(self):
        """Update the overview."""
        try:
            _LOGGER.debug("Updating vehicles overview")
            self.overview = await self.client.async_vehicles_overview()
            for vehicle in self.overview:
                signal = SIGNAL_UPDATE_VEHICLE_FORMAT.format(DOMAIN, vehicle.id)
                self.vehicles[vehicle.id] = vehicle
                dispatcher.dispatcher_send(self.hass, signal, vehicle)
        except self._connectedcars.ConnectedCarsException as ex:
            _LOGGER.error('Could not read overview, %s', ex)
            raise

class ConnectedCarsEntity(Entity):
    """Representation of a ConnectedCars fuel level."""

    def __init__(self, vehicle_data, name, unique_id):
        """Initialize the sensor."""
        self._vehicle_id = vehicle_data.id
        self._vehicle_data = vehicle_data
        self._unique_id = "{}.{}.{}".format(DOMAIN, self._vehicle_id, unique_id)
        self._name = "{} {} {}".format(self._vehicle_data.make, self._vehicle_data.model, name)

    async def async_added_to_hass(self):
        """Call when entity is added to hass."""
        signal = SIGNAL_UPDATE_VEHICLE_FORMAT.format(DOMAIN, self._vehicle_id)
        dispatcher.async_dispatcher_connect(
            self.hass, signal, self.async_update_callback)

    @callback
    def async_update_callback(self, vehicle_data):
        """Update state."""        
        _LOGGER.debug("recived signal to update %s", self.entity_id)
        self._vehicle_data = vehicle_data
        self.async_schedule_update_ha_state(False)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def available(self):
        """Return True if entity is available."""
        return self._vehicle_data is not None

    @property
    def should_poll(self):
        return False
