"""Low-level ADB wrapper for Android device control."""

from typing import Optional
from PIL import Image
import io

from adbutils import AdbClient, AdbDevice


class AndroidController:
    """Wrapper around adbutils for controlling an Android device via ADB.
    
    Provides high-level methods for tapping, swiping, text input, and
    capturing screenshots from a connected Android device.
    """
    
    def __init__(self, serial: Optional[str] = None):
        """Initialize the Android controller.
        
        Args:
            serial: Optional device serial number. If None, auto-connects
                    to the first available device.
        
        Raises:
            RuntimeError: If no device is found.
        """
        self._client = AdbClient(host="127.0.0.1", port=5037)
        self._device: Optional[AdbDevice] = None
        self._connect(serial)
    
    def _connect(self, serial: Optional[str] = None) -> None:
        """Connect to an Android device via ADB.
        
        Args:
            serial: Optional device serial. If None, uses first available device.
        
        Raises:
            RuntimeError: If no device is found or connection fails.
        """
        devices = self._client.device_list()
        
        if not devices:
            raise RuntimeError(
                "No Android devices found. "
                "Ensure ADB is running and a device is connected."
            )
        
        if serial:
            for device in devices:
                if device.serial == serial:
                    self._device = device
                    break
            if not self._device:
                raise RuntimeError(f"Device with serial '{serial}' not found.")
        else:
            self._device = devices[0]
    
    @property
    def device(self) -> AdbDevice:
        """Get the connected ADB device."""
        if not self._device:
            raise RuntimeError("No device connected.")
        return self._device
    
    @property
    def serial(self) -> str:
        """Get the serial number of the connected device."""
        return self.device.serial
    
    def tap(self, x: int, y: int) -> str:
        """Simulate a finger tap at the specified coordinates.
        
        Args:
            x: X coordinate (0 = left edge).
            y: Y coordinate (0 = top edge).
        
        Returns:
            Status message confirming the tap.
        """
        self.device.shell(f"input tap {x} {y}")
        return f"Tapped at ({x}, {y})"
    
    def swipe(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        duration_ms: int = 300
    ) -> str:
        """Simulate a swipe gesture.
        
        Args:
            start_x: Starting X coordinate.
            start_y: Starting Y coordinate.
            end_x: Ending X coordinate.
            end_y: Ending Y coordinate.
            duration_ms: Duration of swipe in milliseconds.
        
        Returns:
            Status message confirming the swipe.
        """
        self.device.shell(
            f"input swipe {start_x} {start_y} {end_x} {end_y} {duration_ms}"
        )
        return f"Swiped from ({start_x}, {start_y}) to ({end_x}, {end_y})"
    
    def input_text(self, text: str) -> str:
        """Input text into the currently focused field.
        
        The text is sanitized to prevent shell injection issues.
        Spaces are converted to '%s' for ADB compatibility.
        
        Args:
            text: The text to input.
        
        Returns:
            Status message confirming the text input.
        """
        # Sanitize text for shell: escape special characters
        sanitized = text.replace("\\", "\\\\")
        sanitized = sanitized.replace('"', '\\"')
        sanitized = sanitized.replace("'", "\\'")
        sanitized = sanitized.replace("`", "\\`")
        sanitized = sanitized.replace("$", "\\$")
        sanitized = sanitized.replace(" ", "%s")  # ADB uses %s for space
        
        self.device.shell(f'input text "{sanitized}"')
        return f"Entered text: '{text}'"
    
    def press_key(self, keycode: int) -> str:
        """Press a key by its Android keycode.
        
        Args:
            keycode: Android keycode (e.g., 3 for HOME, 4 for BACK).
        
        Returns:
            Status message confirming the key press.
        """
        self.device.shell(f"input keyevent {keycode}")
        return f"Pressed key: {keycode}"
    
    def press_home(self) -> str:
        """Press the HOME button.
        
        Returns:
            Status message confirming the action.
        """
        return self.press_key(3)  # KEYCODE_HOME
    
    def press_back(self) -> str:
        """Press the BACK button.
        
        Returns:
            Status message confirming the action.
        """
        return self.press_key(4)  # KEYCODE_BACK
    
    def press_enter(self) -> str:
        """Press the ENTER key.
        
        Returns:
            Status message confirming the action.
        """
        return self.press_key(66)  # KEYCODE_ENTER
    
    def press_recent_apps(self) -> str:
        """Press the RECENT APPS button.
        
        Returns:
            Status message confirming the action.
        """
        return self.press_key(187)  # KEYCODE_APP_SWITCH
    
    def get_screenshot(self) -> Image.Image:
        """Capture a screenshot from the device.
        
        Returns:
            PIL Image object containing the screenshot.
        """
        # adbutils.screenshot() returns PIL.Image directly
        return self.device.screenshot()
    
    def get_screen_size(self) -> tuple[int, int]:
        """Get the screen resolution of the device.
        
        Returns:
            Tuple of (width, height) in pixels.
        """
        output = self.device.shell("wm size")
        # Output format: "Physical size: 1080x2400"
        size_str = output.strip().split(": ")[-1]
        width, height = map(int, size_str.split("x"))
        return width, height
    
    def launch_app(self, package: str) -> str:
        """Launch an app by its package name.
        
        Args:
            package: The package name (e.g., 'com.android.settings').
        
        Returns:
            Status message confirming the launch.
        """
        self.device.shell(
            f"monkey -p {package} -c android.intent.category.LAUNCHER 1"
        )
        return f"Launched app: {package}"
    
    def get_ui_hierarchy(self) -> str:
        """Dump the UI hierarchy XML from the device.
        
        Uses uiautomator to capture the current UI tree structure.
        
        Returns:
            Raw XML string of the UI hierarchy.
        """
        # Dump directly to stdout to avoid file permission issues
        output = self.device.shell("uiautomator dump /dev/tty")
        
        # Extract only the XML part (between <?xml ... </hierarchy>)
        xml_start = output.find("<?xml")
        xml_end = output.find("</hierarchy>")
        
        if xml_start != -1 and xml_end != -1:
            output = output[xml_start:xml_end + len("</hierarchy>")]
        
        return output.strip()
