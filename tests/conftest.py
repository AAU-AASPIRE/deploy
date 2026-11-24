"""The live test's option and a free port (as the aseptic line's conftest has them)."""
import socket


def pytest_addoption(parser):
    parser.addoption("--pi-forte-exe", help="aarch64 FORTE (forte-runtime's build-modules.ps1 -Config pi/modules-pi) for tests/test_pwm_emulated.py")


def free_port():
    """Return a free TCP port on localhost."""
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        return reservation.getsockname()[1]
