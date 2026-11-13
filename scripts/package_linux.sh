#!/usr/bin/env bash
set -euo pipefail

cargo build --locked --release --bin kohdalab-shutter --bin kohdalab-shutter-gui
version=$(target/release/kohdalab-shutter --version | awk '{print $NF}')
test "$(dpkg --print-architecture)" = amd64

out="$PWD/dist/linux"
mkdir -p "$out"
temp=$(mktemp -d)
trap 'rm -rf "$temp"' EXIT
stage="$temp/package"
install -d "$stage/DEBIAN" "$stage/usr/bin" "$stage/usr/share/applications" \
  "$stage/usr/share/doc/kohdalab-shutter" "$stage/usr/share/icons/hicolor/scalable/apps"
install -m755 target/release/kohdalab-shutter{,-gui} "$stage/usr/bin/"
install -m644 LICENSE "$stage/usr/share/doc/kohdalab-shutter/copyright"
install -m644 assets/kohdalab-shutter.svg "$stage/usr/share/icons/hicolor/scalable/apps/"
cat > "$stage/usr/share/applications/kohdalab-shutter.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=KohdaLab Shutter
Exec=kohdalab-shutter-gui
Icon=kohdalab-shutter
Terminal=false
Categories=Science;Education;
DESKTOP
cat > "$stage/DEBIAN/control" <<CONTROL
Package: kohdalab-shutter
Version: $version
Section: science
Priority: optional
Architecture: amd64
Maintainer: KohdaLab
Depends: libc6, libgcc-s1, libgl1, libegl1, libx11-6, libxcursor1, libxi6, libxrandr2, libxkbcommon0, libwayland-client0
Description: Desktop control for networked Pico W optical shutters
CONTROL
deb="$out/kohdalab-shutter_${version}_amd64.deb"
dpkg-deb --root-owner-group --build "$stage" "$deb"

name="kohdalab-shutter-$version-linux-x86_64"
portable="$temp/$name"
mkdir "$portable"
cp "$stage"/usr/bin/* LICENSE "$portable/"
cp -R bindings/control "$portable/control-sdk"
tar -C "$temp" -czf "$out/$name.tar.gz" "$name"
sudo apt-get install -y "$deb"
test "$(kohdalab-shutter --version)" = "kohdalab-shutter $version"
xvfb-run -a python3 scripts/verify_gui_api.py /usr/bin/kohdalab-shutter-gui --output "$out/linux-gui-api-validation.json"
mkdir "$temp/extracted"
tar -C "$temp/extracted" -xzf "$out/$name.tar.gz"
test "$("$temp/extracted/$name/kohdalab-shutter" --version)" = "kohdalab-shutter $version"
xvfb-run -a python3 scripts/verify_gui_api.py "$temp/extracted/$name/kohdalab-shutter-gui" --output "$out/linux-portable-gui-api-validation.json"
sudo apt-get remove -y kohdalab-shutter
test ! -e /usr/bin/kohdalab-shutter-gui
git rev-parse HEAD > "$out/BUILD-COMMIT.txt"
(cd "$out" && sha256sum ./*.deb ./*.tar.gz ./linux*-gui-api-validation.json ./BUILD-COMMIT.txt > SHA256SUMS-linux.txt)
