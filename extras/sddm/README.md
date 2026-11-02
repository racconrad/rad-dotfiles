# Raccon SDDM

A Qt 6 login screen in the Raccon Menu visual family: the active palette, font,
border and corner shape, with a solid background. The greeter has editable user
names, an account menu, password visibility, Caps Lock feedback, session selection,
sign-in failure recovery and confirmation before restarting or shutting down.
Keyboard focus and tab order work without a mouse. Small screens center the panel
and scroll when necessary. Strict desktop styles disable transitions.

From the dots repository:

```sh
./extras/install-sddm.sh --prepare
./extras/install-sddm.sh --preview
./extras/install-sddm.sh --apply
```

Preparation writes `~/.local/share/sddm/themes/raccon`, including the active font.
Preview uses SDDM's test mode; login and power actions are simulated. Applying
requires sudo, copies the self-contained theme into `/usr/share/sddm/themes/raccon`
and selects it in `/etc/sddm.conf.d/zz-raccon-theme.conf`. If `/etc/sddm.conf`
already overrides Theme/Current, only that key is updated. Existing files are
saved under `/var/backups/raccon-sddm-*` with a restore script. No display manager
or user session is restarted, and no autologin or authentication policy is changed.

The palette is a snapshot: run `--apply` again after changing desktop style to
update SDDM, or press **Apply to SDDM** in the desktop style selector. Apply the
selected style to the desktop first to enable this button. It prepares the active
appearance without privileges, opens the desktop's polkit authentication dialog,
and returns to the selector with the result. Canceling authentication leaves SDDM
unchanged. It never restarts the session. `desktop-style sddm` is the equivalent
installed command; failures and backup/restore details are recorded in
`~/.local/state/desktop-style/sddm.log`. A greeter cannot read private user state before login. The default
background is solid; `--background wallpaper` optionally packages a still image.
Requires SDDM's Qt 6 greeter, Qt Quick Controls and fontconfig.

`python3 extras/sddm/check.py ~/.local/share/sddm/themes/raccon` tests the real
greeter offscreen at 1920×1080, 800×600 and 640×480 with isolated account/session
models and simulated authentication. It checks focus and Tab navigation,
double-submit prevention, selected-session forwarding, failure recovery, menus,
power confirmation and captures PNGs in `/tmp`. This also requires QtTest.
The packaged theme in `modules/desktop-styles/files/.local/share/raccon/sddm/raccon`
includes `preview.png`, which illustrates Retro with test account data. The
selector uses these installed assets and does not require a repository checkout.

SDDM API and safe theme testing follow the [official theming documentation](https://github.com/sddm/sddm/blob/develop/docs/THEMING.md).
Action icons come from Adwaita, licensed under LGPL-3.0-or-later or CC-BY-SA-3.0.
The menu mark is original vector geometry. Bundled font licenses accompany the
font when supplied by its installation.
