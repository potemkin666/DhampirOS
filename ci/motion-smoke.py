#!/usr/bin/python3
# Copyright (C) 2026 potemkin666
# See the file COPYING for copying conditions.
# AI-Assisted

"""Small real labwc/GStreamer smoke; logind state is an explicit fixture."""

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

from gi.repository import Gio, GLib
from PIL import Image

CLI = '/usr/bin/dhampiros-motion'
processes = []
evidence = Path(sys.argv[1]).resolve()


def launch(command):
    child = subprocess.Popen(command, stdout=sys.stderr, stderr=sys.stderr, start_new_session=True)
    processes.append(child)
    return child


def call(*arguments):
    return subprocess.check_output([CLI, *arguments], text=True, timeout=15)


def status():
    return json.loads(call('status'))


def until(predicate, seconds=16):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.25)
    raise AssertionError(f'Timeout waiting for native state; last status: {status()}')


def player_pids():
    result = []
    for path in Path('/proc').glob('[0-9]*/cmdline'):
        try:
            if b'/usr/libexec/dhampiros-motion/player.py\x00' in path.read_bytes():
                result.append(int(path.parent.name))
        except (PermissionError, FileNotFoundError):
            pass
    return result


def capture(name):
    output = evidence / f'{name}.png'
    subprocess.run(['grim', str(output)], check=True, timeout=8)
    image = Image.open(output).convert('RGB')
    assert len(set(image.getdata())) > 1000, 'Missing wallpaper: the native desktop is nearly blank'
    return image.tobytes()


def session_state(active, locked):
    Gio.bus_get_sync(Gio.BusType.SESSION, None).call_sync(
        'org.freedesktop.login1', '/org/freedesktop/login1/session/motiontest',
        'org.dhampiros.MotionTest', 'SetState', GLib.Variant('(bb)', (active, locked)),
        None, Gio.DBusCallFlags.NONE, 1000, None)


try:
    with tempfile.TemporaryDirectory(prefix='dhampiros-native-') as temporary:
        home = Path(temporary)
        runtime = home / 'run'
        runtime.mkdir(mode=0o700)
        (home / 'Desktop').mkdir()
        (home / 'Desktop/Native motion check.txt').write_text('PCManFM still owns these desktop icons.\n')
        config = home / '.config'
        (config / 'labwc').mkdir(parents=True)
        (config / 'labwc/rc.xml').write_text('<labwc_config/>')
        os.environ.update(HOME=str(home), XDG_CONFIG_HOME=str(config), XDG_RUNTIME_DIR=str(runtime),
                          XDG_SESSION_TYPE='wayland', XDG_CURRENT_DESKTOP='LXQt:labwc:wlroots',
                          QT_QPA_PLATFORM='wayland', WLR_BACKENDS='headless', WLR_RENDERER='pixman',
                          WLR_LIBINPUT_NO_DEVICES='1', WLR_HEADLESS_OUTPUTS='1',
                          DBUS_SYSTEM_BUS_ADDRESS=os.environ['DBUS_SESSION_BUS_ADDRESS'])
        launch([str(Path(__file__).with_name('motion-session-fixture.py'))])
        compositor = launch(['labwc', '--config-dir', str(config / 'labwc')])
        until(lambda: bool([p for p in runtime.glob('wayland-*') if p.is_socket()]))
        os.environ['WAYLAND_DISPLAY'] = next(p.name for p in runtime.glob('wayland-*') if p.is_socket())
        os.environ['LABWC_PID'] = str(compositor.pid)
        call('mode', 'full')
        manager = launch([CLI, 'desktop'])
        until(lambda: status().get('state') == 'playing' and status().get('desktop_pid'))
        time.sleep(3)
        first = capture('native-full-1')
        time.sleep(3)
        second = capture('native-full-2')
        assert first != second, 'Native wallpaper did not move'
        assert len(player_pids()) == 1, player_pids()
        owner = status()['manager_pid']
        subprocess.run([CLI, 'desktop'], check=True, timeout=5, stdout=sys.stderr)
        assert status()['manager_pid'] == owner and len(player_pids()) == 1
        time.sleep(2)
        resources = status()
        call('mode', 'reduced')
        until(lambda: status().get('player_pid') is None)
        time.sleep(2)
        still_one = capture('native-reduced-1')
        time.sleep(2)
        assert still_one == capture('native-reduced-2'), 'Reduced desktop is not static'
        assert 'DhampirOS-Cursors-Still' in (config / 'lxqt/session.conf').read_text()
        call('mode', 'off')
        assert status()['state'] == 'off' and not player_pids()
        call('quality', 'light')
        call('mode', 'full')
        until(lambda: status().get('quality') == 'light')
        session_state(True, True)
        until(lambda: status().get('player_pid') is None)
        assert not player_pids()
        session_state(True, False)
        until(lambda: status().get('player_pid') is not None)
        accessibility = Gio.Settings.new('org.gnome.desktop.interface')
        accessibility.set_boolean('enable-animations', False)
        Gio.Settings.sync()
        until(lambda: status().get('player_pid') is None)
        accessibility.set_boolean('enable-animations', True)
        Gio.Settings.sync()
        until(lambda: status().get('player_pid') is not None)
        session_state(False, False)
        until(lambda: status().get('player_pid') is None)
        session_state(True, False)
        until(lambda: status().get('player_pid') is not None)
        # Abrupt owner death must restore the still and close its decoder.
        os.kill(manager.pid, signal.SIGKILL)
        manager.wait(timeout=5)
        until(lambda: not player_pids())
        # The normal native file manager remains available after owner death.
        assert subprocess.run(['pcmanfm-qt', '--profile', 'dhampiros-motion', '--set-wallpaper',
                               '/usr/share/backgrounds/dhampiros/nocturne-rider.jpg'], timeout=5).returncode == 0
        # Clean up that remaining desktop before a second login-equivalent run.
        subprocess.run(['pcmanfm-qt', '--profile', 'dhampiros-motion', '--quit'], timeout=5, check=False)
        manager = launch([CLI, 'desktop'])
        until(lambda: status().get('player_pid') is not None)
        manager.terminate()
        manager.wait(timeout=8)
        until(lambda: not player_pids())
        result = {'environment': 'Debian trixie, headless labwc/pixman, actual GTK layer-shell/GStreamer/PCManFM',
                  'logind': 'Private-bus fixture; actual DhampirOS login/logout and lock remain unverified',
                  'native_frames_change': True, 'reduced_frames_static': True, 'off_no_player': True,
                  'duplicate_launch_one_owner': True, 'light_quality': True, 'lock_hint_stops_player': True,
                  'inactive_session_stops_player': True, 'owner_death_cleans_player': True,
                  'existing_accessibility_preference': True,
                  'second_session_and_clean_shutdown': True, 'resource_sample': resources}
        print(json.dumps(result, indent=2))
finally:
    for child in reversed(processes):
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=4)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=2)
