# GPO Autofish

A simple auto-fishing bot for GPO.

## Features

*   GUI for easy control
*   Adjustable PD controller parameters
*   Customizable hotkeys
*   Auto-purchase sequence

## Installation

1.  Clone the repository:
    ```bash
    git clone https://github.com/Karoo4/GPO-Fishy.git
    ```
2.  Install the dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

1.  Run the application:
    ```bash
    python fishyfish.py
    ```
2.  Use the GUI to configure the settings.
3.  Press the "Toggle Main Loop" hotkey (default: F1) to start/stop the auto-fishing.
4.  Press the "Toggle Overlay" hotkey (default: F2) to show/hide the scanning area.
5.  Press the "Exit" hotkey (default: F3) to close the application.

## Building the Executable

To build the executable, you need to have PyInstaller installed (`pip install pyinstaller`). Then, run the following command:

```bash
pyinstaller fishyfish.spec
```

The executable will be located in the `dist` directory.
