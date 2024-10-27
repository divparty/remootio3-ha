"""Support for by a Remootio device controlled garage door or gate."""
from __future__ import annotations

import logging

from aioremootio import Event, EventType, Listener, RemootioClient, State, StateChange

from homeassistant.components import cover
from homeassistant.components.cover import CoverEntity, CoverEntityFeature, CoverDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, ATTR_NAME, CONF_DEVICE_CLASS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_SERIAL_NUMBER, CONF_SERIAL_NUMBER, DOMAIN, REMOOTIO_CLIENT

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up an RemootioCover entity based on the given configuration entry."""

    _LOGGER.debug(
        "Doing async_setup_entry. config_entry [%s] hass.data[%s][%s] [%s]",
        config_entry.as_dict(),
        DOMAIN,
        config_entry.entry_id,
        hass.data[DOMAIN][config_entry.entry_id],
    )

    serial_number: str = config_entry.data[CONF_SERIAL_NUMBER]
    device_class: CoverDeviceClass = config_entry.data[CONF_DEVICE_CLASS]
    remootio_client: RemootioClient = hass.data[DOMAIN][config_entry.entry_id][
        REMOOTIO_CLIENT
    ]

    async_add_entities(
        [
            RemootioCover(
                serial_number, config_entry.title, device_class, remootio_client
            )
        ]
    )


class RemootioCover(CoverEntity):
    """Cover entity which represents an Remootio device controlled garage door or gate."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE

    def __init__(
        self,
        unique_id: str,
        name: str,
        device_class: CoverDeviceClass,
        remootio_client: RemootioClient,
    ) -> None:
        """Initialize this cover entity."""
        self._attr_unique_id = unique_id
        self._attr_device_class = device_class
        self._remootio_client = remootio_client
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=name,
            manufacturer="Assemblabs Ltd",
            model="Remootio 3",
            sw_version=str(remootio_client.api_version),
        )

    async def async_added_to_hass(self) -> None:
        """Register listeners to the used Remootio client to be notified on state changes and events."""
        await self._remootio_client.add_state_change_listener(
            RemootioCoverStateChangeListener(self)
        )
        await self._remootio_client.add_event_listener(RemootioCoverEventListener(self))
        await self.async_update()

    async def async_update(self) -> None:
        """Trigger state update of the used Remootio client."""
        await self._remootio_client.trigger_state_update()

    @property
    def is_opening(self) -> bool:
        """Return True when the Remootio controlled garage door or gate is currently opening."""
        return self._remootio_client.state == State.OPENING

    @property
    def is_closing(self) -> bool:
        """Return True when the Remootio controlled garage door or gate is currently closing."""
        return self._remootio_client.state == State.CLOSING

    @property
    def is_closed(self) -> bool | None:
        """Return True when the Remootio controlled garage door or gate is currently closed."""
        if self._remootio_client.state == State.NO_SENSOR_INSTALLED:
            return None
        return self._remootio_client.state == State.CLOSED

    async def async_open_cover(self, **kwargs) -> None:
        """Open the Remootio controlled garage door or gate."""
        await self._remootio_client.trigger_open()

    async def async_close_cover(self, **kwargs) -> None:
        """Close the Remootio controlled garage door or gate."""
        await self._remootio_client.trigger_close()


class RemootioCoverStateChangeListener(Listener[StateChange]):
    """Listener to be invoked when Remootio controlled garage door or gate changes its state."""

    def __init__(self, owner: RemootioCover) -> None:
        """Initialize an instance of this class."""
        super().__init__()
        self._owner = owner

    async def execute(self, client: RemootioClient, subject: StateChange) -> None:
        """Execute this listener. Tell Home Assistant that the Remootio controlled garage door or gate has changed its state."""
        self._owner.async_write_ha_state()


class RemootioCoverEventListener(Listener[Event]):
    """Listener to be invoked on an event sent by the Remmotio device."""

    def __init__(self, owner: RemootioCover) -> None:
        """Initialize an instance of this class."""
        super().__init__()
        self._owner = owner

    async def execute(self, client: RemootioClient, subject: Event) -> None:
        """Execute this listener. Fire events in Home Assistant based on events sent by the Remootio device."""
        if subject.type == EventType.LEFT_OPEN:
            event_type = f"{DOMAIN.lower()}_{subject.type.name.lower()}"
            self._owner.hass.bus.async_fire(
                event_type,
                {
                    ATTR_ENTITY_ID: self._owner.entity_id,
                    ATTR_SERIAL_NUMBER: self._owner.unique_id,
                    ATTR_NAME: self._owner.name,
                },
            )