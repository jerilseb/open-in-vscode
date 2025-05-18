# Open in VSCode

A Chrome extension that adds an "Open in VSCode" button to GitHub repository pages. With a single click, this extension clones the repository to your desktop and opens it in Visual Studio Code.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## Installation

### Chrome Extension

1. Clone or download this repository to your local machine
2. Open Chrome and navigate to `chrome://extensions/`
3. Enable "Developer mode" by toggling the switch in the top right corner
4. Click "Load unpacked" and select the directory containing this extension
5. The extension should now be installed and active

#### Python Listener

The python listener needs to run for the extension to work. To have the listener start automatically when you log in:

**On Linux:**
- Create an entry in the `.config/autostart` directory. For example

```
[Desktop Entry]
Exec=/usr/bin/python3 /home/jeril/Desktop/github-vscode/github_listener.py
Icon=dialog-scripts
NoDisplay=false
Name=Github-Listener
Type=Application
```

## Usage

1. Navigate to any GitHub repository page
2. You'll see an "Open in VSCode" button next to the "Code" button
3. Click the button to clone the repository to your desktop and open it in VS Code
4. The repository will be cloned to a temporary directory on your desktop

## Requirements

- Google Chrome browser
- Python 3.x
- Git (installed and in your PATH)
- Visual Studio Code with CLI capabilities (the `code` command must be available in your PATH)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.