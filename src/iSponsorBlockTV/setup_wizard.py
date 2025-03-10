import asyncio
import copy

import aiohttp

# Textual imports (Textual is awesome!)
from textual import on
from textual.app import App, ComposeResult
from textual.containers import (
    Container,
    Grid,
    Horizontal,
    ScrollableContainer,
    Vertical,
)
from textual.events import Click
from textual.screen import Screen
from textual.validation import Function
from textual.widgets import (
    Button,
    Checkbox,
    ContentSwitcher,
    Footer,
    Header,
    Input,
    Label,
    RadioButton,
    RadioSet,
    SelectionList,
    Static,
)
from textual.widgets.selection_list import Selection
from textual_slider import Slider

# Local imports
from . import api_helpers, ytlounge
from .constants import skip_categories


def _validate_pairing_code(pairing_code: str) -> bool:
    try:
        pairing_code = pairing_code.replace("-", "").replace(" ", "")
        int(pairing_code)
        return len(pairing_code) == 12
    except ValueError:
        return False  # not a number


class ModalWithClickExit(Screen):
    """A modal screen that exits when clicked outside its bounds.
    https://discord.com/channels/1026214085173461072/1033754296224841768/1136015817356611604
    """

    DEFAULT_CSS = """
    ModalWithClickExit {
        align: center middle;
        layout: vertical;
        overflow-y: auto;
        background: $background 60%;
    }
    """

    @on(Click)
    def close_out_bounds(self, event: Click) -> None:
        if self.get_widget_at(event.screen_x, event.screen_y)[0] is self:
            self.dismiss()


class Element(Static):
    """Base class for elements (devices and channels).
    It has a name and a remove button.
    """

    def __init__(self, element: dict, tooltip: str = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.element_data = element
        self.element_name = ""
        self.process_values_from_data()
        self.tooltip = tooltip

    def process_values_from_data(self):
        raise NotImplementedError("Subclasses must implement this method.")

    def compose(self) -> ComposeResult:
        yield Button(
            label=self.element_name,
            classes="element-name button-small",
            disabled=True,
            id="element-name",
        )
        yield Button(
            "Remove",
            classes="element-remove button-small",
            variant="error",
            id="element-remove",
        )

    def on_mount(self) -> None:
        if self.tooltip:
            self.query_one(".element-name").tooltip = self.tooltip
            self.query_one(".element-name").disabled = False


class Device(Element):
    """A device element."""

    def process_values_from_data(self):
        if "name" in self.element_data and self.element_data["name"]:
            self.element_name = self.element_data["name"]
        else:
            self.element_name = (
                "Unnamed device with id "
                f"{self.element_data['screen_id'][:5]}..."
                f"{self.element_data['screen_id'][-5:]}"
            )


class Channel(Element):
    """A channel element."""

    def process_values_from_data(self):
        if "name" in self.element_data:
            self.element_name = self.element_data["name"]
        else:
            self.element_name = (
                f"Unnamed channel with id {self.element_data['channel_id']}"
            )


class ChannelRadio(RadioButton):
    """A radio button for a channel."""

    def __init__(self, channel: tuple, **kwargs) -> None:
        label = f"{channel[1]} - Subs: {channel[2]}"
        super().__init__(label=label, **kwargs)
        self.channel_data = channel


class MigrationScreen(ModalWithClickExit):
    """Screen with a dialog to remove old ATVS config."""

    BINDINGS = [
        ("escape", "dismiss()", "Cancel"),
        ("s", "remove_and_save", "Remove and save"),
        ("q,ctrl+c", "exit", "Exit"),
    ]
    AUTO_FOCUS = "#exit-save"

    def compose(self) -> ComposeResult:
        yield Grid(
            Label(
                (
                    "Welcome to the new configurator! You seem to have the legacy"
                    " 'atvs' entry on your config file, do you want to remove it?\n(The"
                    " app won't start with it present)"
                ),
                id="question",
                classes="button-100",
            ),
            Button(
                "Remove and save",
                variant="primary",
                id="migrate-remove-save",
                classes="button-100",
            ),
            Button(
                "Don't remove",
                variant="error",
                id="migrate-no-change",
                classes="button-100",
            ),
            id="dialog-migration",
        )

    def action_exit(self) -> None:
        self.app.exit()

    @on(Button.Pressed, "#migrate-no-change")
    def action_no_change(self) -> None:
        self.app.pop_screen()

    @on(Button.Pressed, "#migrate-remove-save")
    def action_remove_and_save(self) -> None:
        del self.app.config.atvs
        self.app.config.save()
        self.app.pop_screen()


class ExitScreen(ModalWithClickExit):
    """Screen with a dialog to exit."""

    BINDINGS = [
        ("escape", "dismiss()", "Cancel"),
        ("s", "save", "Save"),
        ("q,ctrl+c", "exit", "Exit"),
    ]
    AUTO_FOCUS = "#exit-save"

    def compose(self) -> ComposeResult:
        yield Grid(
            Label(
                "Are you sure you want to exit without saving?",
                id="question",
                classes="button-100",
            ),
            Button("Save", variant="success", id="exit-save", classes="button-100"),
            Button(
                "Don't save", variant="error", id="exit-no-save", classes="button-100"
            ),
            Button("Cancel", variant="primary", id="exit-cancel", classes="button-100"),
            id="dialog-exit",
        )

    def action_exit(self) -> None:
        self.app.exit()

    def action_save(self) -> None:
        self.app.config.save()
        self.app.exit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "exit-no-save":
            self.app.exit()
        elif event.button.id == "exit-save":
            self.app.config.save()
            self.app.exit()
        else:
            self.app.pop_screen()


class AddDevice(ModalWithClickExit):
    """Screen with a dialog to add a device, either with a pairing code
    or with lan discovery."""

    BINDINGS = [("escape", "dismiss({})", "Return")]

    def __init__(self, config, **kwargs) -> None:
        super().__init__(**kwargs)
        self.config = config
        self.web_session = aiohttp.ClientSession()
        self.api_helper = api_helpers.ApiHelper(config, self.web_session)
        self.devices_discovered_dial = []

    def compose(self) -> ComposeResult:
        with Container(id="add-device-container"):
            yield Label("Add Device", classes="title")
            with Grid(id="add-device-switch-buttons"):
                yield Button(
                    "Add with pairing code",
                    id="add-device-pin-button",
                    classes="button-switcher",
                )
                yield Button(
                    "Add with lan discovery",
                    id="add-device-dial-button",
                    classes="button-switcher",
                )
            with ContentSwitcher(
                id="add-device-switcher", initial="add-device-pin-container"
            ):
                with Container(id="add-device-pin-container"):
                    yield Input(
                        placeholder=(
                            "Pairing Code (found in Settings - Link with TV code)"
                        ),
                        id="pairing-code-input",
                        validators=[
                            Function(
                                _validate_pairing_code, "Invalid pairing code format"
                            )
                        ],
                    )
                    yield Input(
                        placeholder="Device Name (auto filled if empty/optional)",
                        id="device-name-input",
                    )
                    yield Button(
                        "Add",
                        id="add-device-pin-add-button",
                        variant="success",
                        disabled=True,
                    )
                    yield Label(id="add-device-info")
                with Container(id="add-device-dial-container"):
                    yield Label(
                        (
                            "Make sure your device is on the same network as this"
                            " computer\nIf it isn't showing up, try restarting the"
                            " app.\nIf running in docker, make sure to use"
                            " `--network=host`\nTo refresh the list, close and open the"
                            " dialog again\n[b][u]If it still doesn't work, "
                            "pair using a pairing code (it's much more reliable)"
                        ),
                        classes="subtitle",
                    )
                    yield SelectionList(
                        ("Searching for devices...", "", False),
                        id="dial-devices-list",
                        disabled=True,
                    )
                    yield Button(
                        "Add selected devices",
                        id="add-device-dial-add-button",
                        variant="success",
                        disabled=True,
                    )

    async def on_mount(self) -> None:
        self.devices_discovered_dial = []
        asyncio.create_task(self.task_discover_devices())

    async def task_discover_devices(self):
        devices_found = await self.api_helper.discover_youtube_devices_dial()
        list_widget: SelectionList = self.query_one("#dial-devices-list")
        list_widget.clear_options()
        if devices_found:
            # print(devices_found)
            devices_found_parsed = []
            for index, i in enumerate(devices_found):
                devices_found_parsed.append(Selection(i["name"], index, False))
            list_widget.add_options(devices_found_parsed)
            self.query_one("#dial-devices-list").disabled = False
            self.devices_discovered_dial = devices_found
        else:
            list_widget.add_option(("No devices found", "", False))

    @on(Button.Pressed, "#add-device-switch-buttons > *")
    def handle_switch_buttons(self, event: Button.Pressed) -> None:
        self.query_one("#add-device-switcher").current = event.button.id.replace(
            "-button", "-container"
        )

    @on(Input.Changed, "#pairing-code-input")
    def changed_pairing_code(self, event: Input.Changed):
        self.query_one(
            "#add-device-pin-add-button"
        ).disabled = not event.validation_result.is_valid

    @on(Input.Submitted, "#pairing-code-input")
    @on(Button.Pressed, "#add-device-pin-add-button")
    async def handle_add_device_pin(self) -> None:
        self.query_one("#add-device-pin-add-button").disabled = True
        lounge_controller = ytlounge.YtLoungeApi(
            "iSponsorBlockTV",
        )
        await lounge_controller.change_web_session(self.web_session)
        pairing_code = self.query_one("#pairing-code-input").value
        pairing_code = int(
            pairing_code.replace("-", "").replace(" ", "")
        )  # remove dashes and spaces
        device_name = self.parent.query_one("#device-name-input").value
        paired = False
        try:
            paired = await lounge_controller.pair(pairing_code)
        except BaseException:
            pass
        if paired:
            device = {
                "screen_id": lounge_controller.auth.screen_id,
                "name": device_name if device_name else lounge_controller.screen_name,
                "offset": 0,
            }
            self.query_one("#pairing-code-input").value = ""
            self.query_one("#device-name-input").value = ""
            self.query_one("#add-device-info").update(
                f"[#00ff00][b]Successfully added {device['name']}"
            )
            self.dismiss([device])
        else:
            self.query_one("#pairing-code-input").value = ""
            self.query_one("#add-device-pin-add-button").disabled = False
            self.query_one("#add-device-info").update("[#ff0000]Failed to add device")

    @on(Button.Pressed, "#add-device-dial-add-button")
    def handle_add_device_dial(self) -> None:
        list_widget: SelectionList = self.query_one("#dial-devices-list")
        selected_devices = list_widget.selected
        devices = []
        for i in selected_devices:
            devices.append(self.devices_discovered_dial[i])
        self.dismiss(devices)

    @on(SelectionList.SelectedChanged, "#dial-devices-list")
    def changed_device_list(self, event: SelectionList.SelectedChanged):
        self.query_one(
            "#add-device-dial-add-button"
        ).disabled = not event.selection_list.selected


class AddChannel(ModalWithClickExit):
    """Screen with a dialog to add a channel,
    either using search or with a channel id."""

    BINDINGS = [("escape", "dismiss(())", "Return")]

    def __init__(self, config, **kwargs) -> None:
        super().__init__(**kwargs)
        self.config = config
        web_session = aiohttp.ClientSession()
        self.api_helper = api_helpers.ApiHelper(config, web_session)

    def compose(self) -> ComposeResult:
        with Container(id="add-channel-container"):
            yield Label("Add Channel", classes="title")
            yield Label(
                (
                    "Select a method to add a channel. Adding via search only works if"
                    " a YouTube api key has been set"
                ),
                id="add-channel-label",
                classes="subtitle",
            )
            with Grid(id="add-channel-switch-buttons"):
                yield Button(
                    "Add by channel name",
                    id="add-channel-search-button",
                    classes="button-switcher",
                )
                yield Button(
                    "Add by channel ID",
                    id="add-channel-id-button",
                    classes="button-switcher",
                )
            yield Label(id="add-channel-info", classes="subtitle")
            with ContentSwitcher(
                id="add-channel-switcher", initial="add-channel-search-container"
            ):
                with Vertical(id="add-channel-search-container"):
                    if self.config.apikey:
                        with Grid(id="add-channel-search-inputs"):
                            yield Input(
                                placeholder="Enter channel name",
                                id="channel-name-input-search",
                            )
                            yield Button(
                                "Search", id="search-channel-button", variant="success"
                            )
                        yield RadioSet(
                            RadioButton(label="Search to see results", disabled=True),
                            id="channel-search-results",
                        )
                        yield Button(
                            "Add",
                            id="add-channel-button-search",
                            variant="success",
                            disabled=True,
                            classes="button-100",
                        )
                    else:
                        yield Label(
                            (
                                "[#ff0000]No api key set, cannot search for channels."
                                " You can add it the config section below"
                            ),
                            id="add-channel-search-no-key",
                            classes="subtitle",
                        )
                with Vertical(id="add-channel-id-container"):
                    yield Input(
                        placeholder=(
                            "Enter channel ID (example: UCuAXFkgsw1L7xaCfnd5JJOw)"
                        ),
                        id="channel-id-input",
                    )
                    yield Input(
                        placeholder=(
                            "Enter channel name (only used to display in the config"
                            " file)"
                        ),
                        id="channel-name-input-id",
                    )
                    yield Button(
                        "Add",
                        id="add-channel-button-id",
                        variant="success",
                        classes="button-100",
                    )

    @on(RadioSet.Changed, "#channel-search-results")
    def handle_radio_set_changed(self, event: RadioSet.Changed) -> None:
        self.query_one("#add-channel-button-search").disabled = False

    @on(Button.Pressed, "#add-channel-switch-buttons > *")
    def handle_switch_buttons(self, event: Button.Pressed) -> None:
        self.query_one("#add-channel-switcher").current = event.button.id.replace(
            "-button", "-container"
        )

    @on(Button.Pressed, "#search-channel-button")
    @on(Input.Submitted, "#channel-name-input-search")
    async def handle_search_channel(self) -> None:
        channel_name = self.query_one("#channel-name-input-search").value
        if not channel_name:
            self.query_one("#add-channel-info").update(
                "[#ff0000]Please enter a channel name"
            )
            return
        self.query_one("#search-channel-button").disabled = True
        self.query_one("#add-channel-info").update("Searching...")
        self.query_one("#add-channel-button-search").disabled = True
        self.query_one("#channel-search-results").remove_children()
        try:
            channels_list = await self.api_helper.search_channels(channel_name)
        except BaseException:
            self.query_one("#add-channel-info").update(
                "[#ff0000]Failed to search for channel"
            )
            self.query_one("#search-channel-button").disabled = False
            return
        for i in channels_list:
            self.query_one("#channel-search-results").mount(ChannelRadio(i))
        if channels_list:
            self.query_one("#search-channel-button").disabled = False
        self.query_one("#add-channel-info").update("")

    @on(Button.Pressed, "#add-channel-button-search")
    def handle_add_channel_search(self) -> None:
        channel = self.query_one("#channel-search-results").pressed_button.channel_data
        if not channel:
            self.query_one("#add-channel-info").update(
                "[#ff0000]Please select a channel"
            )
            return
        self.query_one("#add-channel-info").update("Adding...")
        self.dismiss(channel)

    @on(Button.Pressed, "#add-channel-button-id")
    @on(Input.Submitted, "#channel-id-input")
    @on(Input.Submitted, "#channel-name-input-id")
    def handle_add_channel_id(self) -> None:
        channel_id = self.query_one("#channel-id-input").value
        channel_name = self.query_one("#channel-name-input-id").value
        if not channel_id:
            self.query_one("#add-channel-info").update(
                "[#ff0000]Please enter a channel ID"
            )
            return
        if not channel_name:
            channel_name = channel_id
        channel = (channel_id, channel_name, "hidden")
        self.query_one("#add-channel-info").update("Adding...")
        self.dismiss(channel)


class EditDevice(ModalWithClickExit):
    """Screen with a dialog to edit a device. Used by the DevicesManager."""

    BINDINGS = [("escape", "close_screen_saving", "Return")]

    def __init__(self, device: Element, **kwargs) -> None:
        super().__init__(**kwargs)
        self.device_data = device.element_data
        self.device_widget = device

    def action_close_screen_saving(self) -> None:
        self.dismiss()

    def dismiss(self, _=None) -> None:
        self.device_data["name"] = self.query_one("#device-name-input").value
        self.device_data["screen_id"] = self.query_one("#device-id-input").value
        self.device_data["offset"] = int(self.query_one("#device-offset-input").value)
        super().dismiss(self.device_widget)

    def compose(self) -> ComposeResult:
        name = self.device_data.get("name", "")
        offset = self.device_data.get("offset", 0)
        with Container(id="edit-device-container"):
            yield Label("Edit device (ESCAPE to exit)", classes="title")
            yield Label("Device name")
            yield Input(placeholder="Device name", id="device-name-input", value=name)
            yield Label("Device screen id")
            with Grid(id="device-id-container"):
                yield Input(
                    placeholder="Device id",
                    id="device-id-input",
                    value=self.device_data["screen_id"],
                    password=True,
                )
                yield Button("Show id", id="device-id-view")
            yield Label("Device offset (in milliseconds)")
            with Horizontal(id="device-offset-container"):
                yield Input(id="device-offset-input", value=str(offset))
                yield Slider(
                    name="Device offset",
                    id="device-offset-slider",
                    min=0,
                    max=2000,
                    step=100,
                    value=offset,
                )

    def on_slider_changed(self, event: Slider.Changed) -> None:
        offset_input = self.query_one("#device-offset-input")
        with offset_input.prevent(Input.Changed):
            offset_input.value = str(event.slider.value)

    def on_input_changed(self, event: Input.Changed):
        if event.input.id == "device-offset-input":
            value = event.input.value
            if value.isdigit():
                value = int(value)
                slider = self.query_one("#device-offset-slider")
                with slider.prevent(Slider.Changed):
                    self.query_one("#device-offset-slider").value = value

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "device-id-view":
            if "Show" in event.button.label:
                event.button.label = "Hide id"
                self.query_one("#device-id-input").password = False
            else:
                event.button.label = "Show id"
                self.query_one("#device-id-input").password = True


class DevicesManager(Vertical):
    """Manager for devices, allows adding, edit and removing devices."""

    def __init__(self, config, **kwargs) -> None:
        super().__init__(**kwargs)
        self.config = config
        self.devices = config.devices

    def compose(self) -> ComposeResult:
        yield Label("Devices", classes="title")
        with Horizontal(id="add-device-button-container"):
            yield Button(
                "Add Device", id="add-device", classes="button-100 button-small"
            )
        for device in self.devices:
            yield Device(device, tooltip="Click to edit")

    def new_devices(self, device_data) -> None:
        if device_data:
            device_widget = None
            for i in device_data:
                self.devices.append(i)
                device_widget = Device(i, tooltip="Click to edit")
                self.mount(device_widget)
            device_widget.focus(scroll_visible=True)

    @staticmethod
    def edit_device(device_widget: Element) -> None:
        device_widget.process_values_from_data()
        device_widget.query_one("#element-name").label = device_widget.element_name

    @on(Button.Pressed, "#element-remove")
    def remove_channel(self, event: Button.Pressed):
        channel_to_remove: Element = event.button.parent
        self.config.devices.remove(channel_to_remove.element_data)
        channel_to_remove.remove()

    @on(Button.Pressed, "#add-device")
    def add_device(self, event: Button.Pressed):
        self.app.push_screen(AddDevice(self.config), callback=self.new_devices)

    @on(Button.Pressed, "#element-name")
    def edit_channel(self, event: Button.Pressed):
        channel_to_edit: Element = event.button.parent
        self.app.push_screen(EditDevice(channel_to_edit), callback=self.edit_device)


class ApiKeyManager(Vertical):
    """Manager for the YouTube Api Key."""

    def __init__(self, config, **kwargs) -> None:
        super().__init__(**kwargs)
        self.config = config

    def compose(self) -> ComposeResult:
        yield Label("YouTube Api Key", classes="title")
        yield Label(
            "You can get a YouTube Data API v3 Key from the"
            " [link=https://console.developers.google.com/apis/credentials]Google Cloud"
            " Console[/link]. This key is only required if you're whitelisting"
            " channels."
        )
        with Grid(id="api-key-grid"):
            yield Input(
                placeholder="YouTube Api Key",
                id="api-key-input",
                password=True,
                value=self.config.apikey,
            )
            yield Button("Show key", id="api-key-view")

    @on(Input.Changed, "#api-key-input")
    def changed_api_key(self, event: Input.Changed):
        self.config.apikey = event.input.value

    @on(Button.Pressed, "#api-key-view")
    def pressed_api_key_view(self, event: Button.Pressed):
        if "Show" in event.button.label:
            event.button.label = "Hide key"
            self.query_one("#api-key-input").password = False
        else:
            event.button.label = "Show key"
            self.query_one("#api-key-input").password = True


class SkipCategoriesManager(Vertical):
    """Manager for skip categories, allows selecting which categories to skip."""

    def __init__(self, config, **kwargs) -> None:
        super().__init__(**kwargs)
        self.config = config

    def compose(self) -> ComposeResult:
        yield Label("Skip Categories", classes="title")
        yield Label("Select the categories you want to skip", classes="subtitle")
        skip_categories_parsed = []
        for i in skip_categories:
            name, value = i
            if value in self.config.skip_categories:
                skip_categories_parsed.append((name, value, True))
            else:
                skip_categories_parsed.append((name, value, False))
        # print(skip_categories_parsed)
        yield SelectionList(*skip_categories_parsed, id="skip-categories-compact-list")

    @on(SelectionList.SelectedChanged, "#skip-categories-compact-list")
    def changed_skip_categories(self, event: SelectionList.SelectedChanged):
        self.config.skip_categories = event.selection_list.selected


class SkipCountTrackingManager(Vertical):
    """Manager for skip count tracking, allows to enable/disable skip count tracking."""

    def __init__(self, config, **kwargs) -> None:
        super().__init__(**kwargs)
        self.config = config

    def compose(self) -> ComposeResult:
        yield Label("Skip count tracking", classes="title")
        yield Label(
            (
                "This feature tracks which segments you have skipped to let users know"
                " how much their submission has helped others and used as a metric"
                " along with upvotes to ensure that spam doesn't get into the database."
                " The program sends a message to the sponsor block server each time you"
                " skip a segment. Hopefully most people don't change this setting so"
                " that the view numbers are accurate. :)"
            ),
            classes="subtitle",
            id="skip-count-tracking-subtitle",
        )
        yield Checkbox(
            value=self.config.skip_count_tracking,
            id="skip-count-tracking-switch",
            label="Enable skip count tracking",
        )

    @on(Checkbox.Changed, "#skip-count-tracking-switch")
    def changed_skip_tracking(self, event: Checkbox.Changed):
        self.config.skip_count_tracking = event.checkbox.value


class AdSkipMuteManager(Vertical):
    """Manager for ad skip/mute, allows to enable/disable ad skip/mute."""

    def __init__(self, config, **kwargs) -> None:
        super().__init__(**kwargs)
        self.config = config

    def compose(self) -> ComposeResult:
        yield Label("Skip/Mute ads", classes="title")
        yield Label(
            (
                "This feature allows you to automatically mute and/or skip native"
                " YouTube ads. Skipping ads only works if that ad shows the 'Skip Ad'"
                " button, if it doesn't then it will only be able to be muted."
            ),
            classes="subtitle",
            id="skip-count-tracking-subtitle",
        )
        with Horizontal(id="ad-skip-mute-container"):
            yield Checkbox(
                value=self.config.skip_ads,
                id="skip-ads-switch",
                label="Enable skipping ads",
            )
            yield Checkbox(
                value=self.config.mute_ads,
                id="mute-ads-switch",
                label="Enable muting ads",
            )

    @on(Checkbox.Changed, "#mute-ads-switch")
    def changed_mute(self, event: Checkbox.Changed):
        self.config.mute_ads = event.checkbox.value

    @on(Checkbox.Changed, "#skip-ads-switch")
    def changed_skip(self, event: Checkbox.Changed):
        self.config.skip_ads = event.checkbox.value


class ChannelWhitelistManager(Vertical):
    """Manager for channel whitelist,
    allows adding/removing channels from the whitelist."""

    def __init__(self, config, **kwargs) -> None:
        super().__init__(**kwargs)
        self.config = config

    def compose(self) -> ComposeResult:
        yield Label("Channel Whitelist", classes="title")
        yield Label(
            (
                "This feature allows to whitelist channels from being skipped. This"
                " feature is automatically disabled when no channels have been"
                " specified."
            ),
            classes="subtitle",
            id="channel-whitelist-subtitle",
        )
        yield Label(
            (
                ":warning: [#FF0000]You need to set your YouTube Api Key in order to"
                " use this feature"
            ),
            id="warning-no-key",
        )
        with Horizontal(id="add-channel-button-container"):
            yield Button(
                "Add Channel", id="add-channel", classes="button-100 button-small"
            )
        for channel in self.config.channel_whitelist:
            yield Channel(channel)

    def on_mount(self) -> None:
        self.app.query_one("#warning-no-key").display = (
            not self.config.apikey
        ) and bool(self.config.channel_whitelist)

    def new_channel(self, channel: tuple) -> None:
        if channel:
            channel_dict = {
                "id": channel[0],
                "name": channel[1],
            }
            self.config.channel_whitelist.append(channel_dict)
            channel_widget = Channel(channel_dict)
            self.mount(channel_widget)
            channel_widget.focus(scroll_visible=True)
            self.app.query_one("#warning-no-key").display = (
                not self.config.apikey
            ) and bool(self.config.channel_whitelist)

    @on(Button.Pressed, "#element-remove")
    def remove_channel(self, event: Button.Pressed):
        channel_to_remove: Element = event.button.parent
        self.config.channel_whitelist.remove(channel_to_remove.element_data)
        channel_to_remove.remove()
        self.app.query_one("#warning-no-key").display = (
            not self.config.apikey
        ) and bool(self.config.channel_whitelist)

    @on(Button.Pressed, "#add-channel")
    def add_channel(self, event: Button.Pressed):
        self.app.push_screen(AddChannel(self.config), callback=self.new_channel)


class AutoPlayManager(Vertical):
    """Manager for autoplay, allows enabling/disabling autoplay."""

    def __init__(self, config, **kwargs) -> None:
        super().__init__(**kwargs)
        self.config = config

    def compose(self) -> ComposeResult:
        yield Label("Autoplay", classes="title")
        yield Label(
            "This feature allows you to enable/disable autoplay",
            classes="subtitle",
            id="autoplay-subtitle",
        )
        with Horizontal(id="autoplay-container"):
            yield Checkbox(
                value=self.config.auto_play,
                id="autoplay-switch",
                label="Enable autoplay",
            )

    @on(Checkbox.Changed, "#autoplay-switch")
    def changed_skip(self, event: Checkbox.Changed):
        self.config.auto_play = event.checkbox.value


class ISponsorBlockTVSetupMainScreen(Screen):
    TITLE = "iSponsorBlockTV"
    SUB_TITLE = "Setup Wizard"
    BINDINGS = [("q,ctrl+c", "exit_modal", "Exit"), ("s", "save", "Save")]
    AUTO_FOCUS = None

    def __init__(self, config, **kwargs) -> None:
        super().__init__(**kwargs)
        self.dark = True
        self.config = config
        self.initial_config = copy.deepcopy(config)

    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()
        with ScrollableContainer(id="setup-wizard"):
            yield DevicesManager(
                config=self.config, id="devices-manager", classes="container"
            )
            yield SkipCategoriesManager(
                config=self.config, id="skip-categories-manager", classes="container"
            )
            yield SkipCountTrackingManager(
                config=self.config, id="count-segments-manager", classes="container"
            )
            yield AdSkipMuteManager(
                config=self.config, id="ad-skip-mute-manager", classes="container"
            )
            yield ChannelWhitelistManager(
                config=self.config, id="channel-whitelist-manager", classes="container"
            )
            yield ApiKeyManager(
                config=self.config, id="api-key-manager", classes="container"
            )
            yield AutoPlayManager(
                config=self.config, id="autoplay-manager", classes="container"
            )

    def on_mount(self) -> None:
        if self.check_for_old_config_entries():
            self.app.push_screen(MigrationScreen())

    def action_save(self) -> None:
        self.config.save()
        self.initial_config = copy.deepcopy(self.config)

    def action_exit_modal(self) -> None:
        if self.config != self.initial_config:
            self.app.push_screen(ExitScreen())
        else:  # No changes were made
            self.app.exit()

    def check_for_old_config_entries(self) -> bool:
        if hasattr(self.config, "atvs"):
            return True
        return False

    @on(Input.Changed, "#api-key-input")
    def changed_api_key(self, event: Input.Changed):
        try:  # ChannelWhitelist might not be mounted
            # Show if no api key is set and at least one channel is in the whitelist
            self.app.query_one("#warning-no-key").display = (
                not event.input.value
            ) and self.config.channel_whitelist
        except BaseException:
            pass


class ISponsorBlockTVSetup(App):
    CSS_PATH = (  # tcss is the recommended extension for textual css files
        "setup-wizard-style.tcss"
    )
    # Bindings for the whole app here, so they are available in all screens
    BINDINGS = [("q,ctrl+c", "exit_modal", "Exit"), ("s", "save", "Save")]

    def __init__(self, config, **kwargs) -> None:
        super().__init__(**kwargs)
        self.config = config
        self.main_screen = ISponsorBlockTVSetupMainScreen(config=self.config)

    def on_mount(self) -> None:
        self.push_screen(self.main_screen)

    def action_save(self) -> None:
        self.main_screen.action_save()

    def action_exit_modal(self) -> None:
        self.main_screen.action_exit_modal()


def main(config):
    app = ISponsorBlockTVSetup(config)
    app.run()
