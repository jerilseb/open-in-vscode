#!/usr/bin/env python3

import subprocess
import os
import sys
import shutil
import tempfile
import re
import signal
import atexit
import errno  # For specific OSError codes
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading  # For graceful server shutdown

# --- Configuration ---
DEFAULT_PORT = 45678
CLONE_BASE_DIR = os.path.expanduser("~/Desktop")

# --- PID File Management ---
PID_FILE_TEMPLATE = "/tmp/github_listener_{}.pid"
PID_FILE = ""  # Will be set after port is determined


def create_pid_file():
    """Creates the PID file with the current process ID."""
    try:
        with open(PID_FILE, "w") as f:
            f.write(str(os.getpid()))
    except OSError as e:
        print(
            f"Fatal: Could not create PID file {PID_FILE}: {e}. Aborting.",
            file=sys.stderr,
        )
        sys.exit(1)


def is_process_running(pid):
    """Checks if a process with the given PID is running."""
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True


def check_and_exit_if_already_running(port_to_check):
    """Checks if another instance is running using a PID file. Exits if so."""
    global PID_FILE
    PID_FILE = PID_FILE_TEMPLATE.format(port_to_check)

    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, "r") as f:
                pid = int(f.read())
        except Exception:
            # Can't read PID file: treat as stale
            pid = None
        
        if pid and is_process_running(pid):
            print(
                f"Error: Another instance (PID {pid}) is already running on port {port_to_check}",
                file=sys.stderr,
            )
            sys.exit(1)
        else:
            # Stale PID file; remove it
            try:
                os.remove(PID_FILE)
            except OSError as e:
                print(
                    f"Warning: Could not remove stale PID file {PID_FILE}: {e}",
                    file=sys.stderr,
                )
                sys.exit(1)

    create_pid_file()


def cleanup_pid_file():
    """Removes the PID file if it exists and belongs to the current process."""
    if PID_FILE and os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, "r") as f:
                pid_in_file = int(f.read().strip())
            if pid_in_file == os.getpid():
                os.remove(PID_FILE)
        except (ValueError, OSError, FileNotFoundError):
            pass


atexit.register(cleanup_pid_file)

# --- Function to show notifications ---
def show_notification(message, title, type_):
    """Shows a desktop notification and prints to console."""
    timeout_ms = 3000 if type_ == "info" else 5000
    notification_cmd = None

    if shutil.which("notify-send"):
        notification_cmd = ["notify-send", "-t", str(timeout_ms), title, message]
    elif shutil.which("kdialog"):
        notification_cmd = [
            "kdialog",
            "--passivepopup",
            message,
            str(timeout_ms // 1000),
            "--title",
            title,
        ]
    elif shutil.which("zenity"):
        notification_cmd = ["zenity", "--notification", f"--text={title}: {message}"]

    if notification_cmd:
        try:
            if "kdialog" in notification_cmd[0] or "zenity" in notification_cmd[0]:
                subprocess.Popen(notification_cmd)
            else:
                subprocess.run(notification_cmd, check=False)
        except Exception as e:
            print(
                f"Warning: Failed to send notification via {notification_cmd[0]}: {e}",
                file=sys.stderr,
            )

    if type_ == "error":
        print(f"Error: {title} - {message}", file=sys.stderr)
    else:
        print(f"Info: {title} - {message}", file=sys.stdout)


def show_error(message):
    show_notification(message, "ERROR", "error")


def show_info(message):
    show_notification(message, "INFO", "info")


# --- Helper function to run a command detached ---
def run_detached(command_args):
    """Runs a command detached from the current process."""
    try:
        kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
        kwargs["start_new_session"] = True
        subprocess.Popen(command_args, **kwargs)
        return True
    except Exception as e:
        show_error(f"Failed to run detached '{' '.join(command_args)}': {e}")
        return False


# --- Function to open VS Code ---
def open_editor(directory):
    """Attempts to open the given directory in VS Code."""
    code_cmd = shutil.which("code")
    if code_cmd:
        return run_detached([code_cmd, directory])
    show_error("'code' (VS Code CLI) not found in PATH.")
    return False


# --- Pre-flight Checks ---
def pre_flight_checks():
    """Performs essential checks before starting the server. Exits on failure."""
    if not shutil.which("git"):
        show_error("'git' is not installed or not in PATH.")
        sys.exit(1)
    if not shutil.which("code"):
        show_error("'code' (VS Code CLI) is not installed or not in PATH.")
        sys.exit(1)
    try:
        if not os.path.isdir(CLONE_BASE_DIR) or not os.access(CLONE_BASE_DIR, os.W_OK):
            show_error(f"Directory '{CLONE_BASE_DIR}' doesn't exist or isn't writable.")
            sys.exit(1)
    except OSError as e:
        show_error(f"Error with Directory '{CLONE_BASE_DIR}': {e}")
        sys.exit(1)


# --- HTTP Request Handler ---
class GitHubListenerHandler(BaseHTTPRequestHandler):
    """Handles incoming HTTP requests for cloning GitHub repos."""

    def _send_cors_headers(self, allow_methods="POST, OPTIONS"):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", allow_methods)
        self.send_header(
            "Access-Control-Allow-Headers", "Content-Type, X-Requested-With"
        )
        self.send_header("Access-Control-Max-Age", "86400")  # 1 day

    def do_OPTIONS(self):
        self.send_response(204)  # No Content
        self._send_cors_headers()
        self.end_headers()
        print("Handled OPTIONS request.", file=sys.stderr)

    def do_POST(self):
        response_status_code = 500  # Default to Internal Server Error
        response_body_str = "An unexpected error occurred."
        clone_target_dir = None

        try:
            content_length_str = self.headers.get("Content-Length")
            try:
                content_length = int(content_length_str) if content_length_str else 0
                if content_length < 0:
                    content_length = 0
            except ValueError:
                content_length = 0
                print(
                    f"Warning: Malformed Content-Length: '{content_length_str}'. Treating as 0.",
                    file=sys.stderr,
                )

            body_bytes = self.rfile.read(content_length)
            github_url = body_bytes.decode("utf-8", errors="ignore").strip()
            print(f"Received POST for URL: '{github_url}'", file=sys.stderr)

            if not content_length or not github_url:
                response_body_str = "Error: No content in POST request or empty URL."
                response_status_code = 400  # Bad Request
                show_error(response_body_str)
            elif re.match(
                r"^(https|git)://github\.com/.+/.+(\.git)?$", github_url
            ) or re.match(r"^git@github\.com:.+/.+\.git$", github_url):

                repo_name_match = re.search(r"/([^/]+?)(\.git)?$", github_url)
                repo_name = (
                    repo_name_match.group(1) if repo_name_match else "repository"
                )

                clone_target_dir = tempfile.mkdtemp(
                    prefix=f"{repo_name}_", dir=CLONE_BASE_DIR
                )
                show_info(f"Cloning repository..")

                clone_process = subprocess.run(
                    ["git", "clone", "--depth", "1", github_url, clone_target_dir],
                    capture_output=True,
                    text=True,
                    check=True,
                    encoding="utf-8",
                    errors="ignore",
                )
                print(
                    f"Successfully cloned: {clone_process.stdout.strip()}",
                    file=sys.stderr,
                )

                if open_editor(clone_target_dir):
                    response_body_str = f"Success: Cloned '{repo_name}' and opened in VS Code at '{clone_target_dir}'."
                    response_status_code = 200  # OK
                else:
                    # open_editor already calls show_error
                    response_body_str = (
                        f"Error: Cloned '{repo_name}' but failed to open in VS Code."
                    )
                    response_status_code = 500  # Internal Server Error
                    # shutil.rmtree below in finally will handle this if clone_target_dir exists
            else:  # Invalid GitHub URL
                response_body_str = f"Error: Invalid GitHub URL: '{github_url}'."
                response_status_code = 400  # Bad Request
                show_error(response_body_str)

        except subprocess.CalledProcessError as e:
            response_body_str = f"Error: Failed to clone '{github_url}'. Git output: {e.stderr.strip() or e.stdout.strip()}"
            response_status_code = 500
            show_error(response_body_str)
        except Exception as e:  # Catch other potential errors (mkdtemp, etc.)
            response_body_str = f"An unexpected error occurred: {e}"
            response_status_code = 500
            show_error(response_body_str)
        finally:
            if (
                response_status_code >= 400
                and clone_target_dir
                and os.path.exists(clone_target_dir)
            ):
                shutil.rmtree(clone_target_dir, ignore_errors=True)

            self.send_response(response_status_code)
            self._send_cors_headers()
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            response_body_bytes = response_body_str.encode("utf-8")
            self.send_header("Content-Length", str(len(response_body_bytes)))
            self.end_headers()
            self.wfile.write(response_body_bytes)
            print(f"Response sent ({response_status_code}).", file=sys.stderr)

    def log_message(self, format, *args):
        # print(f"HTTP Server Log: {format % args}", file=sys.stderr) # Uncomment for debugging http.server messages
        return  # Suppress default logging


# --- Main Application ---
http_server_instance = None  # Global to be accessible by signal_handler


def main():
    """Main function to start the HTTP listener."""
    global http_server_instance

    if len(sys.argv) > 1:
        try:
            current_port = int(sys.argv[1])
            if not (1024 <= current_port <= 65535):
                raise ValueError("Port must be between 1024 and 65535.")
        except ValueError as e:
            print(f"Error: Invalid port number '{sys.argv[1]}'. {e}", file=sys.stderr)
            sys.exit(1)
    else:
        current_port = DEFAULT_PORT

    pre_flight_checks()
    check_and_exit_if_already_running(current_port)

    def signal_handler(sig, frame):
        print("\nShutting down listener...", file=sys.stderr)
        if http_server_instance:
            # Shutdown needs to be called from a different thread
            threading.Thread(target=http_server_instance.shutdown, daemon=True).start()
        # sys.exit(0) will allow atexit (PID cleanup) to run.
        # If shutdown hangs, the process will eventually be killed by OS or user.
        # No explicit sys.exit here; let serve_forever() exit naturally after shutdown.
        # If signal received before server starts, this handler might not have http_server_instance.
        # We call sys.exit(0) to ensure cleanup if that's the case.
        if not http_server_instance:
            sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        server_address = ("", current_port)  # Listen on all interfaces
        http_server_instance = HTTPServer(server_address, GitHubListenerHandler)

        show_info("GitHub Listener (HTTP) started")
        http_server_instance.serve_forever()  # Blocks until shutdown() is called

    except OSError as e:
        show_error(f"Could not start HTTP server on port {current_port}: {e}")
        if "Address already in use" in str(e) and PID_FILE and os.path.exists(PID_FILE):
            print(
                f"Hint: Check PID file {PID_FILE} or if another process is using port {current_port}.",
                file=sys.stderr,
            )
        sys.exit(1)
    except Exception as e:
        show_error(f"An unexpected error occurred with the HTTP server: {e}")
        sys.exit(1)
    finally:
        if http_server_instance:
            http_server_instance.server_close()  # Clean up the server socket
        print("Listener stopped.", file=sys.stderr)


if __name__ == "__main__":
    main()
