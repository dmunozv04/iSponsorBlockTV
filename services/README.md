# Services

This directory holds platform-specific service definitions and installers.

## Layout

- `services/systemd/`: Linux systemd unit and installer.
- (planned) `services/macos/`: launchd plist and installer.
- (planned) `services/windows/`: Windows service or scheduled task scripts.

## Linux (systemd)

Install inside the target host/container after cloning to `/opt/isponsorblocktv`:

```
/opt/isponsorblocktv/services/systemd/install.sh
```

This installs `isponsorblocktv.service`, creates a virtualenv and installs
the app from `/opt/isponsorblocktv`, sets `iSPBTV_data_dir` to
`/var/lib/isponsorblocktv`, and starts the service. It also installs a
`/usr/local/bin/iSponsorBlockTV` wrapper (symlinked to `/usr/bin/iSponsorBlockTV`)
that restarts the service after `setup` or `setup-cli`, and exports the
default data dir via `/etc/profile.d/isponsorblocktv.sh` and `/etc/environment`.

If `apt-get` is available, the installer will install `python3`, `python3-venv`,
and `python3-pip`. Otherwise, ensure those packages are installed beforehand.
