#![cfg_attr(target_os = "windows", windows_subsystem = "windows")]

use clap::Parser;
use eframe::egui::{self, Color32, RichText, Stroke, Vec2};
use kohdalab_shutter::{
    DEFAULT_PORT,
    control::{ApiError, Control, response, string},
    discovery::{self, Device},
    protocol::{Operation, Snapshot, Status},
    remote,
    session::{ChannelInfo, ControllerInfo},
    transport::Client,
};
use kohdalab_control_protocol::{is_common, prepare as prepare_common, response as common_response};
use serde_json::{Value, json};
use std::{
    collections::{BTreeMap, BTreeSet, VecDeque},
    net::{Ipv4Addr, SocketAddrV4},
    path::PathBuf,
    sync::{
        Arc,
        atomic::{AtomicBool, Ordering},
        mpsc::{self, Receiver},
    },
    time::{Duration, Instant},
};

const BG: Color32 = Color32::from_rgb(18, 19, 23);
const PANEL: Color32 = Color32::from_rgb(26, 27, 32);
const SURFACE: Color32 = Color32::from_rgb(34, 36, 43);
const BORDER: Color32 = Color32::from_rgb(56, 58, 67);
const TEXT: Color32 = Color32::from_rgb(235, 236, 241);
const MUTED: Color32 = Color32::from_rgb(160, 163, 176);
const BLUE: Color32 = Color32::from_rgb(48, 91, 158);
const BUTTON: Color32 = Color32::from_rgb(45, 46, 53);
const TEAL: Color32 = Color32::from_rgb(63, 215, 194);
const ORANGE: Color32 = Color32::from_rgb(245, 183, 82);
const RED: Color32 = Color32::from_rgb(255, 123, 130);

#[derive(Clone, Copy, PartialEq, Eq, clap::ValueEnum, serde::Serialize)]
#[serde(rename_all = "lowercase")]
enum Layout {
    Horizontal,
    Vertical,
}

#[derive(Clone, Copy, PartialEq, Eq, clap::ValueEnum, serde::Serialize)]
#[serde(rename_all = "lowercase")]
enum Order {
    Ascending,
    Descending,
}

#[derive(Parser)]
#[command(version, about = "KohdaLab Shutter desktop controller")]
struct Args {
    /// Explore simulated shutters without connecting to Pico W hardware
    #[arg(long)]
    demo: bool,
    /// Save a real GUI screenshot and exit (demo mode only)
    #[arg(long, requires = "demo")]
    screenshot: Option<PathBuf>,
    /// Capture the connection picker instead of the connected demo
    #[arg(long, requires = "demo")]
    picker: bool,
    /// Demo channel selection, e.g. 0,2
    #[arg(long, requires = "demo", value_delimiter = ',')]
    channels: Vec<u8>,
    /// Enable the authenticated loopback GUI control API
    #[arg(long)]
    gui_api: bool,
    #[arg(long, requires = "gui_api")]
    api_directory: Option<PathBuf>,
    /// Override the local preferences file (demo otherwise remains isolated)
    #[arg(long)]
    preferences: Option<PathBuf>,
    /// Capture Settings in the isolated demo
    #[arg(long, requires = "demo")]
    settings: bool,
    #[arg(long, value_enum)]
    layout: Option<Layout>,
    /// Display order only; physical channel identifiers never change
    #[arg(long, value_enum)]
    order: Option<Order>,
}

enum Reply {
    Devices(Vec<Device>, BTreeMap<String, ControllerInfo>),
    Info(ControllerInfo),
    Connected(Client, Snapshot, ControllerInfo),
    Released(ControllerInfo, Option<String>),
    Refreshed(Snapshot, ControllerInfo),
    Config(Result<ControllerInfo, String>),
    Accepted(String),
}
#[derive(Clone, Default)]
struct LabelPatch {
    device: Option<String>,
    channels: BTreeMap<u8, String>,
}

struct App {
    host: String,
    port: u16,
    broadcast: String,
    devices: Vec<Device>,
    device_info: BTreeMap<String, ControllerInfo>,
    info: Option<ControllerInfo>,
    device_label: String,
    channel_labels: BTreeMap<u8, String>,
    name_edits: BTreeMap<u8, String>,
    active_name: Option<(String, u8)>,
    refreshing: bool,
    queued_toggle: Option<u8>,
    dirty_device: bool,
    draft_device: Option<String>,
    dirty_channels: BTreeSet<u8>,
    config_due: Option<Instant>,
    config_pending: Option<LabelPatch>,
    pending_release: bool,
    config_error: String,
    settings_open: bool,
    preferences_path: Option<PathBuf>,
    preferences_saved: kohdalab_shutter::preferences::Preferences,
    preferences_candidate: kohdalab_shutter::preferences::Preferences,
    preferences_due: Option<Instant>,
    preferences_error: String,
    preferences_blocked: bool,
    selected: BTreeSet<u8>,
    last_size: Option<Vec2>,
    client: Option<Client>,
    status: Status,
    state: Snapshot,
    pending: Option<Receiver<Result<Reply, String>>>,
    next_refresh: Instant,
    message: String,
    error: bool,
    last_command: Option<String>,
    last_update: Option<Instant>,
    log: VecDeque<String>,
    started: Instant,
    demo: bool,
    demo_connected: bool,
    demo_status: Status,
    screenshot: Option<PathBuf>,
    screenshot_requested: bool,
    screenshot_success: Arc<AtomicBool>,
    layout: Layout,
    order: Order,
    control: Control,
    api: Option<remote::Server>,
    api_enabled: bool,
    api_error: String,
    api_directory: Option<PathBuf>,
    pending_api_job: Option<String>,
}

impl Default for App {
    fn default() -> Self {
        Self {
            host: String::new(),
            port: DEFAULT_PORT,
            broadcast: "255.255.255.255".into(),
            devices: Vec::new(),
            device_info: BTreeMap::new(),
            info: None,
            device_label: String::new(),
            channel_labels: BTreeMap::new(),
            name_edits: BTreeMap::new(),
            active_name: None,
            refreshing: false,
            queued_toggle: None,
            dirty_device: false,
            draft_device: None,
            dirty_channels: BTreeSet::new(),
            config_due: None,
            config_pending: None,
            pending_release: false,
            config_error: String::new(),
            settings_open: false,
            preferences_path: None,
            preferences_saved: Default::default(),
            preferences_candidate: Default::default(),
            preferences_due: None,
            preferences_error: String::new(),
            preferences_blocked: false,
            selected: BTreeSet::new(),
            last_size: None,
            client: None,
            status: Status::new(),
            state: Snapshot::default(),
            pending: None,
            next_refresh: Instant::now(),
            message: String::new(),
            error: false,
            last_command: None,
            last_update: None,
            log: VecDeque::new(),
            started: Instant::now(),
            demo: false,
            demo_connected: false,
            demo_status: Status::new(),
            screenshot: None,
            screenshot_requested: false,
            screenshot_success: Arc::new(AtomicBool::new(false)),
            layout: Layout::Horizontal,
            order: Order::Ascending,
            control: Control::default(),
            api: None,
            api_directory: None,
            api_enabled: false,
            api_error: String::new(),
            pending_api_job: None,
        }
    }
}

impl App {
    fn demo() -> Self {
        let mut app = Self {
            demo: true,
            ..Self::default()
        };
        app.devices = demo_devices();
        app.host = app.devices[0].address.ip().to_string();
        app.demo_status = [(0, 0), (1, 90), (2, 0), (3, 90)].into();
        for (i, device) in app.devices.iter().enumerate() {
            app.device_info
                .insert(device.id.clone(), demo_info(&device.id, i));
        }
        app.info = app.device_info.get(&app.devices[0].id).cloned();
        app.device_label = app.info.as_ref().unwrap().label.clone();
        app.channel_labels = app
            .info
            .as_ref()
            .unwrap()
            .channels
            .iter()
            .map(|ch| (ch.id, ch.label.clone()))
            .collect();
        app.selected = (0..4).collect();
        app.connect();
        app.log
            .push_front("00:00  Two simulated Pico W devices available".into());
        app
    }

    fn connected(&self) -> bool {
        if self.demo {
            self.demo_connected
        } else {
            self.client.is_some()
        }
    }

    fn record(&mut self, text: impl Into<String>) {
        let seconds = self.started.elapsed().as_secs();
        self.log.push_back(format!(
            "{:02}:{:02}  {}",
            seconds / 60,
            seconds % 60,
            text.into()
        ));
        if self.log.len() > 100 {
            self.log.pop_front();
        }
    }

    fn task(&mut self, job: impl FnOnce() -> std::io::Result<Reply> + Send + 'static) {
        let (sender, receiver) = mpsc::channel();
        self.pending = Some(receiver);
        self.refreshing = false;
        self.error = false;
        std::thread::spawn(move || {
            let result = job().map_err(|e| e.to_string());
            if let Err(mpsc::SendError(Ok(Reply::Connected(client, _, _)))) = sender.send(result) {
                let _ = client.release();
            }
        });
    }

    fn find(&mut self) {
        if self.demo {
            self.devices = demo_devices();
            self.message = "Two simulated devices. Select one, then connect.".into();
            self.record("Discovery: 2 simulated devices (no network)");
            return;
        }
        let target = match self.broadcast.parse::<Ipv4Addr>() {
            Ok(ip) => SocketAddrV4::new(ip, discovery::DISCOVERY_PORT),
            Err(_) => {
                self.error = true;
                self.message = "Enter a valid IPv4 broadcast address.".into();
                return;
            }
        };
        self.devices.clear();
        self.message = "Searching the local network...".into();
        self.record("Searching for Pico W devices");
        self.task(move || {
            let devices = discovery::discover(target, Duration::from_secs(2))?;
            let mut info = BTreeMap::new();
            // A small bounded batch avoids spending one timeout per absent controller.
            for batch in devices.chunks(8) {
                let workers: Vec<_> = batch
                    .iter()
                    .cloned()
                    .map(|device| {
                        std::thread::spawn(move || {
                            let client = Client::new(
                                device.address.ip().to_string(),
                                device.address.port(),
                                Duration::from_secs(2),
                                1,
                            )
                            .ok()?;
                            Some((device.id, client.info().ok()?))
                        })
                    })
                    .collect();
                for worker in workers {
                    if let Ok(Some((id, detail))) = worker.join() {
                        info.insert(id, detail);
                    }
                }
            }
            Ok(Reply::Devices(devices, info))
        });
    }

    fn endpoint(&self) -> std::io::Result<Client> {
        Client::new(
            self.host.trim().to_owned(),
            self.port,
            Duration::from_secs(2),
            2,
        )
    }

    fn select_device(&mut self, device: &Device) {
        self.host = device.address.ip().to_string();
        self.port = device.address.port();
        self.persist_preferences(true);
        self.selected.clear();
        self.name_edits.clear();
        self.active_name = None;
        self.queued_toggle = None;
        self.dirty_device = false;
        self.draft_device = None;
        self.dirty_channels.clear();
        self.config_due = None;
        self.channel_labels.clear();
        self.config_error.clear();
        self.info = self.device_info.get(&device.id).cloned();
        self.device_label = self
            .info
            .as_ref()
            .map_or(String::new(), |info| info.label.clone());
        if let Some(info) = self.info.clone() {
            self.restore_channels(&info);
            self.update_info(info);
        }
        self.error = false;
        self.message.clear();
        if !self.demo {
            match self.endpoint() {
                Ok(client) => self.task(move || client.info().map(Reply::Info)),
                Err(error) => {
                    self.error = true;
                    self.message = error.to_string();
                }
            }
        }
    }

    fn update_info(&mut self, info: ControllerInfo) {
        if self
            .draft_device
            .as_ref()
            .is_some_and(|id| id != &info.device_id)
        {
            self.dirty_device = false;
            self.dirty_channels.clear();
            self.config_due = None;
            self.draft_device = None;
            self.config_error =
                "Unsaved names belonged to a different Pico and were not applied.".into();
        }
        if !self.dirty_device {
            self.device_label = info.label.clone();
        }
        for channel in &info.channels {
            if !self.dirty_channels.contains(&channel.id) {
                self.channel_labels
                    .insert(channel.id, channel.label.clone());
            }
        }
        self.device_info
            .insert(info.device_id.clone(), info.clone());
        self.info = Some(info);
    }

    fn channel_label(&self, channel: u8) -> String {
        self.channel_labels
            .get(&channel)
            .filter(|label| !label.trim().is_empty())
            .cloned()
            .unwrap_or_else(|| format!("CH{channel:02}"))
    }

    fn changed_label(&mut self) {
        self.draft_device = self.info.as_ref().map(|info| info.device_id.clone());
        self.config_due = Some(Instant::now() + Duration::from_millis(700));
        self.config_error.clear();
    }

    fn label_patch(&self) -> Result<LabelPatch, String> {
        if self
            .draft_device
            .as_ref()
            .is_some_and(|id| self.info.as_ref().is_none_or(|info| &info.device_id != id))
        {
            return Err("Names belong to a different Pico.".into());
        }
        let mut patch = LabelPatch::default();
        if self.dirty_device {
            patch.device = Some(self.device_label.trim().to_owned());
        }
        for ch in &self.dirty_channels {
            patch.channels.insert(
                *ch,
                self.channel_labels
                    .get(ch)
                    .map_or("", String::as_str)
                    .trim()
                    .to_owned(),
            );
        }
        for label in patch.device.iter().chain(patch.channels.values()) {
            if label.is_empty()
                || label.chars().count() > 32
                || label.len() > 96
                || label
                    .chars()
                    .any(|ch| ch.is_control() || matches!(ch, '\u{2028}' | '\u{2029}'))
            {
                return Err("Name is empty or too long.".into());
            }
        }
        Ok(patch)
    }

    fn acknowledge_config(&mut self, patch: &LabelPatch, info: ControllerInfo) {
        if patch
            .device
            .as_ref()
            .is_some_and(|label| self.device_label.trim() == label)
        {
            self.dirty_device = false;
        }
        for (ch, label) in &patch.channels {
            if self
                .channel_labels
                .get(ch)
                .is_some_and(|value| value.trim() == label)
            {
                self.dirty_channels.remove(ch);
            }
        }
        self.update_info(info);
        if !self.dirty_device && self.dirty_channels.is_empty() {
            self.draft_device = None;
        }
        self.config_error.clear();
    }

    fn autosave_labels(&mut self) {
        if !self.connected()
            || self.control.owned()
            || self.pending.is_some()
            || self.config_due.is_none_or(|due| Instant::now() < due)
        {
            return;
        }
        self.config_due = None;
        let patch = match self.label_patch() {
            Ok(patch) => patch,
            Err(error) => {
                self.config_error = error;
                return;
            }
        };
        if patch.device.is_none() && patch.channels.is_empty() {
            return;
        }
        if self.demo {
            if let Some(mut info) = self.info.clone() {
                if let Some(label) = &patch.device {
                    info.label = label.clone();
                }
                for ch in &mut info.channels {
                    if let Some(label) = patch.channels.get(&ch.id) {
                        ch.label = label.clone();
                    }
                }
                self.acknowledge_config(&patch, info);
            }
        } else if let Some(client) = self.client.clone() {
            self.config_pending = Some(patch.clone());
            self.task(move || {
                Ok(Reply::Config(
                    client
                        .set_config(patch.device.as_deref(), &patch.channels)
                        .and_then(|()| client.info())
                        .map_err(|error| format!("Names were not saved: {error}")),
                ))
            });
        }
    }

    fn connect(&mut self) {
        self.last_command = None;
        self.last_update = None;
        self.error = false;
        if self.selected.is_empty() {
            self.error = true;
            self.message = "Select at least one available channel.".into();
            return;
        }
        if self.demo {
            if self.info.as_ref().is_some_and(|info| {
                info.channels
                    .iter()
                    .any(|ch| ch.locked && self.selected.contains(&ch.id))
            }) {
                self.error = true;
                self.message = "Selected channels are in use.".into();
                return;
            }
            self.demo_connected = true;
            self.status = self
                .demo_status
                .iter()
                .filter(|(ch, _)| self.selected.contains(ch))
                .map(|(&ch, &angle)| (ch, angle))
                .collect();
            self.state = Snapshot::demo(&self.status);
            self.last_update = Some(Instant::now());
            self.message.clear();
            return;
        }
        match self.endpoint() {
            Ok(client) => {
                let selected: Vec<_> = self.selected.iter().copied().collect();
                let expected_id = self
                    .devices
                    .iter()
                    .find(|device| {
                        device.address.ip().to_string() == self.host
                            && device.address.port() == self.port
                    })
                    .map(|device| device.id.clone());
                self.message = "Connecting…".into();
                self.task(move || {
                    let info = client.info()?;
                    if expected_id.is_some_and(|id| !id.eq_ignore_ascii_case(&info.device_id)) {
                        return Err(std::io::Error::other(
                            "Pico identity changed. Find and select the controller again.",
                        ));
                    }
                    let claimed = client.claim(&selected)?;
                    match claimed.snapshot().and_then(|snapshot| {
                        if selected.iter().all(|ch| snapshot.channels.contains_key(ch)) {
                            Ok(snapshot)
                        } else {
                            Err(std::io::Error::other(
                                "Selected channels are missing from Pico state",
                            ))
                        }
                    }) {
                        Ok(snapshot) => Ok(Reply::Connected(claimed, snapshot, info)),
                        Err(error) => {
                            let _ = claimed.release();
                            Err(error)
                        }
                    }
                });
            }
            Err(error) => {
                self.error = true;
                self.message = error.to_string();
            }
        }
    }

    fn disconnect(&mut self) {
        self.persist_preferences(true);
        if self.demo {
            self.config_due = Some(Instant::now());
            self.autosave_labels();
        }
        let patch = self.label_patch();
        let client = self.client.take();
        self.settings_open = false;
        self.active_name = None;
        self.name_edits.clear();
        self.queued_toggle = None;
        self.demo_connected = false;
        self.status.clear();
        self.state = Snapshot::default();
        self.last_update = None;
        self.message.clear();
        if let Some(client) = client {
            self.pending_release = true;
            self.task(move || {
                let save_error = match patch {
                    Ok(patch) if patch.device.is_some() || !patch.channels.is_empty() => client
                        .set_config(patch.device.as_deref(), &patch.channels)
                        .err()
                        .map(|error| format!("Names were not saved: {error}")),
                    Err(error) => Some(error),
                    _ => None,
                };
                // Always release channels even when storage is unavailable.
                client.release()?;
                client.info().map(|info| Reply::Released(info, save_error))
            });
        }
    }

    fn apply_snapshot(&mut self, mut snapshot: Snapshot) {
        snapshot.channels.retain(|ch, _| self.selected.contains(ch));
        self.status = snapshot.positions();
        self.state = snapshot;
        self.last_update = Some(Instant::now());
        self.next_refresh = Instant::now() + Duration::from_secs(1);
    }

    fn refresh(&mut self) {
        if self.demo {
            self.apply_snapshot(Snapshot::demo(&self.demo_status));
        } else if let Some(client) = self.client.clone() {
            self.task(move || {
                client.renew()?;
                let state = client.snapshot()?;
                let info = client.info()?;
                Ok(Reply::Refreshed(state, info))
            });
            self.refreshing = true;
        }
    }

    fn operate(&mut self, operation: Operation, channels: Vec<u8>) {
        if !self.connected()
            || self.pending.is_some()
            || channels.is_empty()
            || channels.iter().any(|ch| !self.selected.contains(ch))
        {
            return;
        }
        if self.demo {
            for channel in &channels {
                if let Some(angle) = self.demo_status.get_mut(channel) {
                    *angle = match operation {
                        Operation::Open => 90,
                        Operation::Close => 0,
                        Operation::Toggle => {
                            if *angle == 0 {
                                90
                            } else {
                                0
                            }
                        }
                    };
                }
            }
            self.apply_snapshot(Snapshot::demo(&self.demo_status));
            let description = format!(
                "SIM: {operation:?} accepted for {} channel(s)",
                channels.len()
            );
            self.last_command = Some(description.clone());
            self.record(description);
            self.last_update = Some(Instant::now());
            return;
        }
        if let Some(client) = self.client.clone() {
            // A cached position must not look settled after a newer command.
            // Only the next STATE response can confirm its commanded endpoint.
            for channel in &channels {
                if let Some(state) = self.state.channels.get_mut(channel) {
                    state.busy = true;
                    state.target = match operation {
                        Operation::Open => state.open_angle,
                        Operation::Close => state.close_angle,
                        Operation::Toggle => {
                            if state.target == state.close_angle {
                                state.open_angle
                            } else {
                                state.close_angle
                            }
                        }
                    };
                }
            }
            self.task(move || {
                let total = channels.len();
                client.operate_many(operation, &channels)?;
                Ok(Reply::Accepted(format!(
                    "{operation:?}: {total} channel(s) accepted"
                )))
            });
        }
    }

    fn receive(&mut self) {
        let Some(receiver) = &self.pending else {
            return;
        };
        let result = match receiver.try_recv() {
            Ok(result) => result,
            Err(mpsc::TryRecvError::Empty) => return,
            Err(mpsc::TryRecvError::Disconnected) => {
                Err("Background task stopped unexpectedly".into())
            }
        };
        self.pending = None;
        self.refreshing = false;
        let api_error = result.as_ref().err().cloned();
        match result {
            Ok(Reply::Devices(devices, info)) => {
                self.device_info = info;
                self.message = if devices.is_empty() {
                    "No Pico W found. Start its server; check Wi-Fi or inspect the IP over USB."
                        .into()
                } else {
                    format!(
                        "Found {} device(s). Select the intended Pico W, then connect.",
                        devices.len()
                    )
                };
                self.record(format!("Discovery complete: {} device(s)", devices.len()));
                self.devices = devices;
                if self.info.is_none()
                    && let Some(device) = self
                        .devices
                        .iter()
                        .find(|device| {
                            self.preferences_candidate.last_device.as_deref()
                                == Some(device.id.as_str())
                        })
                        .cloned()
                {
                    self.host = device.address.ip().to_string();
                    self.port = device.address.port();
                    if let Some(info) = self.device_info.get(&device.id).cloned() {
                        self.restore_channels(&info);
                    }
                }
                if let Some(info) = self
                    .devices
                    .iter()
                    .find(|device| {
                        device.address.ip().to_string() == self.host
                            && device.address.port() == self.port
                    })
                    .and_then(|device| self.device_info.get(&device.id))
                    .cloned()
                {
                    self.selected.retain(|ch| {
                        info.channels
                            .iter()
                            .any(|entry| entry.id == *ch && !entry.locked)
                    });
                    self.device_label = info.label.clone();
                    self.info = Some(info);
                }
            }
            Ok(Reply::Info(info)) => {
                if self.info.is_none() {
                    self.restore_channels(&info);
                }
                self.selected.retain(|ch| {
                    info.channels
                        .iter()
                        .any(|entry| entry.id == *ch && !entry.locked)
                });
                self.update_info(info);
                self.message.clear();
            }
            Ok(Reply::Connected(client, snapshot, info)) => {
                self.update_info(info);
                self.client = Some(client);
                self.apply_snapshot(snapshot);
                self.message.clear();
            }
            Ok(Reply::Released(info, error)) => {
                self.pending_release = false;
                if let Some(error) = error {
                    self.config_error = error;
                } else {
                    self.dirty_device = false;
                    self.dirty_channels.clear();
                    self.config_due = None;
                }
                self.update_info(info);
            }
            Ok(Reply::Refreshed(status, info)) => {
                self.apply_snapshot(status);
                self.update_info(info);
                self.message.clear();
            }
            Ok(Reply::Config(result)) => {
                let patch = self.config_pending.take().unwrap_or_default();
                match result {
                    Ok(info) => self.acknowledge_config(&patch, info),
                    Err(error) => self.config_error = error,
                }
            }
            Ok(Reply::Accepted(description)) => {
                self.record(description.clone());
                self.last_command = Some(description);
                self.next_refresh = Instant::now();
            }
            Err(error) => {
                self.queued_toggle = None;
                self.pending_release = false;
                self.record(format!("ERROR: {error}"));
                self.error = true;
                self.message = error;
                self.status.clear();
                self.state = Snapshot::default();
                if let Some(client) = self.client.take() {
                    std::thread::spawn(move || {
                        let _ = client.release();
                    });
                }
                self.last_update = None;
            }
        }
        if let Some(id) = self.pending_api_job.take() {
            let result = api_error.map_or_else(
                || Ok(json!({"accepted":true,"completion":"command_acknowledgement","snapshot":self.snapshot_json(),"devices":self.devices_json()})),
                |error| Err(ApiError::new("transport", error)),
            );
            self.control.complete(&id, result);
        }
        if let Some(channel) = self.queued_toggle.take()
            && self.connected()
            && !self.control.owned()
        {
            self.operate(Operation::Toggle, vec![channel]);
        }
    }

    fn devices_json(&self) -> Value {
        json!(
            self.devices
                .iter()
                .map(|device| json!({"id":device.id,"address":device.address.to_string(),"label":self.device_info.get(&device.id).map(|info| &info.label),"channels":self.device_info.get(&device.id).map(|info| &info.channels)}))
                .collect::<Vec<_>>()
        )
    }

    fn ordered_channels(&self) -> Vec<u8> {
        let mut channels: Vec<_> = self.status.keys().copied().collect();
        if self.order == Order::Descending {
            channels.reverse();
        }
        channels
    }

    fn snapshot_json(&self) -> Value {
        let channels: serde_json::Map<String, Value> = self
            .state
            .channels
            .iter()
            .map(|(&channel, state)| {
                let mut value = serde_json::to_value(state).expect("channel state is serializable");
                value["state"] = json!(state.name());
                value["label"] = json!(
                    self.info
                        .as_ref()
                        .and_then(|info| info.channels.iter().find(|entry| entry.id == channel))
                        .map(|entry| entry.label.as_str())
                );
                (channel.to_string(), value)
            })
            .collect();
        json!({"connected":self.connected() && self.last_update.is_some(),"demo":self.demo,
            "layout":self.layout,"order":self.order,"display_order":self.ordered_channels(),"host":self.host,"port":self.port,"busy":self.pending.is_some(),
            "owner":self.control.label(),"device_label":self.info.as_ref().map(|info|info.label.as_str()),"selected_channels":self.selected,"channels":channels,"devices":self.devices_json(),
            "message":self.message,"last_command":self.last_command,
            "state_semantics":"commanded_not_sensor_verified"})
    }

    fn process_api(&mut self) {
        if self.control.expire() {
            self.record("External control expired; holding last requested state");
        }
        let requests: Vec<_> = self
            .api
            .as_ref()
            .map(|api| api.requests.try_iter().take(8).collect())
            .unwrap_or_default();
        for request in requests {
            let original = request.body.clone();
            let value = if request.deadline < Instant::now() {
                let native = response(Err(ApiError::new(
                    "timeout",
                    "Request expired before execution; no new action started",
                )));
                if is_common(&original) { common_response(&original, native) } else { native }
            } else {
                match prepare_common(&request.body) {
                    Err(error) => error,
                    Ok(mut native) => {
                        // The shared normalizer uses private control_* names for
                        // adapters; map the read-only aliases to Shutter's
                        // existing native handlers without changing mutations.
                        if let Some(method) = native.get("_control_method").and_then(Value::as_str) {
                            let mapped = match method {
                                "describe" => Some("capabilities"),
                                "status" => Some("status"),
                                "config" => Some("config"),
                                "result" => Some("result"),
                                _ => None,
                            };
                            if let Some(mapped) = mapped {
                                native["method"] = json!(mapped);
                                native["action"] = json!(mapped);
                            }
                        }
                        let native_response = response(self.api_request(&native));
                        if is_common(&original) { common_response(&original, native_response) } else { native_response }
                    }
                }
            };
            let _ = request.reply.send(value);
        }
    }

    fn api_request(&mut self, body: &Value) -> Result<Value, ApiError> {
        let method = body
            .get("method")
            .or_else(|| body.get("action"))
            .and_then(Value::as_str)
            .ok_or_else(|| ApiError::new("invalid_request", "method must be a string"))?;
        match method {
            "capabilities" => {
                return Ok(
                    json!({"protocol":2,"app":"kohdalab-shutter","version":env!("CARGO_PKG_VERSION"),
                "application":"kohdalab-shutter","control_protocol":1,
                "methods":["control.describe","control.status","control.config","control.acquire","control.heartbeat","control.release","control.result","control.discover","control.connect","control.disconnect","control.open","control.close","control.toggle","control.open_all","control.close_all","control.set_layout","control.set_order"],
                "safety":{"supports_ownership":true,"exclusive_control":true,"physical_auto_connect":false,"simulation_required_for_tests":true,"stop_requires_lease":true},
                "actions":["capabilities","status","config","acquire","heartbeat","release","result","discover","connect","disconnect","open","close","toggle","open_all","close_all","set_layout","set_order"],
                "channel_selection_required":true,"channel_lock_scope":"pico_channel","pico_lease_timeout_s":15,"lease_timeout_s":10,"release_policy":"hold_last_state","job_completion":"command_acknowledgement",
                "state_semantics":"commanded_not_sensor_verified","receipt_limit":64,"action_id_limit":4096,
                "supports_ownership":true,"heartbeat_seconds":1,"timeout_seconds":10}),
                );
            }
            "status" => return Ok(self.snapshot_json()),
            "config" => {
                return Ok(
                    json!({"host":self.host,"port":self.port,"broadcast":self.broadcast,"layout":self.layout,"order":self.order,"demo":self.demo}),
                );
            }
            "result" => {
                let mut receipt = self.control.result(string(body, "id")?)?;
                receipt["job_id"] = receipt["id"].clone();
                receipt["terminal"] = json!(matches!(receipt["status"].as_str(), Some("completed" | "stopped" | "error")));
                receipt["cleanup"] = json!(if receipt["status"] == "completed" {"not_required"} else {"unknown"});
                receipt["linked_job_id"] = Value::Null;
                return Ok(receipt);
            }
            "acquire" => {
                let mut lease = self.control.acquire(body, self.pending.is_some())?;
                lease["client_id"] = body.get("client").cloned().unwrap_or(Value::Null);
                lease["heartbeat_seconds"] = json!(1);
                lease["timeout_seconds"] = json!(10);
                return Ok(lease);
            }
            "heartbeat" => {
                self.control.authorize(body)?;
                return Ok(json!({"alive":true}));
            }
            "release" => {
                let mut released = self.control.release(body)?;
                released["cleanup"] = json!("not_required");
                return Ok(released);
            }
            "discover" | "connect" | "disconnect" | "open" | "close" | "toggle" | "open_all"
            | "close_all" | "set_layout" | "set_order" => {}
            _ => return Err(ApiError::new("unsupported", "Unknown API method")),
        }
        self.control.authorize(body)?;
        if let Some(receipt) = self.control.cached(body, method)? {
            let mut receipt = receipt;
            receipt["job_id"] = receipt["id"].clone();
            receipt["terminal"] = json!(matches!(receipt["status"].as_str(), Some("completed" | "stopped" | "error")));
            receipt["cleanup"] = json!(if receipt["status"] == "completed" {"not_required"} else {"unknown"});
            receipt["linked_job_id"] = Value::Null;
            return Ok(receipt);
        }
        if self.pending.is_some() {
            return Err(ApiError::new(
                "busy",
                "Wait for the current GUI job or refresh",
            ));
        }
        let mut action = None;
        let mut channels = Vec::new();
        let mut connection = None;
        let mut layout = None;
        let mut order = None;
        match method {
            "connect" => {
                if body.get("host").is_some_and(|v| !v.is_null())
                    && body.get("device_id").is_some_and(|v| !v.is_null())
                {
                    return Err(ApiError::new(
                        "invalid_request",
                        "Choose host or device_id, not both",
                    ));
                }
                if self.connected() {
                    return Err(ApiError::new(
                        "busy",
                        "Disconnect before changing the Pico connection",
                    ));
                }
                let (host, default_port) =
                    if let Some(id) = body.get("device_id").filter(|value| !value.is_null()) {
                        let id = id.as_str().ok_or_else(|| {
                            ApiError::new("invalid_request", "device_id must be a string")
                        })?;
                        let device = discovery::select_device(&self.devices, Some(id))
                            .map_err(|error| ApiError::new("not_found", error.to_string()))?;
                        (device.address.ip().to_string(), device.address.port())
                    } else if let Some(host) = body.get("host").filter(|value| !value.is_null()) {
                        (
                            host.as_str()
                                .filter(|host| !host.trim().is_empty())
                                .ok_or_else(|| {
                                    ApiError::new("invalid_request", "host must be non-empty")
                                })?
                                .to_owned(),
                            DEFAULT_PORT,
                        )
                    } else if !self.host.trim().is_empty() {
                        (self.host.clone(), self.port)
                    } else {
                        let device = discovery::select_device(&self.devices, None)
                            .map_err(|error| ApiError::new("not_found", error.to_string()))?;
                        (device.address.ip().to_string(), device.address.port())
                    };
                let port = body.get("port").map_or(Ok(default_port), |value| {
                    value
                        .as_u64()
                        .filter(|port| (1..=65535).contains(port))
                        .map(|port| port as u16)
                        .ok_or_else(|| ApiError::new("invalid_request", "port must be in 1..65535"))
                })?;
                let selection = if let Some(value) = body.get("channels") {
                    let list = value
                        .as_array()
                        .filter(|list| !list.is_empty())
                        .ok_or_else(|| {
                            ApiError::new("invalid_request", "channels must be a nonempty array")
                        })?;
                    let mut selection = BTreeSet::new();
                    for value in list {
                        let ch = value.as_u64().filter(|ch| *ch < 16).ok_or_else(|| {
                            ApiError::new(
                                "invalid_request",
                                "channels must contain channel numbers in 0..15",
                            )
                        })? as u8;
                        if !selection.insert(ch) {
                            return Err(ApiError::new("invalid_request", "Duplicate channel"));
                        }
                    }
                    selection
                } else if self.demo {
                    self.devices
                        .iter()
                        .find(|device| {
                            device.address.ip().to_string() == host && device.address.port() == port
                        })
                        .and_then(|device| self.device_info.get(&device.id))
                        .map_or_else(
                            || (0..4).collect(),
                            |info| {
                                info.channels
                                    .iter()
                                    .filter(|ch| !ch.locked)
                                    .map(|ch| ch.id)
                                    .collect()
                            },
                        )
                } else {
                    return Err(ApiError::new(
                        "invalid_request",
                        "Select channels before connecting",
                    ));
                };
                connection = Some((host, port, selection));
            }
            "discover" => {
                if self.connected() {
                    return Err(ApiError::new("busy", "Disconnect before searching"));
                }
                if !self.demo && self.broadcast.parse::<Ipv4Addr>().is_err() {
                    return Err(ApiError::new(
                        "invalid_request",
                        "Invalid broadcast address",
                    ));
                }
            }
            "open" | "close" | "toggle" | "open_all" | "close_all" => {
                if !self.connected() || self.status.is_empty() {
                    return Err(ApiError::new(
                        "disconnected",
                        "Connect and read channels before sending an action",
                    ));
                }
                action = Some(match method {
                    "open" | "open_all" => Operation::Open,
                    "close" | "close_all" => Operation::Close,
                    _ => Operation::Toggle,
                });
                if method.ends_with("_all") {
                    channels = self.status.keys().copied().collect();
                } else {
                    let channel = body["channel"]
                        .as_u64()
                        .filter(|channel| *channel < 16)
                        .ok_or_else(|| {
                            ApiError::new("invalid_request", "channel must be an integer in 0..15")
                        })? as u8;
                    if !self.status.contains_key(&channel) {
                        return Err(ApiError::new(
                            "invalid_request",
                            "Channel is not reported by this Pico",
                        ));
                    }
                    channels.push(channel);
                }
            }
            "set_layout" => {
                layout = Some(match string(body, "layout")? {
                    "horizontal" => Layout::Horizontal,
                    "vertical" => Layout::Vertical,
                    _ => {
                        return Err(ApiError::new(
                            "invalid_request",
                            "layout must be horizontal or vertical",
                        ));
                    }
                })
            }
            "set_order" => {
                order = Some(match string(body, "order")? {
                    "ascending" => Order::Ascending,
                    "descending" => Order::Descending,
                    _ => {
                        return Err(ApiError::new(
                            "invalid_request",
                            "order must be ascending or descending",
                        ));
                    }
                });
            }
            _ => {}
        }
        let receipt = self.control.begin(body, method)?;
        let id = receipt["id"].as_str().expect("job ID").to_owned();
        self.pending_api_job = Some(id.clone());
        if let Some((host, port, selection)) = connection {
            self.selected = selection;
            self.host = host;
            self.port = port;
            self.info = self
                .devices
                .iter()
                .find(|device| {
                    device.address.ip().to_string() == self.host
                        && device.address.port() == self.port
                })
                .and_then(|device| self.device_info.get(&device.id))
                .cloned();
            self.connect();
        } else if let Some(operation) = action {
            self.operate(operation, channels);
        } else if let Some(layout) = layout {
            self.layout = layout;
        } else if let Some(order) = order {
            self.order = order;
        } else if method == "discover" {
            self.find();
        } else if method == "disconnect" {
            self.disconnect();
        }
        if self.pending.is_none() {
            self.pending_api_job = None;
            self.control.complete(&id,Ok(json!({"accepted":true,"completion":"command_acknowledgement","snapshot":self.snapshot_json(),"devices":self.devices_json()})));
        }
        let mut receipt = self.control.result(&id)?;
        receipt["job_id"] = receipt["id"].clone();
        receipt["terminal"] = json!(matches!(receipt["status"].as_str(), Some("completed" | "stopped" | "error")));
        receipt["cleanup"] = json!(if receipt["status"] == "completed" {"not_required"} else {"unknown"});
        receipt["linked_job_id"] = Value::Null;
        Ok(receipt)
    }

    fn connection_panel(&mut self, ui: &mut egui::Ui) {
        let manual = self.pending.is_none() && !self.control.owned();
        ui.horizontal(|ui| {
            ui.label(RichText::new("Connect").size(20.0).strong());
            ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                if ui
                    .add_enabled(
                        manual,
                        egui::Button::new("Find Pico W").min_size(Vec2::new(96.0, 28.0)),
                    )
                    .clicked()
                {
                    self.find();
                }
            });
        });
        ui.add_space(12.0);
        ui.columns(2, |columns| {
            columns[0].horizontal(|ui| {
                ui.set_min_height(30.0);
                ui.label(RichText::new("Controller").small().color(MUTED));
            });
            columns[0].add_space(6.0);
            let mut chosen = None;
            egui::ScrollArea::vertical()
                .id_salt("controllers")
                .max_height(200.0)
                .show(&mut columns[0], |ui| {
                    ui.set_min_height(180.0);
                    for device in &self.devices {
                        let label = self
                            .device_info
                            .get(&device.id)
                            .map_or("Pico W", |info| info.label.as_str());
                        let active = self.host == device.address.ip().to_string()
                            && self.port == device.address.port();
                        if ui
                            .add_enabled(
                                manual,
                                egui::Button::new(format!("{label}\n{}", device.address.ip()))
                                    .selected(active)
                                    .wrap()
                                    .min_size(Vec2::new(ui.available_width(), 50.0)),
                            )
                            .on_hover_text(format!("{} · {}", device.id, device.address))
                            .clicked()
                        {
                            chosen = Some(device.clone());
                        }
                    }
                    if self.devices.is_empty() {
                        ui.label(
                            RichText::new(if self.pending.is_some() {
                                "Searching…"
                            } else {
                                "No controllers found"
                            })
                            .small()
                            .color(MUTED),
                        );
                    }
                });
            if let Some(device) = chosen {
                self.select_device(&device);
            }
            columns[1].horizontal(|ui| {
                ui.set_min_height(30.0);
                ui.label(RichText::new("Channels").small().color(MUTED));
                if ui
                    .add_enabled(
                        manual && self.info.is_some(),
                        egui::Button::new("Refresh").small(),
                    )
                    .clicked()
                    && !self.demo
                    && let Ok(client) = self.endpoint()
                {
                    self.task(move || client.info().map(Reply::Info));
                }
            });
            columns[1].add_space(6.0);
            egui::ScrollArea::vertical()
                .id_salt("channel-selection")
                .max_height(200.0)
                .show(&mut columns[1], |ui| {
                    ui.set_min_height(180.0);
                    if let Some(info) = self.info.clone() {
                        for channel in info.channels {
                            let mut selected = self.selected.contains(&channel.id);
                            ui.horizontal(|ui| {
                                if ui
                                    .add_enabled(
                                        manual && !channel.locked,
                                        egui::Checkbox::new(
                                            &mut selected,
                                            format!("CH{:02}", channel.id),
                                        ),
                                    )
                                    .changed()
                                {
                                    if selected {
                                        self.selected.insert(channel.id);
                                    } else {
                                        self.selected.remove(&channel.id);
                                    }
                                }
                                ui.add(
                                    egui::Label::new(
                                        RichText::new(&channel.label).color(if channel.locked {
                                            MUTED
                                        } else {
                                            TEXT
                                        }),
                                    )
                                    .truncate(),
                                )
                                .on_hover_text(&channel.label);
                            });
                            if channel.locked {
                                ui.label(RichText::new("In use").small().color(ORANGE));
                            }
                            ui.add_space(5.0);
                        }
                    } else {
                        ui.label(RichText::new("Select a controller").small().color(MUTED));
                    }
                });
        });
        ui.add_space(10.0);
        ui.separator();
        ui.add_space(8.0);
        ui.horizontal(|ui| {
            let (rect, _) = ui.allocate_exact_size(Vec2::splat(16.0), egui::Sense::hover());
            if self.pending.is_some() {
                egui::Spinner::new().paint_at(ui, rect);
            }
            ui.label(
                RichText::new(format!("{} selected", self.selected.len()))
                    .small()
                    .color(MUTED),
            );
            ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                if ui
                    .add_enabled(
                        manual && self.info.is_some() && !self.selected.is_empty(),
                        egui::Button::new("Connect")
                            .fill(BLUE)
                            .min_size(Vec2::new(104.0, 30.0)),
                    )
                    .clicked()
                {
                    self.connect();
                }
            });
        });
        if !self.config_error.is_empty() {
            ui.label(RichText::new(&self.config_error).small().color(ORANGE));
        }
        if !self.preferences_error.is_empty() {
            ui.label(RichText::new(&self.preferences_error).small().color(ORANGE));
        }
        if self.error {
            ui.label(RichText::new(&self.message).small().color(RED));
        }
        ui.add_space(8.0);
        ui.collapsing("Settings", |ui| {
            ui.add_enabled_ui(manual, |ui| {
                ui.horizontal(|ui| {
                    ui.label("Host");
                    let host_changed = ui
                        .add(egui::TextEdit::singleline(&mut self.host).desired_width(180.0))
                        .changed();
                    let port_changed = ui
                        .add(egui::DragValue::new(&mut self.port).range(1..=65535))
                        .changed();
                    if host_changed || port_changed {
                        self.dirty_device = false;
                        self.dirty_channels.clear();
                        self.channel_labels.clear();
                        self.draft_device = None;
                        self.config_due = None;
                        self.info = None;
                        self.selected.clear();
                        self.device_label.clear();
                    }
                    if ui.button("Read").clicked() {
                        self.selected.clear();
                        self.info = None;
                        match self.endpoint() {
                            Ok(client) => self.task(move || client.info().map(Reply::Info)),
                            Err(error) => {
                                self.error = true;
                                self.message = error.to_string();
                            }
                        }
                    }
                });
                ui.horizontal(|ui| {
                    ui.label("Broadcast");
                    ui.text_edit_singleline(&mut self.broadcast);
                });
                self.automation_settings(ui);
            });
        });
    }

    fn automation_settings(&mut self, ui: &mut egui::Ui) {
        let mut enabled = self.api_enabled;
        if ui
            .add_enabled(
                !self.control.owned() && self.pending_api_job.is_none(),
                egui::Checkbox::new(&mut enabled, "Local control API"),
            )
            .changed()
        {
            self.api_enabled = enabled;
            self.api_error.clear();
            if enabled {
                match remote::Server::start(self.api_directory.clone()) {
                    Ok(server) => self.api = Some(server),
                    Err(error) => {
                        self.api_error = format!("Local API could not start: {error}");
                    }
                }
            } else {
                self.api = None;
                self.control.revoke();
            }
        }
        if !self.api_error.is_empty() {
            ui.label(RichText::new(&self.api_error).small().color(ORANGE));
        }
        if let Some(label) = self.control.label() {
            ui.label(format!("Controlled by {label}"));
            if ui
                .add_enabled(self.pending.is_none(), egui::Button::new("Take control"))
                .clicked()
            {
                self.control.revoke();
            }
        }
    }

    fn init_preferences(&mut self, path: Option<PathBuf>) {
        self.preferences_path = path;
        let Some(path) = &self.preferences_path else {
            return;
        };
        match kohdalab_shutter::preferences::Preferences::load(path) {
            Ok(preferences) => {
                self.layout = if preferences.layout == "vertical" {
                    Layout::Vertical
                } else {
                    Layout::Horizontal
                };
                self.order = if preferences.order == "descending" {
                    Order::Descending
                } else {
                    Order::Ascending
                };
                self.broadcast = preferences.broadcast.clone();
                self.host = preferences.manual_host.clone();
                self.port = preferences.manual_port;
                self.api_enabled |= preferences.local_control_api;
                if self.api_enabled && self.api.is_none() {
                    match remote::Server::start(self.api_directory.clone()) {
                        Ok(server) => self.api = Some(server),
                        Err(error) => {
                            self.api_error = format!("Local API could not start: {error}")
                        }
                    }
                }
                self.preferences_saved = preferences.clone();
                self.preferences_candidate = preferences;
            }
            Err(error) => {
                self.preferences_blocked = true;
                self.preferences_error = format!("Settings could not be loaded: {error}");
            }
        }
    }

    fn current_preferences(&self) -> kohdalab_shutter::preferences::Preferences {
        let mut value = self.preferences_candidate.clone();
        value.layout = if self.layout == Layout::Vertical {
            "vertical"
        } else {
            "horizontal"
        }
        .into();
        value.order = if self.order == Order::Descending {
            "descending"
        } else {
            "ascending"
        }
        .into();
        value.local_control_api = self.api_enabled;
        value.broadcast = self.broadcast.clone();
        value.manual_host = self.host.clone();
        value.manual_port = self.port;
        if let Some(info) = &self.info {
            value.last_device = Some(info.device_id.clone());
            let device = value.devices.entry(info.device_id.clone()).or_default();
            device.selected_channels = self.selected.iter().copied().collect();
            // Cache only committed Pico labels, never an unacknowledged edit.
            device.label = info.label.clone();
            device.channel_labels = info
                .channels
                .iter()
                .map(|ch| (ch.id, ch.label.clone()))
                .collect();
        }
        value
    }

    fn persist_preferences(&mut self, force: bool) {
        if self.preferences_path.is_none() || self.preferences_blocked {
            return;
        }
        let value = self.current_preferences();
        if value != self.preferences_candidate {
            self.preferences_candidate = value;
            self.preferences_due = Some(Instant::now() + Duration::from_millis(700));
        }
        if self.preferences_candidate == self.preferences_saved {
            self.preferences_due = None;
            return;
        }
        if !force && self.preferences_due.is_none_or(|due| Instant::now() < due) {
            return;
        }
        self.preferences_due = None;
        match self
            .preferences_candidate
            .save(self.preferences_path.as_ref().unwrap())
        {
            Ok(()) => {
                self.preferences_saved = self.preferences_candidate.clone();
                self.preferences_error.clear();
            }
            Err(error) => {
                self.preferences_error = format!("PC settings were not saved: {error}");
            }
        }
    }

    fn restore_channels(&mut self, info: &ControllerInfo) {
        if let Some(device) = self.preferences_candidate.devices.get(&info.device_id) {
            self.selected = device
                .selected_channels
                .iter()
                .filter(|ch| {
                    info.channels
                        .iter()
                        .any(|entry| entry.id == **ch && !entry.locked)
                })
                .copied()
                .collect();
        }
    }

    fn settings_panel(&mut self, ctx: &egui::Context) {
        if !self.settings_open {
            return;
        }
        let mut open = true;
        egui::Window::new("Settings")
            .open(&mut open)
            .anchor(egui::Align2::CENTER_CENTER, Vec2::ZERO)
            .collapsible(false)
            .resizable(false)
            .default_width(390.0)
            .show(ctx, |ui| {
                egui::ScrollArea::vertical()
                    .max_height(460.0)
                    .show(ui, |ui| {
                        ui.add_enabled_ui(!self.control.owned(), |ui| {
                            ui.label(RichText::new("Controller").small().color(MUTED));
                            ui.horizontal(|ui| {
                                ui.label("Pico");
                                if ui
                                    .add(
                                        egui::TextEdit::singleline(&mut self.device_label)
                                            .char_limit(32)
                                            .desired_width(300.0),
                                    )
                                    .changed()
                                {
                                    self.dirty_device = true;
                                    self.changed_label();
                                }
                            });
                            ui.add_space(10.0);
                            ui.separator();
                            ui.add_space(6.0);
                            ui.horizontal(|ui| {
                                ui.label("Layout");
                                ui.selectable_value(
                                    &mut self.layout,
                                    Layout::Horizontal,
                                    "Horizontal",
                                );
                                ui.selectable_value(&mut self.layout, Layout::Vertical, "Vertical");
                            });
                            ui.horizontal(|ui| {
                                ui.label("Order");
                                ui.selectable_value(&mut self.order, Order::Ascending, "CH ↑");
                                ui.selectable_value(&mut self.order, Order::Descending, "CH ↓");
                            });
                        });
                        ui.add_space(10.0);
                        ui.separator();
                        ui.add_space(6.0);
                        self.automation_settings(ui);
                        ui.add_space(10.0);
                        if !self.config_error.is_empty() {
                            ui.label(RichText::new(&self.config_error).small().color(ORANGE));
                            if ui.button("Retry").clicked() {
                                self.changed_label();
                            }
                        }
                        if !self.preferences_error.is_empty() {
                            ui.label(RichText::new(&self.preferences_error).small().color(ORANGE));
                            if !self.preferences_blocked && ui.button("Retry PC save").clicked() {
                                self.persist_preferences(true);
                            }
                        }
                        if self.config_error.is_empty() && self.preferences_error.is_empty() {
                            let pending = self.dirty_device
                                || !self.dirty_channels.is_empty()
                                || self.config_pending.is_some()
                                || self.preferences_due.is_some()
                                || (self.preferences_path.is_some()
                                    && self.current_preferences() != self.preferences_saved);
                            ui.label(
                                RichText::new(if pending { "Saving…" } else { "Saved" })
                                    .small()
                                    .color(MUTED),
                            );
                        }
                    });
            });
        self.settings_open = open;
    }

    fn commit_channel_name(&mut self, channel: u8, text: &str) -> bool {
        let value = text.trim();
        if value.is_empty()
            || value.chars().count() > 32
            || value.len() > 96
            || value
                .chars()
                .any(|ch| ch.is_control() || matches!(ch, '\u{2028}' | '\u{2029}'))
        {
            self.config_error = "Name is empty or too long.".into();
            return false;
        }
        if !self.selected.contains(&channel) || !self.connected() || self.control.owned() {
            return false;
        }
        if value != self.channel_label(channel) {
            self.channel_labels.insert(channel, value.into());
            self.dirty_channels.insert(channel);
            self.changed_label();
            self.config_due = Some(Instant::now());
        }
        true
    }

    fn inline_channel_name(&mut self, ui: &mut egui::Ui, channel: u8) {
        let current = self.channel_label(channel);
        let key = (
            self.info
                .as_ref()
                .map_or(self.host.as_str(), |info| info.device_id.as_str())
                .to_owned(),
            channel,
        );
        if self.active_name.as_ref() != Some(&key) {
            self.name_edits.insert(channel, current.clone());
        }
        let response = ui
            .add_enabled(
                !self.control.owned(),
                egui::TextEdit::singleline(
                    self.name_edits.entry(channel).or_insert(current.clone()),
                )
                .id_salt(("channel-name", channel, self.host.as_str(), self.port))
                .desired_width(ui.available_width())
                .char_limit(32)
                .horizontal_align(egui::Align::Center),
            )
            .on_hover_text("Edit name · Enter to apply");
        if response.gained_focus() {
            self.active_name = Some(key.clone());
        }
        if response.has_focus() && ui.input(|input| input.key_pressed(egui::Key::Escape)) {
            response.surrender_focus();
            self.active_name = None;
            self.name_edits.insert(channel, current);
            return;
        }
        if response.lost_focus() {
            if self.active_name.as_ref() == Some(&key) {
                self.active_name = None;
            }
            if ui.input(|input| input.key_pressed(egui::Key::Enter)) {
                let value = self.name_edits.get(&channel).cloned().unwrap_or_default();
                self.commit_channel_name(channel, &value);
            } else {
                self.name_edits.insert(channel, current);
            }
        }
    }

    fn request_toggle(&mut self, channel: u8) {
        if !self.connected()
            || !self.selected.contains(&channel)
            || self.control.owned()
            || self.queued_toggle.is_some()
        {
            return;
        }
        if self.pending.is_some() {
            if self.refreshing {
                self.queued_toggle = Some(channel);
            }
        } else {
            self.operate(Operation::Toggle, vec![channel]);
        }
    }

    fn channels_panel(&mut self, ui: &mut egui::Ui) {
        let enabled = self.connected()
            && (self.pending.is_none() || self.refreshing)
            && self.queued_toggle.is_none()
            && !self.control.owned();
        let channels = self.ordered_channels();
        let device_id = self
            .info
            .as_ref()
            .map_or("", |info| info.device_id.as_str())
            .to_owned();
        let mut toggle = None;
        egui::ScrollArea::both().id_salt("shutters").show(ui, |ui| {
            if self.layout == Layout::Horizontal {
                let total = channels.len() as f32 * 166.0 - 10.0;
                let inset = ((ui.available_width() - total) * 0.5).max(0.0);
                ui.horizontal_top(|ui| {
                    ui.spacing_mut().item_spacing.x = 10.0;
                    if inset > 0.0 {
                        ui.add_space(inset);
                    }
                    for channel in channels {
                        ui.push_id((&device_id, channel), |ui| {
                            card_frame().inner_margin(12).show(ui, |ui| {
                                ui.vertical(|ui| {
                                    ui.set_width(130.0);
                                    ui.label(
                                        RichText::new(format!("CH{channel:02}"))
                                            .strong()
                                            .size(13.0),
                                    );
                                    self.inline_channel_name(ui, channel);
                                    ui.add_space(6.0);
                                    let state = self
                                        .state
                                        .channels
                                        .get(&channel)
                                        .map_or("Unknown", |state| state.name());
                                    let response = ui
                                        .vertical_centered(|ui| {
                                            ui.add_enabled_ui(enabled, |ui| {
                                                shutter_window(ui, state, 0.68)
                                            })
                                            .inner
                                        })
                                        .inner;
                                    response.widget_info(|| {
                                        egui::WidgetInfo::labeled(
                                            egui::WidgetType::Button,
                                            enabled,
                                            format!("Toggle CH{channel:02}: {state}"),
                                        )
                                    });
                                    if response.clicked() {
                                        toggle = Some(channel);
                                    }
                                });
                            });
                        });
                    }
                });
            } else {
                for channel in channels {
                    ui.push_id((&device_id, channel), |ui| {
                        card_frame().inner_margin(10).show(ui, |ui| {
                            ui.set_min_width(ui.available_width().max(280.0));
                            ui.horizontal(|ui| {
                                ui.vertical(|ui| {
                                    ui.set_width((ui.available_width() - 120.0).max(130.0));
                                    ui.label(
                                        RichText::new(format!("CH{channel:02}"))
                                            .strong()
                                            .size(13.0),
                                    );
                                    self.inline_channel_name(ui, channel);
                                });
                                let state = self
                                    .state
                                    .channels
                                    .get(&channel)
                                    .map_or("Unknown", |state| state.name());
                                let response = ui
                                    .add_enabled_ui(enabled, |ui| shutter_window(ui, state, 0.50))
                                    .inner;
                                response.widget_info(|| {
                                    egui::WidgetInfo::labeled(
                                        egui::WidgetType::Button,
                                        enabled,
                                        format!("Toggle CH{channel:02}: {state}"),
                                    )
                                });
                                if response.clicked() {
                                    toggle = Some(channel);
                                }
                            });
                        });
                    });
                    ui.add_space(6.0);
                }
            }
        });
        if let Some(channel) = toggle {
            self.request_toggle(channel);
        }
    }

    fn header(&mut self, ctx: &egui::Context) {
        let connected = self.connected();
        egui::TopBottomPanel::top("header")
            .exact_height(44.0)
            .show_separator_line(false)
            .frame(
                egui::Frame::new()
                    .fill(PANEL)
                    .inner_margin(egui::Margin::symmetric(12, 7)),
            )
            .show(ctx, |ui| {
                ui.horizontal(|ui| {
                    if connected {
                        status_dot(ui, if self.error { RED } else { TEAL });
                        let label = self
                            .info
                            .as_ref()
                            .map_or(self.device_label.as_str(), |info| info.label.as_str())
                            .to_owned();
                        let problem = !self.config_error.is_empty()
                            || !self.preferences_error.is_empty()
                            || !self.api_error.is_empty();
                        let reserve = if self.demo { 140.0 } else { 110.0 }
                            + if problem { 24.0 } else { 0.0 };
                        let width = (ui.available_width() - reserve).max(80.0);
                        ui.allocate_ui_with_layout(
                            Vec2::new(width, 28.0),
                            egui::Layout::left_to_right(egui::Align::Center),
                            |ui| {
                                ui.set_min_width(width);
                                egui::containers::menu::MenuButton::from_button(
                                    egui::Button::new(
                                        RichText::new(format!("{label}  ▾")).strong().size(13.0),
                                    )
                                    .frame(false)
                                    .truncate(),
                                )
                                .ui(ui, |ui| {
                                    ui.label(RichText::new("Connected").small().color(TEAL));
                                    ui.label(RichText::new(&label).strong());
                                    ui.label(
                                        RichText::new(format!("{}:{}", self.host, self.port))
                                            .small()
                                            .color(MUTED),
                                    );
                                    ui.separator();
                                    if ui
                                        .add_enabled(
                                            self.pending.is_none() && !self.control.owned(),
                                            egui::Button::new("Disconnect"),
                                        )
                                        .clicked()
                                    {
                                        self.disconnect();
                                        ui.close();
                                    }
                                })
                                .0
                                .on_hover_text("Connection options");
                            },
                        );
                    } else {
                        ui.label(RichText::new("KohdaLab Shutter").size(13.0).strong());
                    }
                    ui.label(
                        RichText::new(format!("v{}", env!("CARGO_PKG_VERSION")))
                            .size(10.0)
                            .color(MUTED),
                    );
                    if self.demo {
                        ui.label(RichText::new("Demo").size(10.0).color(ORANGE));
                    }
                    if connected {
                        let (rect, _) =
                            ui.allocate_exact_size(Vec2::splat(14.0), egui::Sense::hover());
                        if self.config_pending.is_some()
                            || self.dirty_device
                            || !self.dirty_channels.is_empty()
                        {
                            egui::Spinner::new().paint_at(ui, rect);
                        }
                        if (!self.config_error.is_empty()
                            || !self.preferences_error.is_empty()
                            || !self.api_error.is_empty())
                            && ui
                                .small_button(RichText::new("!").color(ORANGE))
                                .on_hover_text("Settings need attention")
                                .clicked()
                        {
                            self.settings_open = true;
                        }
                    }
                    if connected {
                        ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                            if ui.button("···").on_hover_text("Settings").clicked() {
                                self.settings_open = true;
                            }
                        });
                    }
                });
            });
    }

    fn desired_size(&self) -> Vec2 {
        if self.settings_open {
            return Vec2::new(560.0, 560.0);
        }
        if !self.connected() {
            return Vec2::new(540.0, 490.0);
        }
        let count = self.status.len().max(1) as f32;
        if self.layout == Layout::Horizontal {
            Vec2::new((count * 166.0 + 26.0).clamp(280.0, 1160.0), 260.0)
        } else {
            Vec2::new(350.0, (count * 98.0 + 68.0).min(820.0))
        }
    }

    fn draw(&mut self, ctx: &egui::Context) {
        let desired = self.desired_size();
        if self.last_size != Some(desired) {
            self.last_size = Some(desired);
            ctx.send_viewport_cmd(egui::ViewportCommand::InnerSize(desired));
            ctx.send_viewport_cmd(egui::ViewportCommand::Title(if self.connected() {
                format!("{} · KohdaLab Shutter", self.device_label)
            } else {
                "Connect · KohdaLab Shutter".into()
            }));
        }
        self.header(ctx);
        egui::CentralPanel::default()
            .frame(
                egui::Frame::new()
                    .fill(BG)
                    .inner_margin(if self.connected() { 12 } else { 20 }),
            )
            .show(ctx, |ui| {
                if self.connected() {
                    self.channels_panel(ui);
                } else {
                    egui::ScrollArea::vertical().show(ui, |ui| self.connection_panel(ui));
                }
            });
        self.settings_panel(ctx);
    }

    fn capture(&mut self, ctx: &egui::Context) {
        if self.screenshot.is_none() {
            return;
        }
        if !self.screenshot_requested && self.started.elapsed() > Duration::from_secs(2) {
            self.screenshot_requested = true;
            ctx.send_viewport_cmd(egui::ViewportCommand::Screenshot(Default::default()));
        }
        for event in ctx.input(|input| input.raw.events.clone()) {
            if let egui::Event::Screenshot { image, .. } = event {
                let path = self.screenshot.as_ref().expect("screenshot configured");
                let bytes = image
                    .pixels
                    .iter()
                    .flat_map(|pixel| pixel.to_array())
                    .collect();
                let result =
                    image::RgbaImage::from_raw(image.width() as u32, image.height() as u32, bytes)
                        .ok_or_else(|| "Invalid screenshot pixels".to_string())
                        .and_then(|buffer| buffer.save(path).map_err(|error| error.to_string()));
                match result {
                    Ok(()) => {
                        self.screenshot_success.store(true, Ordering::Release);
                    }
                    Err(error) => {
                        eprintln!("Screenshot failed: {error}");
                    }
                }
                ctx.send_viewport_cmd(egui::ViewportCommand::Close);
            }
        }
        if self.started.elapsed() > Duration::from_secs(20) {
            eprintln!("Screenshot timed out");
            ctx.send_viewport_cmd(egui::ViewportCommand::Close);
        }
    }
}

impl eframe::App for App {
    fn on_exit(&mut self, _gl: Option<&eframe::glow::Context>) {
        let deadline = Instant::now() + Duration::from_secs(10);
        while self.config_pending.is_some() && self.pending.is_some() && Instant::now() < deadline {
            self.receive();
            if self.pending.is_some() {
                std::thread::sleep(Duration::from_millis(20));
            }
        }
        if self.demo {
            self.config_due = Some(Instant::now());
            self.autosave_labels();
        }
        if let Some(client) = self.client.clone()
            && self.config_pending.is_none()
            && let Ok(patch) = self.label_patch()
            && (patch.device.is_some() || !patch.channels.is_empty())
        {
            match client
                .set_config(patch.device.as_deref(), &patch.channels)
                .and_then(|()| client.info())
            {
                Ok(info) => self.acknowledge_config(&patch, info),
                Err(error) => self.config_error = error.to_string(),
            }
        }
        self.persist_preferences(true);
        if let Some(client) = self.client.take() {
            let _ = client.release();
        }
    }

    fn clear_color(&self, _visuals: &egui::Visuals) -> [f32; 4] {
        BG.to_normalized_gamma_f32()
    }

    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        self.receive();
        self.process_api();
        self.autosave_labels();
        self.persist_preferences(false);
        if self.connected() && self.pending.is_none() && Instant::now() >= self.next_refresh {
            self.refresh();
        }
        self.draw(ctx);
        self.capture(ctx);
        ctx.request_repaint_after(Duration::from_millis(100));
    }
}

fn demo_info(id: &str, index: usize) -> ControllerInfo {
    ControllerInfo {
        protocol: 2,
        device_id: id.into(),
        label: if index == 0 {
            "Optics bench"
        } else {
            "Pump probe"
        }
        .into(),
        lease_ms: 15000,
        channels: (0..4)
            .map(|id| ChannelInfo {
                id,
                label: ["Pump", "Probe", "Reference", "Gate"][id as usize].into(),
                locked: index == 1 && id < 2,
            })
            .collect(),
    }
}

fn demo_devices() -> Vec<Device> {
    vec![
        Device {
            id: "e6614104037b2a21".into(),
            address: "192.0.2.20:12345".parse().unwrap(),
        },
        Device {
            id: "e6614104037b2b92".into(),
            address: "192.0.2.21:12345".parse().unwrap(),
        },
    ]
}

fn card_frame() -> egui::Frame {
    egui::Frame::new()
        .fill(PANEL)
        .corner_radius(10)
        .inner_margin(20)
        .stroke(Stroke::new(1.0_f32, BORDER))
}

fn state_color(name: &str) -> Color32 {
    match name {
        "Open" => TEAL,
        "Close" => RED,
        "Moving" => ORANGE,
        _ => MUTED,
    }
}
fn status_dot(ui: &mut egui::Ui, color: Color32) {
    let (rect, _) = ui.allocate_exact_size(Vec2::splat(10.0), egui::Sense::hover());
    ui.painter().circle_filled(rect.center(), 3.5, color);
}
// Front-facing schematic of commanded state, not a measurement of transmitted light.
fn shutter_window(ui: &mut egui::Ui, state: &str, scale: f32) -> egui::Response {
    let (rect, response) =
        ui.allocate_exact_size(Vec2::new(174.0, 132.0) * scale, egui::Sense::click());
    let painter = ui.painter();
    let centre = rect.center();
    let radius = 48.0 * scale;
    painter.circle_filled(centre, radius + 5.0 * scale, BORDER);
    painter.circle_filled(centre, radius, BG);
    if state == "Open" {
        for (r, alpha) in [(32.0, 9), (27.0, 15), (22.0, 25)] {
            painter.circle_filled(
                centre,
                r * scale,
                Color32::from_rgba_unmultiplied(63, 215, 194, alpha),
            );
        }
        painter.circle_filled(centre, 17.0 * scale, TEAL);
        painter.circle_filled(
            centre - Vec2::splat(4.0 * scale),
            4.0 * scale,
            Color32::from_white_alpha(90),
        );
    }
    if state != "Unknown" {
        let opening = match state {
            "Open" => 0.90,
            "Moving" => 0.35,
            _ => 0.0,
        };
        // Circular caps keep both sliding leaves inside the round aperture.
        for side in [-1.0_f32, 1.0] {
            let cut = opening * radius;
            let angle = (cut / radius).acos();
            let points = (0..=32)
                .map(|i| {
                    let theta = -angle + 2.0 * angle * i as f32 / 32.0;
                    centre + Vec2::new(side * radius * theta.cos(), radius * theta.sin())
                })
                .collect();
            painter.add(egui::Shape::convex_polygon(
                points,
                Color32::from_rgb(74, 77, 88),
                Stroke::NONE,
            ));
            let half_height = (radius * radius - cut * cut).sqrt();
            painter.line_segment(
                [
                    centre + Vec2::new(side * cut, -half_height),
                    centre + Vec2::new(side * cut, half_height),
                ],
                Stroke::new(1.0 * scale, Color32::from_rgb(130, 134, 148)),
            );
        }
    }
    if state == "Moving" || state == "Unknown" {
        painter.text(
            centre,
            egui::Align2::CENTER_CENTER,
            if state == "Moving" { "↔" } else { "?" },
            egui::FontId::proportional(23.0 * scale),
            state_color(state),
        );
    }
    if response.hovered() || response.has_focus() {
        painter.circle_stroke(
            centre,
            radius + 7.0 * scale,
            Stroke::new(
                if response.is_pointer_button_down_on() {
                    2.0_f32
                } else {
                    1.0_f32
                },
                BLUE,
            ),
        );
    }
    response
        .on_hover_cursor(egui::CursorIcon::PointingHand)
        .on_hover_text(format!(
            "{state} · Click to toggle. Commanded state; no position sensor."
        ))
}

fn style(ctx: &egui::Context) {
    ctx.set_theme(egui::ThemePreference::Dark);
    let mut visuals = egui::Visuals::dark();
    visuals.panel_fill = BG;
    visuals.window_fill = PANEL;
    visuals.extreme_bg_color = SURFACE;
    visuals.text_edit_bg_color = Some(PANEL);
    visuals.override_text_color = Some(TEXT);
    visuals.selection.bg_fill = BLUE;
    visuals.selection.stroke = Stroke::new(1.0_f32, TEXT);
    visuals.window_stroke = Stroke::new(0.7_f32, BORDER);
    for widget in [
        &mut visuals.widgets.inactive,
        &mut visuals.widgets.hovered,
        &mut visuals.widgets.active,
    ] {
        widget.bg_stroke = Stroke::new(0.7_f32, BORDER);
        widget.corner_radius = egui::CornerRadius::same(6);
        widget.fg_stroke = Stroke::new(1.0_f32, TEXT);
    }
    visuals.widgets.inactive.bg_fill = BUTTON;
    visuals.widgets.inactive.weak_bg_fill = Color32::from_rgb(20, 21, 25);
    visuals.widgets.hovered.bg_fill = Color32::from_rgb(58, 60, 69);
    visuals.widgets.active.bg_fill = BLUE;
    visuals.widgets.noninteractive.bg_stroke = Stroke::new(0.6_f32, BORDER);
    ctx.set_visuals(visuals);
    ctx.style_mut(|style| {
        style.spacing.item_spacing = Vec2::new(8.0, 7.0);
        style.spacing.button_padding = Vec2::new(10.0, 6.0);
        style.spacing.interact_size = Vec2::new(36.0, 30.0);
        for text in [egui::TextStyle::Body, egui::TextStyle::Button] {
            style
                .text_styles
                .insert(text, egui::FontId::proportional(13.0));
        }
        style
            .text_styles
            .insert(egui::TextStyle::Small, egui::FontId::proportional(11.0));
    });
    // Use installed platform fonts; no proprietary font is packaged in releases.
    let candidates = if cfg!(target_os = "macos") {
        vec![
            PathBuf::from("/System/Library/Fonts/SFNS.ttf"),
            PathBuf::from("/System/Library/Fonts/Supplemental/Arial.ttf"),
        ]
    } else if cfg!(windows) {
        vec![
            PathBuf::from(std::env::var_os("WINDIR").unwrap_or_else(|| "C:\\Windows".into()))
                .join("Fonts/segoeui.ttf"),
        ]
    } else {
        vec![PathBuf::from(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        )]
    };
    for path in candidates {
        if let Ok(data) = std::fs::read(path) {
            let mut fonts = egui::FontDefinitions::default();
            fonts.font_data.insert(
                "platform".into(),
                std::sync::Arc::new(egui::FontData::from_owned(data)),
            );
            fonts
                .families
                .entry(egui::FontFamily::Proportional)
                .or_default()
                .insert(0, "platform".into());
            let cjk = if cfg!(target_os = "macos") {
                Some(PathBuf::from("/System/Library/Fonts/Hiragino Sans GB.ttc"))
            } else if cfg!(windows) {
                Some(
                    PathBuf::from(
                        std::env::var_os("WINDIR").unwrap_or_else(|| "C:\\Windows".into()),
                    )
                    .join("Fonts/msgothic.ttc"),
                )
            } else {
                None
            };
            if let Some(data) = cjk.and_then(|path| std::fs::read(path).ok()) {
                fonts.font_data.insert(
                    "cjk".into(),
                    std::sync::Arc::new(egui::FontData::from_owned(data)),
                );
                fonts
                    .families
                    .entry(egui::FontFamily::Proportional)
                    .or_default()
                    .push("cjk".into());
            }
            ctx.set_fonts(fonts);
            break;
        }
    }
}

fn run(args: Args) -> Result<(), Box<dyn std::error::Error>> {
    if let Some(path) = &args.screenshot {
        if path.extension().is_none_or(|extension| extension != "png") {
            return Err("Screenshot path must end in .png".into());
        }
        if let Some(parent) = path
            .parent()
            .filter(|parent| !parent.as_os_str().is_empty())
        {
            std::fs::create_dir_all(parent)?;
        }
    }
    let api = if args.gui_api {
        Some(remote::Server::start(args.api_directory.clone()).map_err(std::io::Error::other)?)
    } else {
        None
    };
    let success = Arc::new(AtomicBool::new(false));
    let flag = success.clone();
    let expected_screenshot = args.screenshot.is_some();
    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_inner_size([540.0, 520.0])
            .with_min_inner_size([270.0, 220.0]),
        ..Default::default()
    };
    eframe::run_native(
        "KohdaLab Shutter",
        options,
        Box::new(move |cc| {
            style(&cc.egui_ctx);
            let mut app = if args.demo {
                App::demo()
            } else {
                App::default()
            };
            let preferences_path = args.preferences.clone().or_else(|| {
                if args.demo {
                    None
                } else {
                    kohdalab_shutter::preferences::default_path()
                }
            });
            app.api = api;
            app.api_enabled = app.api.is_some();
            app.api_directory = args.api_directory.clone();
            app.init_preferences(preferences_path);
            if args.demo && !args.channels.is_empty() {
                if args.channels.iter().any(|ch| *ch > 3) {
                    return Err("Demo channels must be in 0..3".into());
                }
                app.selected = args.channels.iter().copied().collect();
                app.refresh();
            }
            if args.picker {
                app.disconnect();
            }
            if let Some(layout) = args.layout {
                app.layout = layout;
            }
            if let Some(order) = args.order {
                app.order = order;
            }
            app.settings_open = args.settings;
            if !args.demo && !args.gui_api {
                app.find();
            }
            app.screenshot = args.screenshot;
            app.screenshot_success = flag;
            Ok(Box::new(app))
        }),
    )?;
    if expected_screenshot && !success.load(Ordering::Acquire) {
        return Err("Screenshot was not saved".into());
    }
    Ok(())
}

fn main() {
    if let Err(error) = run(Args::parse()) {
        eprintln!("ERROR: {error}");
        std::process::exit(1);
    }
}
#[cfg(test)]
mod tests {
    use super::*;

    fn deliver(app: &mut App, result: Result<Reply, String>) {
        let (sender, receiver) = mpsc::channel();
        sender.send(result).unwrap();
        app.pending = Some(receiver);
        app.receive();
    }

    #[test]
    fn accepted_command_remains_visible_when_status_refresh_fails() {
        let mut app = App {
            client: Some(
                Client::new("127.0.0.1".into(), DEFAULT_PORT, Duration::from_secs(1), 1).unwrap(),
            ),
            ..App::default()
        };
        deliver(&mut app, Ok(Reply::Accepted("Toggle CH0 accepted".into())));
        deliver(&mut app, Err("STATUS timed out".into()));
        assert_eq!(app.last_command.as_deref(), Some("Toggle CH0 accepted"));
        assert!(app.status.is_empty());
        assert!(app.client.is_none());
        assert!(app.error);
    }

    #[test]
    fn discovering_devices_never_silently_selects_one() {
        let mut app = App::default();
        deliver(
            &mut app,
            Ok(Reply::Devices(
                vec![Device {
                    id: "aa".into(),
                    address: "127.0.0.1:12345".parse().unwrap(),
                }],
                BTreeMap::new(),
            )),
        );
        assert!(app.host.is_empty());
        assert!(app.client.is_none());
        assert_eq!(app.devices.len(), 1);
    }

    #[test]
    fn common_lease_and_receipt_shapes_are_standard_without_early_completion() {
        let mut app = App::demo();
        let client = uuid::Uuid::new_v4().to_string();
        let mut acquire = json!({"method":"acquire","client":client,"request_id":uuid::Uuid::new_v4().to_string()});
        let lease = app.api_request(&acquire).unwrap();
        assert_eq!(lease["client_id"], client);
        assert_eq!(lease["heartbeat_seconds"], 1);
        assert_eq!(lease["timeout_seconds"], 10);
        acquire["lease"] = lease["lease"].clone();
        acquire["method"] = json!("toggle");
        acquire["channel"] = json!(0);
        let receipt = app.api_request(&acquire).unwrap();
        assert_eq!(receipt["job_id"], acquire["request_id"]);
        assert!(receipt["terminal"].as_bool().is_some());
        assert_eq!(receipt["cleanup"], "not_required");
        let released = app
            .api_request(&json!({
                "method":"release",
                "client":client,
                "lease":lease["lease"],
                "request_id":uuid::Uuid::new_v4().to_string()
            }))
            .unwrap();
        assert_eq!(released["released"], true);
        assert_eq!(released["cleanup"], "not_required");
        let mut wrong = acquire.clone();
        wrong["lease"] = json!("wrong");
        wrong["request_id"] = json!(uuid::Uuid::new_v4().to_string());
        assert_eq!(app.api_request(&wrong).unwrap_err().code, "ownership_lost");
    }
    #[test]
    fn demo_operations_never_create_a_network_client_or_task() {
        let mut app = App::demo();
        app.operate(Operation::Open, vec![0, 2]);
        assert_eq!(app.status[&0], 90);
        assert_eq!(app.status[&2], 90);
        app.operate(Operation::Toggle, vec![0]);
        assert_eq!(app.status[&0], 0);
        app.disconnect();
        assert!(app.status.is_empty());
        app.find();
        app.host = "a-host-that-must-never-be-resolved.invalid".into();
        app.connect();
        app.refresh();
        assert!(app.connected());
        assert!(app.client.is_none());
        assert!(app.pending.is_none());
        assert_eq!(app.devices.len(), 2);
    }

    #[test]
    fn offline_actions_do_not_create_a_task() {
        let mut app = App::default();
        app.operate(Operation::Open, vec![0]);
        assert!(app.pending.is_none());
    }

    #[test]
    fn screenshot_requires_isolated_demo_mode() {
        assert!(Args::try_parse_from(["gui", "--screenshot", "screen.png"]).is_err());
        assert!(Args::try_parse_from(["gui", "--demo", "--screenshot", "screen.png"]).is_ok());
    }
    fn api_owner(app: &mut App) -> Value {
        let mut request = json!({"client":uuid::Uuid::new_v4().to_string(),"method":"acquire"});
        request["lease"] = app.api_request(&request).unwrap()["lease"].clone();
        request
    }

    #[test]
    fn api_jobs_share_gui_state_and_toggle_is_idempotent() {
        let mut app = App::demo();
        let mut request = api_owner(&mut app);
        request["method"] = json!("toggle");
        request["channel"] = json!(0);
        request["request_id"] = json!(uuid::Uuid::new_v4().to_string());
        let receipt = app.api_request(&request).unwrap();
        assert_eq!(receipt["status"], "completed");
        assert_eq!(app.snapshot_json()["channels"]["0"]["state"], "Open");
        assert_eq!(app.api_request(&request).unwrap(), receipt);
        assert_eq!(app.snapshot_json()["channels"]["0"]["state"], "Open");
        request["channel"] = json!(1);
        assert_eq!(
            app.api_request(&request).unwrap_err().code,
            "request_id_conflict"
        );
        assert!(app.client.is_none());
        assert!(app.pending.is_none());
    }

    #[test]
    fn api_layout_and_takeover_do_not_move_a_shutter() {
        let mut app = App::demo();
        let before = app.status.clone();
        let mut request = api_owner(&mut app);
        request["method"] = json!("set_layout");
        request["layout"] = json!("vertical");
        request["request_id"] = json!(uuid::Uuid::new_v4().to_string());
        app.api_request(&request).unwrap();
        assert!(app.layout == Layout::Vertical);
        assert_eq!(app.status, before);
        app.control.revoke();
        assert_eq!(
            app.api_request(&request).unwrap_err().code,
            "ownership_lost"
        );
        assert_eq!(app.status, before);
    }

    #[test]
    fn api_rejects_missing_channel_without_creating_a_job() {
        let mut app = App::demo();
        let mut request = api_owner(&mut app);
        request["method"] = json!("open");
        request["channel"] = json!(99);
        request["request_id"] = json!(uuid::Uuid::new_v4().to_string());
        assert_eq!(
            app.api_request(&request).unwrap_err().code,
            "invalid_request"
        );
        assert!(
            app.control
                .result(request["request_id"].as_str().unwrap())
                .is_err()
        );
    }
    #[test]
    fn api_cannot_operate_channels_outside_the_pico_selection() {
        let mut app = App::demo();
        app.selected = [1, 3].into();
        app.refresh();
        let before = app.demo_status.clone();
        let mut request = api_owner(&mut app);
        request["method"] = json!("open");
        request["channel"] = json!(0);
        request["request_id"] = json!(uuid::Uuid::new_v4().to_string());
        assert_eq!(
            app.api_request(&request).unwrap_err().code,
            "invalid_request"
        );
        assert_eq!(app.demo_status, before);
        request["method"] = json!("open_all");
        request["request_id"] = json!(uuid::Uuid::new_v4().to_string());
        app.api_request(&request).unwrap();
        assert_eq!(app.demo_status[&0], before[&0]);
        assert_eq!(app.demo_status[&2], before[&2]);
    }

    #[test]
    fn names_autosave_and_preferences_restore_without_connecting() {
        let directory = tempfile::tempdir().unwrap();
        let path = directory.path().join("preferences.json");
        let mut app = App::demo();
        app.init_preferences(Some(path.clone()));
        app.selected = [1, 2].into();
        app.layout = Layout::Vertical;
        app.order = Order::Descending;
        app.device_label = "Bench A".into();
        app.dirty_device = true;
        app.channel_labels.insert(1, "Probe beam".into());
        app.dirty_channels.insert(1);
        app.config_due = Some(Instant::now());
        app.autosave_labels();
        app.persist_preferences(true);
        assert_eq!(app.info.as_ref().unwrap().label, "Bench A");
        assert_eq!(app.info.as_ref().unwrap().channels[1].label, "Probe beam");
        let mut restored = App::default();
        restored.init_preferences(Some(path));
        assert!(restored.layout == Layout::Vertical && restored.order == Order::Descending);
        assert!(!restored.connected());
        let mut info = app.info.clone().unwrap();
        info.channels[2].locked = true;
        restored.restore_channels(&info);
        restored.update_info(info);
        assert_eq!(restored.selected, BTreeSet::from([1]));
        assert_eq!(restored.channel_label(1), "Probe beam");
    }

    #[test]
    fn old_save_acknowledgement_cannot_overwrite_newer_name_edit() {
        let mut app = App::demo();
        app.channel_labels.insert(1, "Newer name".into());
        app.dirty_channels.insert(1);
        let patch = LabelPatch {
            device: None,
            channels: BTreeMap::from([(1, "Earlier name".into())]),
        };
        let mut info = app.info.clone().unwrap();
        info.channels[1].label = "Earlier name".into();
        app.acknowledge_config(&patch, info);
        assert_eq!(app.channel_label(1), "Newer name");
        assert!(app.dirty_channels.contains(&1));
        assert_eq!(
            app.current_preferences()
                .devices
                .values()
                .next()
                .unwrap()
                .channel_labels[&1],
            "Earlier name"
        );
    }

    #[test]
    fn failed_name_save_does_not_disconnect_or_erase_unsaved_draft() {
        let mut app = App::demo();
        app.device_label = "Unsaved name".into();
        app.dirty_device = true;
        let positions = app.status.clone();
        app.config_pending = Some(LabelPatch {
            device: Some("Unsaved name".into()),
            channels: BTreeMap::new(),
        });
        deliver(
            &mut app,
            Ok(Reply::Config(Err("Storage unavailable".into()))),
        );
        assert!(app.connected());
        assert_eq!(app.status, positions);
        assert!(app.dirty_device);
        assert_eq!(app.device_label, "Unsaved name");
        assert_eq!(app.config_error, "Storage unavailable");
    }

    #[test]
    fn closing_flushes_names_and_pc_settings_before_debounce() {
        use eframe::App as _;
        let directory = tempfile::tempdir().unwrap();
        let path = directory.path().join("preferences.json");
        let mut app = App::demo();
        app.init_preferences(Some(path.clone()));
        app.device_label = "Before close".into();
        app.dirty_device = true;
        app.changed_label();
        app.on_exit(None);
        let loaded = kohdalab_shutter::preferences::Preferences::load(&path).unwrap();
        assert_eq!(
            loaded.devices.values().next().unwrap().label,
            "Before close"
        );
    }

    #[test]
    fn main_window_shows_names_and_has_no_all_controls() {
        let mut app = App::demo();
        let text = render_text(&mut app);
        assert!(text.iter().any(|(label, _)| label == "Probe"));
        assert!(text.iter().any(|(label, _)| label == "CH01"));
        assert!(
            !text
                .iter()
                .any(|(label, _)| label == "Open all" || label == "Close all")
        );
    }

    #[test]
    fn unsaved_names_cannot_cross_controller_identity() {
        let mut app = App::demo();
        app.device_label = "Only for A".into();
        app.dirty_device = true;
        app.changed_label();
        app.channel_labels.insert(0, "Only A channel".into());
        app.dirty_channels.insert(0);
        let other = demo_info("bb", 0);
        app.update_info(other);
        assert!(!app.dirty_device && app.dirty_channels.is_empty());
        assert_eq!(app.channel_label(0), "Pump");
        assert_ne!(app.device_label, "Only for A");
        assert!(app.config_due.is_none());
        assert!(app.config_error.contains("different Pico"));
    }

    #[test]
    fn api_opt_in_is_restored_with_fresh_ephemeral_credentials() {
        let directory = tempfile::tempdir().unwrap();
        let path = directory.path().join("config.json");
        let preferences = kohdalab_shutter::preferences::Preferences {
            local_control_api: true,
            ..Default::default()
        };
        preferences.save(&path).unwrap();
        let mut app = App {
            api_directory: Some(directory.path().join("api")),
            ..Default::default()
        };
        app.init_preferences(Some(path.clone()));
        assert!(app.api.is_some());
        assert!(app.current_preferences().local_control_api);
        let contents = std::fs::read_to_string(path).unwrap();
        assert!(!contents.contains("token") && !contents.contains("lease"));
    }

    fn ui_frame(app: &mut App, ctx: &egui::Context, events: Vec<egui::Event>) -> egui::FullOutput {
        ctx.run(
            egui::RawInput {
                screen_rect: Some(egui::Rect::from_min_size(
                    egui::Pos2::ZERO,
                    app.desired_size(),
                )),
                events,
                ..Default::default()
            },
            |ctx| app.draw(ctx),
        )
    }

    fn click(app: &mut App, ctx: &egui::Context, pos: egui::Pos2) -> egui::FullOutput {
        ui_frame(
            app,
            ctx,
            vec![
                egui::Event::PointerMoved(pos),
                egui::Event::PointerButton {
                    pos,
                    button: egui::PointerButton::Primary,
                    pressed: true,
                    modifiers: Default::default(),
                },
            ],
        );
        ui_frame(
            app,
            ctx,
            vec![egui::Event::PointerButton {
                pos,
                button: egui::PointerButton::Primary,
                pressed: false,
                modifiers: Default::default(),
            }],
        )
    }

    fn key(key: egui::Key) -> egui::Event {
        egui::Event::Key {
            key,
            physical_key: None,
            pressed: true,
            repeat: false,
            modifiers: Default::default(),
        }
    }

    fn text_position(output: &egui::FullOutput, text: &str) -> egui::Pos2 {
        output
            .shapes
            .iter()
            .find_map(|shape| {
                if let egui::epaint::Shape::Text(label) = &shape.shape
                    && label.galley.job.text == text
                {
                    Some(label.pos + egui::vec2(5.0, 5.0))
                } else {
                    None
                }
            })
            .unwrap_or_else(|| panic!("Missing text: {text}"))
    }

    #[test]
    fn clicking_aperture_toggles_once_without_open_close_buttons() {
        let mut app = App::demo();
        let ctx = egui::Context::default();
        style(&ctx);
        let output = ui_frame(&mut app, &ctx, vec![]);
        let centre = output
            .shapes
            .iter()
            .find_map(|shape| {
                if let egui::epaint::Shape::Circle(circle) = &shape.shape
                    && (circle.radius - 48.0 * 0.68).abs() < 0.1
                    && circle.fill == BG
                {
                    Some(circle.center)
                } else {
                    None
                }
            })
            .expect("clickable aperture");
        let before = app.demo_status[&0];
        click(&mut app, &ctx, centre);
        assert_ne!(app.demo_status[&0], before);
        ui_frame(&mut app, &ctx, vec![]);
        assert_ne!(app.demo_status[&0], before);
        assert!(
            !render_text(&mut app)
                .iter()
                .any(|(text, _)| text == "Open" || text == "Close")
        );
    }

    #[test]
    fn names_commit_on_enter_and_discard_on_escape_or_blur() {
        let mut app = App::demo();
        let ctx = egui::Context::default();
        style(&ctx);
        let output = ui_frame(&mut app, &ctx, vec![]);
        let position = text_position(&output, "Pump");
        click(&mut app, &ctx, position);
        ui_frame(
            &mut app,
            &ctx,
            vec![key(egui::Key::End), egui::Event::Text(" beam".into())],
        );
        assert_eq!(app.channel_label(0), "Pump");
        ui_frame(&mut app, &ctx, vec![key(egui::Key::Enter)]);
        assert_eq!(app.channel_label(0), "Pump beam");
        assert_eq!(app.demo_status[&0], 0);
        click(&mut app, &ctx, position);
        ui_frame(
            &mut app,
            &ctx,
            vec![
                key(egui::Key::End),
                egui::Event::Text(" discarded".into()),
                key(egui::Key::Escape),
            ],
        );
        assert_eq!(app.channel_label(0), "Pump beam");
        click(&mut app, &ctx, position);
        ui_frame(
            &mut app,
            &ctx,
            vec![key(egui::Key::End), egui::Event::Text(" discarded".into())],
        );
        click(&mut app, &ctx, egui::pos2(10.0, 250.0));
        assert_eq!(app.channel_label(0), "Pump beam");
        assert_eq!(app.name_edits[&0], "Pump beam");
    }

    #[test]
    fn connection_menu_exposes_disconnect_and_picker_channels_are_vertical() {
        let mut app = App::demo();
        let ctx = egui::Context::default();
        style(&ctx);
        let output = ui_frame(&mut app, &ctx, vec![]);
        let position = text_position(&output, "Optics bench  ▾");
        click(&mut app, &ctx, position);
        let output = ui_frame(&mut app, &ctx, vec![]);
        text_position(&output, "Disconnect");
        app.disconnect();
        let text = render_text(&mut app);
        let positions: Vec<_> = (0..4)
            .map(|ch| {
                text.iter()
                    .find(|(text, _)| text == &format!("CH{ch:02}"))
                    .unwrap()
                    .1
            })
            .collect();
        for pair in positions.windows(2) {
            assert_eq!(pair[0].x, pair[1].x);
            assert!(pair[0].y < pair[1].y);
        }
    }

    #[test]
    fn polling_queues_only_one_toggle_and_transport_failure_cancels_it() {
        let mut app = App::demo();
        let (_sender, receiver) = mpsc::channel();
        app.pending = Some(receiver);
        app.refreshing = true;
        app.request_toggle(0);
        app.request_toggle(0);
        assert_eq!(app.queued_toggle, Some(0));
        let snapshot = Snapshot::demo(&app.demo_status);
        let info = app.info.clone().unwrap();
        deliver(&mut app, Ok(Reply::Refreshed(snapshot, info)));
        assert_eq!(app.demo_status[&0], 90);
        assert_eq!(app.queued_toggle, None);
        app.queued_toggle = Some(0);
        deliver(&mut app, Err("connection lost".into()));
        assert_eq!(app.queued_toggle, None);
        assert_eq!(app.demo_status[&0], 90);
    }

    fn render_text(app: &mut App) -> Vec<(String, egui::Pos2)> {
        fn collect(shape: &egui::epaint::Shape, text: &mut Vec<(String, egui::Pos2)>) {
            match shape {
                egui::epaint::Shape::Text(label) => {
                    text.push((label.galley.job.text.clone(), label.pos))
                }
                egui::epaint::Shape::Vec(shapes) => {
                    for shape in shapes {
                        collect(shape, text);
                    }
                }
                _ => {}
            }
        }
        let ctx = egui::Context::default();
        style(&ctx);
        let output = ctx.run(
            egui::RawInput {
                screen_rect: Some(egui::Rect::from_min_size(
                    egui::Pos2::ZERO,
                    app.desired_size(),
                )),
                ..Default::default()
            },
            |ctx| {
                app.draw(ctx);
            },
        );
        let mut text = Vec::new();
        for shape in output.shapes {
            collect(&shape.shape, &mut text);
        }
        text
    }

    #[test]
    fn polling_does_not_move_shutter_controls_or_show_connection_messages_above_them() {
        for layout in [Layout::Horizontal, Layout::Vertical] {
            let mut app = App::demo();
            app.layout = layout;
            app.message = "Connected. Commanded positions refresh every second.".into();
            let idle = render_text(&mut app);
            let (_sender, receiver) = mpsc::channel();
            app.pending = Some(receiver);
            let polling = render_text(&mut app);
            for channel in 0..4 {
                let name = format!("CH{channel:02}");
                let before = idle
                    .iter()
                    .find(|(text, _)| text == &name)
                    .expect("idle channel")
                    .1;
                let after = polling
                    .iter()
                    .find(|(text, _)| text == &name)
                    .expect("polling channel")
                    .1;
                assert_eq!(before, after, "Polling moved {name}");
            }
            assert!(!polling.iter().any(|(text, _)| text == &app.message));
        }
    }

    #[test]
    fn picker_and_controls_are_separate_and_only_selected_channels_are_visible() {
        let mut app = App::demo();
        app.selected = [1, 3].into();
        app.refresh();
        let text = render_text(&mut app);
        assert!(text.iter().any(|(text, _)| text == "CH01"));
        assert!(text.iter().any(|(text, _)| text == "CH03"));
        assert!(
            !text
                .iter()
                .any(|(text, _)| text == "CH00" || text == "CH02" || text == "Find Pico W")
        );
        assert!(!text.iter().any(|(text, _)| text == "Disconnect"));
        assert!(text.iter().any(|(text, _)| text.contains("Optics bench")));
        app.disconnect();
        let picker = render_text(&mut app);
        assert!(picker.iter().any(|(text, _)| text == "Find Pico W"));
        assert!(
            !picker
                .iter()
                .any(|(text, _)| text == "Open all" || text == "Disconnect")
        );
    }

    #[test]
    fn no_selection_cannot_connect_or_operate_unselected_channels() {
        let mut app = App::demo();
        app.disconnect();
        app.selected.clear();
        app.connect();
        assert!(!app.connected());
        assert!(app.error);
        app.selected = [2].into();
        app.connect();
        let before = app.demo_status.clone();
        app.operate(Operation::Toggle, vec![0]);
        assert_eq!(app.demo_status, before);
        assert_eq!(app.status.len(), 1);
    }

    #[test]
    fn display_order_is_numeric_for_both_layouts_without_renumbering_channels() {
        let mut app = App::demo();
        app.status = [(10, 90), (2, 0), (1, 90)].into();
        let original = app.status.clone();
        for layout in [Layout::Horizontal, Layout::Vertical] {
            app.layout = layout;
            app.order = Order::Ascending;
            assert_eq!(app.ordered_channels(), [1, 2, 10]);
            app.order = Order::Descending;
            assert_eq!(app.ordered_channels(), [10, 2, 1]);
        }
        assert_eq!(app.status, original);
    }

    #[test]
    fn api_changes_display_order_without_changing_hardware_state() {
        let mut app = App::demo();
        let before = app.status.clone();
        let mut request = api_owner(&mut app);
        request["method"] = json!("set_order");
        request["order"] = json!("descending");
        request["request_id"] = json!(uuid::Uuid::new_v4().to_string());
        let receipt = app.api_request(&request).unwrap();
        assert_eq!(receipt["status"], "completed");
        assert_eq!(app.snapshot_json()["display_order"], json!([3, 2, 1, 0]));
        assert_eq!(app.status, before);
        assert_eq!(app.api_request(&request).unwrap(), receipt);
        request["request_id"] = json!(uuid::Uuid::new_v4().to_string());
        request["order"] = json!("invalid");
        assert_eq!(
            app.api_request(&request).unwrap_err().code,
            "invalid_request"
        );
        assert_eq!(app.status, before);
    }
}
