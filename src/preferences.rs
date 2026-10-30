//! Local, non-secret desktop preferences.
//!
//! This is deliberately separate from the Pico configuration.  It only keeps
//! presentation and reconnecting conveniences; session credentials must never be put in this file.
//! The optional local API opt-in is retained; credentials are regenerated.

use std::{
    collections::{BTreeMap, BTreeSet},
    fs,
    io::{self, Write},
    net::Ipv4Addr,
    path::{Path, PathBuf},
};

use kohdalab_control_protocol::paths::AppPaths;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use tempfile::NamedTempFile;

const SCHEMA_VERSION: u8 = 1;
const DEFAULT_LAYOUT: &str = "horizontal";
const DEFAULT_ORDER: &str = "ascending";
const DEFAULT_BROADCAST: &str = "255.255.255.255";
const DEFAULT_MANUAL_PORT: u16 = 12345;
const MAX_LABEL_CHARS: usize = 32;
const MAX_LABEL_BYTES: usize = 96;

/// Preferences which are safe to retain on the computer running the GUI.
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Preferences {
    pub application: String,
    #[serde(default)]
    pub local_control_api: bool,
    #[serde(default = "default_schema_version")]
    pub schema_version: u8,
    #[serde(default = "default_layout")]
    pub layout: String,
    #[serde(default = "default_order")]
    pub order: String,
    #[serde(default = "default_broadcast")]
    pub broadcast: String,
    /// A manually entered endpoint only; it is never used to auto-connect.
    #[serde(default)]
    pub manual_host: String,
    #[serde(default = "default_manual_port")]
    pub manual_port: u16,
    #[serde(default)]
    pub last_device: Option<String>,
    #[serde(default)]
    pub devices: BTreeMap<String, DevicePreferences>,
    /// Future fields are retained so an older GUI does not erase them.
    #[serde(flatten)]
    pub extra: BTreeMap<String, Value>,
}

/// Preferences associated with one Pico device ID.
#[derive(Clone, Debug, Default, PartialEq, Serialize, Deserialize)]
pub struct DevicePreferences {
    #[serde(default)]
    pub selected_channels: Vec<u8>,
    /// Cached Pico label. An empty value means that no label is known yet.
    #[serde(default)]
    pub label: String,
    #[serde(default)]
    pub channel_labels: BTreeMap<u8, String>,
    /// Future fields are retained so an older GUI does not erase them.
    #[serde(flatten)]
    pub extra: BTreeMap<String, Value>,
}

impl Default for Preferences {
    fn default() -> Self {
        Self {
            application: "kohdalab-shutter".into(),
            local_control_api: false,
            schema_version: SCHEMA_VERSION,
            layout: DEFAULT_LAYOUT.to_owned(),
            order: DEFAULT_ORDER.to_owned(),
            broadcast: DEFAULT_BROADCAST.to_owned(),
            manual_host: String::new(),
            manual_port: DEFAULT_MANUAL_PORT,
            last_device: None,
            devices: BTreeMap::new(),
            extra: BTreeMap::new(),
        }
    }
}

impl Preferences {
    /// Load preferences without ever repairing or replacing a bad existing file.
    pub fn load(path: &Path) -> io::Result<Self> {
        let contents = match fs::read_to_string(path) {
            Ok(contents) => contents,
            Err(error) if error.kind() == io::ErrorKind::NotFound => return Ok(Self::default()),
            Err(error) => return Err(error),
        };
        let preferences: Self = serde_json::from_str(&contents)
            .map_err(|error| invalid_data(format!("invalid preferences JSON: {error}")))?;
        preferences.validate()?;
        Ok(preferences)
    }

    /// Validate then atomically replace the preference file.
    pub fn save(&self, path: &Path) -> io::Result<()> {
        self.validate()?;
        let parent = path
            .parent()
            .filter(|parent| !parent.as_os_str().is_empty())
            .unwrap_or_else(|| Path::new("."));
        fs::create_dir_all(parent)?;

        let mut temporary = NamedTempFile::new_in(parent)?;
        serde_json::to_writer_pretty(&mut temporary, self)
            .map_err(|error| invalid_data(format!("could not encode preferences: {error}")))?;
        temporary.write_all(b"\n")?;
        temporary.as_file_mut().sync_all()?;
        temporary
            .persist(path)
            .map(|_| ())
            .map_err(|error| error.error)
    }

    pub fn ensure_default(path: &Path) -> io::Result<bool> {
        if path.exists() {
            return Ok(false);
        }
        let parent = path
            .parent()
            .filter(|p| !p.as_os_str().is_empty())
            .unwrap_or_else(|| Path::new("."));
        fs::create_dir_all(parent)?;
        let data = serde_json::to_vec_pretty(&Self::default())
            .map_err(|error| invalid_data(format!("could not encode preferences: {error}")))?;
        let mut temporary = NamedTempFile::new_in(parent)?;
        temporary.write_all(&data)?;
        temporary.as_file_mut().sync_all()?;
        match temporary.persist_noclobber(path) {
            Ok(_) => Ok(true),
            Err(error) if error.error.kind() == io::ErrorKind::AlreadyExists => Ok(false),
            Err(error) => Err(error.error),
        }
    }

    /// Check values before they reach disk or are used by the GUI.
    pub fn validate(&self) -> io::Result<()> {
        if self.application != "kohdalab-shutter" {
            return Err(invalid_data("Configuration belongs to another application"));
        }
        if self.schema_version != SCHEMA_VERSION {
            return Err(invalid_data(format!(
                "unsupported preferences schema version {}",
                self.schema_version
            )));
        }
        if !matches!(self.layout.as_str(), "horizontal" | "vertical") {
            return Err(invalid_data("layout must be horizontal or vertical"));
        }
        if !matches!(self.order.as_str(), "ascending" | "descending") {
            return Err(invalid_data("order must be ascending or descending"));
        }
        self.broadcast
            .parse::<Ipv4Addr>()
            .map_err(|_| invalid_data("broadcast must be an IPv4 address"))?;
        if self.manual_host.chars().count() > 253
            || self
                .manual_host
                .chars()
                .any(|character| matches!(character, '\r' | '\n'))
        {
            return Err(invalid_data(
                "manual host must be at most 253 characters and contain no line breaks",
            ));
        }
        if self.manual_port == 0 {
            return Err(invalid_data("manual port must be between 1 and 65535"));
        }
        if let Some(device_id) = &self.last_device {
            validate_device_id(device_id)?;
        }
        for (device_id, device) in &self.devices {
            validate_device_id(device_id)?;
            device.validate()?;
        }
        Ok(())
    }
}

impl DevicePreferences {
    fn validate(&self) -> io::Result<()> {
        let mut selected = BTreeSet::new();
        for &channel in &self.selected_channels {
            validate_channel(channel)?;
            if !selected.insert(channel) {
                return Err(invalid_data(
                    "selected_channels contains a duplicate channel",
                ));
            }
        }
        // An empty device label is the intentional default for an unknown/offline Pico.
        if !self.label.is_empty() {
            validate_label(&self.label)?;
        }
        for (&channel, label) in &self.channel_labels {
            validate_channel(channel)?;
            validate_label(label)?;
        }
        Ok(())
    }
}

/// Return the standard per-user preference path for the current platform.
pub fn default_path() -> Option<PathBuf> {
    AppPaths::for_app("shutter")
        .ok()
        .map(|paths| paths.config_file())
}

fn default_schema_version() -> u8 {
    SCHEMA_VERSION
}

fn default_layout() -> String {
    DEFAULT_LAYOUT.to_owned()
}

fn default_order() -> String {
    DEFAULT_ORDER.to_owned()
}

fn default_broadcast() -> String {
    DEFAULT_BROADCAST.to_owned()
}

fn default_manual_port() -> u16 {
    DEFAULT_MANUAL_PORT
}

fn validate_device_id(device_id: &str) -> io::Result<()> {
    if !(1..=64).contains(&device_id.len())
        || !device_id.bytes().all(|byte| byte.is_ascii_hexdigit())
    {
        return Err(invalid_data(
            "device ID must contain 1 to 64 hexadecimal characters",
        ));
    }
    Ok(())
}

fn validate_channel(channel: u8) -> io::Result<()> {
    if channel > 15 {
        return Err(invalid_data("channel must be between 0 and 15"));
    }
    Ok(())
}

fn validate_label(label: &str) -> io::Result<()> {
    if label.is_empty()
        || label.len() > MAX_LABEL_BYTES
        || label.chars().count() > MAX_LABEL_CHARS
        || label
            .chars()
            .any(|character| character.is_control() || matches!(character, '\u{2028}' | '\u{2029}'))
    {
        return Err(invalid_data(
            "label must be 1-32 printable characters (at most 96 UTF-8 bytes)",
        ));
    }
    Ok(())
}

fn invalid_data(message: impl Into<String>) -> io::Error {
    io::Error::new(io::ErrorKind::InvalidData, message.into())
}

#[cfg(test)]
#[allow(clippy::field_reassign_with_default)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn round_trips_per_device_preferences() {
        let directory = tempdir().unwrap();
        let path = directory.path().join("nested/preferences.json");
        let mut preferences = Preferences::default();
        preferences.layout = "vertical".into();
        preferences.order = "descending".into();
        preferences.broadcast = "192.168.10.255".into();
        preferences.manual_host = "shutter.local".into();
        preferences.manual_port = 12346;
        preferences.last_device = Some("a1b2".into());
        preferences.devices.insert(
            "a1b2".into(),
            DevicePreferences {
                selected_channels: vec![1, 3],
                label: "Main shutter".into(),
                channel_labels: BTreeMap::from([(1, "Probe".into()), (3, "Pump".into())]),
                ..DevicePreferences::default()
            },
        );
        preferences.devices.insert(
            "c3d4".into(),
            DevicePreferences {
                selected_channels: vec![0],
                label: "予備".into(),
                channel_labels: BTreeMap::from([(0, "Sample".into())]),
                ..DevicePreferences::default()
            },
        );

        preferences.save(&path).unwrap();
        assert_eq!(Preferences::load(&path).unwrap(), preferences);
    }

    #[test]
    fn corrupt_file_is_rejected_without_modifying_it() {
        let directory = tempdir().unwrap();
        let path = directory.path().join("preferences.json");
        let corrupt = "{ not valid JSON";
        fs::write(&path, corrupt).unwrap();

        assert_eq!(
            Preferences::load(&path).unwrap_err().kind(),
            io::ErrorKind::InvalidData
        );
        assert_eq!(fs::read_to_string(&path).unwrap(), corrupt);
    }

    #[test]
    fn persist_replaces_an_existing_preference_file() {
        let directory = tempdir().unwrap();
        let path = directory.path().join("preferences.json");
        let mut first = Preferences::default();
        first.layout = "vertical".into();
        first.save(&path).unwrap();

        let mut replacement = Preferences::default();
        replacement.order = "descending".into();
        replacement.save(&path).unwrap();

        assert_eq!(Preferences::load(&path).unwrap(), replacement);
    }

    #[test]
    fn preserves_unknown_root_and_device_fields() {
        let directory = tempdir().unwrap();
        let path = directory.path().join("preferences.json");
        fs::write(
            &path,
            r#"{
                "application":"kohdalab-shutter",
                "schema_version": 1,
                "layout": "horizontal",
                "order": "ascending",
                "broadcast": "255.255.255.255",
                "future_root": {"enabled": true},
                "devices": {
                    "a1": {
                        "selected_channels": [0],
                        "label": "Main",
                        "channel_labels": {"0": "Probe"},
                        "future_device": [1, 2]
                    }
                }
            }"#,
        )
        .unwrap();

        let preferences = Preferences::load(&path).unwrap();
        assert_eq!(preferences.extra["future_root"]["enabled"], true);
        assert_eq!(
            preferences.devices["a1"].extra["future_device"],
            serde_json::json!([1, 2])
        );
        preferences.save(&path).unwrap();

        let written: Value = serde_json::from_str(&fs::read_to_string(&path).unwrap()).unwrap();
        assert_eq!(written["future_root"]["enabled"], true);
        assert_eq!(
            written["devices"]["a1"]["future_device"],
            serde_json::json!([1, 2])
        );
    }

    #[test]
    fn foreign_and_unmarked_files_are_rejected_without_rewriting() {
        let directory = tempdir().unwrap();
        let path = directory.path().join("config.json");
        for contents in [
            r#"{"application":"kohdalab-iv","schema_version":1}"#,
            r#"{"schema_version":1}"#,
        ] {
            fs::write(&path, contents).unwrap();
            assert!(Preferences::load(&path).is_err());
            assert_eq!(fs::read_to_string(&path).unwrap(), contents);
        }
        let default = default_path().unwrap();
        assert!(default.ends_with(".kohdalab/shutter/config/config.json"));
    }

    #[test]
    fn ensure_default_creates_once_and_preserves_existing_or_invalid() {
        let directory = tempdir().unwrap();
        let path = directory.path().join("config.json");
        assert!(Preferences::ensure_default(&path).unwrap());
        let first = fs::read(&path).unwrap();
        assert!(!Preferences::ensure_default(&path).unwrap());
        assert_eq!(fs::read(&path).unwrap(), first);
        let foreign = br#"{"application":"foreign"}"#;
        fs::write(&path, foreign).unwrap();
        assert!(!Preferences::ensure_default(&path).unwrap());
        assert_eq!(fs::read(&path).unwrap(), foreign);
    }
    #[test]
    fn ensure_default_concurrent_initialization_publishes_complete_json() {
        let directory = tempdir().unwrap();
        let path = directory.path().join("config.json");
        let a = {
            let p = path.clone();
            std::thread::spawn(move || Preferences::ensure_default(&p).unwrap())
        };
        let b = {
            let p = path.clone();
            std::thread::spawn(move || Preferences::ensure_default(&p).unwrap())
        };
        assert_eq!(a.join().unwrap() as u8 + b.join().unwrap() as u8, 1);
        assert!(Preferences::load(&path).is_ok());
    }
    #[test]
    fn ensure_default_reports_unusable_parent() {
        let directory = tempdir().unwrap();
        let parent = directory.path().join("file");
        fs::write(&parent, b"file").unwrap();
        assert!(Preferences::ensure_default(&parent.join("child/config.json")).is_err());
    }

    #[test]
    fn rejects_invalid_local_values() {
        let mut preferences = Preferences::default();
        preferences.layout = "diagonal".into();
        assert!(preferences.validate().is_err());

        let mut preferences = Preferences::default();
        preferences.devices.insert(
            "deadbeef".into(),
            DevicePreferences {
                selected_channels: vec![1, 1],
                ..DevicePreferences::default()
            },
        );
        assert!(preferences.validate().is_err());

        let mut preferences = Preferences::default();
        preferences.manual_port = 0;
        assert!(preferences.validate().is_err());
    }
}
