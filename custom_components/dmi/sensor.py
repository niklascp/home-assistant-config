"""
Sensor for data from Danish Metrology Institute (DMI).

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.dmi/
"""
import asyncio
import logging

from random import randrange
from datetime import datetime

import voluptuous as vol

from homeassistant.components.weather import (
    ATTR_WEATHER_HUMIDITY, ATTR_WEATHER_PRESSURE, ATTR_WEATHER_TEMPERATURE,
    ATTR_WEATHER_WIND_BEARING, ATTR_WEATHER_WIND_SPEED)
from homeassistant.const import (
    CONF_NAME, CONF_MONITORED_CONDITIONS, ATTR_ATTRIBUTION,
    DEVICE_CLASS_HUMIDITY, DEVICE_CLASS_TEMPERATURE, DEVICE_CLASS_PRESSURE,
    TEMP_CELSIUS)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import (async_track_utc_time_change,
                                         async_call_later)

_LOGGER = logging.getLogger(__name__)

ATTR_LOCATION = 'location'
ATTR_UPDATED = 'updated'
ATTRIBUTION = "Data provided by DMI"

CONF_LOCATION_ID = 'location_id'
CONF_FORECASTS = 'forecasts'

DEFAULT_NAME = 'DMI'

SENSOR_TYPES = {
    ATTR_WEATHER_TEMPERATURE: [
        'Temperature', TEMP_CELSIUS, DEVICE_CLASS_TEMPERATURE,
        'temp', '{:.1f}'],
    ATTR_WEATHER_WIND_SPEED: [
        'Wind speed', 'm/s', None, 'windSpeed', '{:.0f}'],
    'wind_gust': [
        'Wind gust', 'm/s', None, 'windGust', '{:.0f}'],
    ATTR_WEATHER_PRESSURE: [
        'Pressure', 'hPa', DEVICE_CLASS_PRESSURE, 'pressure', '{:.0f}'],
    ATTR_WEATHER_WIND_BEARING: [
        'Wind direction', '°', None, 'windDegree', '{:.0f}'],
    ATTR_WEATHER_HUMIDITY: [
        'Humidity', '%', DEVICE_CLASS_HUMIDITY, 'humidity', '{:.0f}'],
    'precipitation': [
        'Precipitation', 'mm', None, 'precip1', '{:.1f}']
}

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend({
    vol.Required(
        CONF_MONITORED_CONDITIONS,
        default=[ATTR_WEATHER_TEMPERATURE]):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Required(CONF_LOCATION_ID): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_FORECASTS, default=[0]):
        vol.All(cv.ensure_list, [vol.In(range(23))]),
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the DMI sensor."""
    location_id = config.get(CONF_LOCATION_ID)
    name = config.get(CONF_NAME)

    sensor_entities = [
        DmiSensor(location_id, name, forecast, sensor_type)
        for forecast in config[CONF_FORECASTS]
        for sensor_type in config[CONF_MONITORED_CONDITIONS]
    ]
    async_add_entities(sensor_entities)

    data = DmiData(hass, location_id, sensor_entities)
    async_track_utc_time_change(hass, data.fetch_data,
                                minute="/5", second=0)
    await data.fetch_data()


class DmiSensor(Entity):
    """Representation of an DMI sensor."""

    def __init__(self, location_id, name, forecast, sensor_type):
        """Initialize the sensor."""
        self._unique_id = "dmi.{}.{}".format(location_id, sensor_type)
        self._name = '{} {}'.format(name, SENSOR_TYPES[sensor_type][0])

        if forecast > 0:
            self._unique_id = "{}.forecast_{}".format(
                self._unique_id, forecast)
            self._name = '{} ({}H)'.format(self._name, forecast)

        self._forecast = forecast
        self._type = sensor_type
        self._state = None
        self._location_name = None
        self._last_update = None
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self._device_class = SENSOR_TYPES[sensor_type][2]

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_LOCATION: self._location_name,
            ATTR_UPDATED: self._last_update,
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def device_class(self):
        """Return the device class."""
        return self._device_class


class DmiData:
    """The class for handling the data retrieval."""

    def __init__(self, hass, location_id, sensor_entities):
        """Initialize the probe."""
        self.hass = hass
        self.location_id = location_id
        self.sensor_entities = sensor_entities

        self.last_update = None
        self.location_city = None
        self.data = {}

    async def fetch_data(self, *_):
        """Get the latest data from DMI."""
        try:
            import dmiapi
            client = dmiapi.DmiApiClient()
            _LOGGER.debug("Fetching data")
            self.data = await client.async_forecasts(self.location_id)
            self.last_update = datetime.strptime(
                self.data.get('lastupdate'), '%Y%m%d%H%M%S')
            self.location_city = self.data.get('city')
        except Exception as err:
            # Retry in 0 to 5 minutes.
            minutes = randrange(6)
            _LOGGER.error("Retrying in %i minutes: %s", minutes, err)
            async_call_later(self.hass, minutes*60, self.fetch_data)
            return

        await self.update_states()

    async def update_states(self, *_):
        """Update enties with current data from self.data."""
        tasks = []

        for sensor_entity in self.sensor_entities:
             # pylint: disable=protected-access
            if sensor_entity._last_update != self.last_update:
                forecast = self.data['forecasts'][sensor_entity._forecast]
                sensor_type = SENSOR_TYPES[sensor_entity._type]
                value = forecast[sensor_type[3]]
                if value != None:
                    sensor_entity._state = sensor_type[4].format(value)
                else:
                    sensor_entity._state = None
                sensor_entity._location_name = self.location_city
                sensor_entity._last_update = self.last_update

                tasks.append(sensor_entity.async_update_ha_state())

        if tasks:
            await asyncio.wait(tasks, loop=self.hass.loop)
