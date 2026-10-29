#![cfg_attr(target_os = "windows", windows_subsystem = "windows")]

use clap::Parser;
use eframe::egui::{self, Color32, RichText, Stroke, Vec2};
use kohdalab_shutter::{
    DEFAULT_PORT,
    control::{ApiError, Control, response, string},
    discovery::{self, Device},
    protocol::{Operation, Snapshot, Status},
    remote,
    transport::Client,
};
use serde_json::{Value, json};
use std::{
    collections::VecDeque,
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
const SIDEBAR: Color32 = Color32::from_rgb(22, 23, 28);
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
    /// Enable the authenticated loopback GUI control API
    #[arg(long)]
    gui_api: bool,
    #[arg(long, requires = "gui_api")]
    api_directory: Option<PathBuf>,
    #[arg(long, value_enum, default_value = "horizontal")]
    layout: Layout,
    /// Display order only; physical channel identifiers never change
    #[arg(long, value_enum, default_value = "ascending")]
    order: Order,
}

enum Reply {
    Devices(Vec<Device>),
    Status(Snapshot),
    Accepted(String),
}
struct App {
    host: String,
    port: u16,
    broadcast: String,
    devices: Vec<Device>,
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
    pending_api_job: Option<String>,
}

impl Default for App {
    fn default() -> Self {
        Self {
            host: String::new(),
            port: DEFAULT_PORT,
            broadcast: "255.255.255.255".into(),
            devices: Vec::new(),
            client: None,
            status: Status::new(),
            state: Snapshot::default(),
            pending: None,
            next_refresh: Instant::now(),
            message: "Find a Pico W, select its ID, then connect.".into(),
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
        self.error = false;
        std::thread::spawn(move || {
            let _ = sender.send(job().map_err(|e| e.to_string()));
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
        self.task(move || discovery::discover(target, Duration::from_secs(2)).map(Reply::Devices));
    }

    fn connect(&mut self) {
        self.last_command = None;
        self.last_update = None;
        self.error = false;
        if self.demo {
            self.demo_connected = true;
            self.status = self.demo_status.clone();
            self.state = Snapshot::demo(&self.status);
            self.last_update = Some(Instant::now());
            self.message = "Simulation connected. No hardware is controlled.".into();
            self.record(format!("Connected to simulated Pico at {}", self.host));
            return;
        }
        match Client::new(
            self.host.trim().to_owned(),
            self.port,
            Duration::from_secs(2),
            2,
        ) {
            Ok(client) => {
                self.client = Some(client.clone());
                self.status.clear();
                self.state = Snapshot::default();
                self.message = "Connecting and reading channel positions...".into();
                self.record(format!("Connecting to {}:{}", self.host.trim(), self.port));
                self.task(move || client.snapshot().map(Reply::Status));
            }
            Err(error) => {
                self.error = true;
                self.message = error.to_string();
            }
        }
    }

    fn disconnect(&mut self) {
        self.client = None;
        self.demo_connected = false;
        self.status.clear();
        self.state = Snapshot::default();
        self.last_update = None;
        self.message = "Disconnected. Select a Pico W to connect.".into();
        self.record("Disconnected");
    }

    fn refresh(&mut self) {
        if self.demo {
            self.status = self.demo_status.clone();
            self.state = Snapshot::demo(&self.status);
            self.last_update = Some(Instant::now());
            self.next_refresh = Instant::now() + Duration::from_secs(1);
        } else if let Some(client) = self.client.clone() {
            self.task(move || client.snapshot().map(Reply::Status));
        }
    }

    fn operate(&mut self, operation: Operation, channels: Vec<u8>) {
        if !self.connected() || self.pending.is_some() || channels.is_empty() {
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
            self.status = self.demo_status.clone();
            self.state = Snapshot::demo(&self.status);
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
                for (completed, channel) in channels.into_iter().enumerate() {
                    client.operate(operation, channel).map_err(|error| std::io::Error::new(error.kind(),
                        format!("{operation:?}: {completed}/{total} commands acknowledged before error: {error}")))?;
                }
                Ok(Reply::Accepted(format!("{operation:?}: {total} command(s) accepted; check commanded angles.")))
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
        let api_error = result.as_ref().err().cloned();
        match result {
            Ok(Reply::Devices(devices)) => {
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
            }
            Ok(Reply::Status(status)) => {
                let first = self.last_update.is_none();
                self.status = status.positions();
                self.state = status;
                self.last_update = Some(Instant::now());
                self.message = "Connected. Commanded positions refresh every second.".into();
                self.next_refresh = Instant::now() + Duration::from_secs(1);
                if first {
                    self.record(format!(
                        "Connected; {} channels available",
                        self.status.len()
                    ));
                }
            }
            Ok(Reply::Accepted(description)) => {
                self.record(description.clone());
                self.last_command = Some(description);
                self.next_refresh = Instant::now();
            }
            Err(error) => {
                self.record(format!("ERROR: {error}"));
                self.error = true;
                self.message = error;
                self.status.clear();
                self.state = Snapshot::default();
                self.client = None;
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
    }

    fn devices_json(&self) -> Value {
        json!(
            self.devices
                .iter()
                .map(|device| json!({"id":device.id,"address":device.address.to_string()}))
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
                (channel.to_string(), value)
            })
            .collect();
        json!({"connected":self.connected() && self.last_update.is_some(),"demo":self.demo,
            "layout":self.layout,"order":self.order,"display_order":self.ordered_channels(),"host":self.host,"port":self.port,"busy":self.pending.is_some(),
            "owner":self.control.label(),"channels":channels,"devices":self.devices_json(),
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
            let result = if request.deadline < Instant::now() {
                Err(ApiError::new(
                    "timeout",
                    "Request expired before execution; no new action started",
                ))
            } else {
                self.api_request(&request.body)
            };
            let _ = request.reply.send(response(result));
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
                "actions":["capabilities","status","config","acquire","heartbeat","release","result","discover","connect","disconnect","open","close","toggle","open_all","close_all","set_layout","set_order"],
                "lease_timeout_s":10,"release_policy":"hold_last_state","job_completion":"command_acknowledgement",
                "state_semantics":"commanded_not_sensor_verified","receipt_limit":64,"action_id_limit":4096}),
                );
            }
            "status" => return Ok(self.snapshot_json()),
            "config" => {
                return Ok(
                    json!({"host":self.host,"port":self.port,"broadcast":self.broadcast,"layout":self.layout,"order":self.order,"demo":self.demo}),
                );
            }
            "result" => return self.control.result(string(body, "id")?),
            "acquire" => return self.control.acquire(body, self.pending.is_some()),
            "heartbeat" => {
                self.control.authorize(body)?;
                return Ok(json!({"alive":true}));
            }
            "release" => return self.control.release(body),
            "discover" | "connect" | "disconnect" | "open" | "close" | "toggle" | "open_all"
            | "close_all" | "set_layout" | "set_order" => {}
            _ => return Err(ApiError::new("unsupported", "Unknown API method")),
        }
        self.control.authorize(body)?;
        if let Some(receipt) = self.control.cached(body, method)? {
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
                connection = Some((host, port));
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
        if let Some((host, port)) = connection {
            self.host = host;
            self.port = port;
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
        self.control.result(&id)
    }

    fn connection_panel(&mut self, ui: &mut egui::Ui) {
        let connected = self.connected();
        let manual = self.pending.is_none() && !self.control.owned();
        section(ui, "Connection", |ui| {
            if connected {
                egui::Frame::new()
                    .fill(Color32::TRANSPARENT)
                    .inner_margin(0)
                    .show(ui, |ui| {
                        ui.set_min_width(ui.available_width());
                        ui.horizontal(|ui| {
                            status_dot(ui, TEAL);
                            ui.label(RichText::new("Pico W").strong().size(16.0));
                        });
                        ui.add_space(5.0);
                        ui.label(
                            RichText::new(format!("{}:{}", self.host, self.port))
                                .small()
                                .color(MUTED),
                        );
                    });
                ui.add_space(9.0);
                if ui
                    .add_enabled(
                        manual,
                        egui::Button::new("Change controller…")
                            .fill(Color32::TRANSPARENT)
                            .stroke(Stroke::NONE),
                    )
                    .clicked()
                {
                    self.disconnect();
                }
            } else {
                if ui
                    .add_enabled(
                        manual,
                        egui::Button::new(RichText::new("Find Pico W").color(Color32::WHITE))
                            .fill(BLUE)
                            .min_size(Vec2::new(ui.available_width(), 36.0)),
                    )
                    .clicked()
                {
                    self.find();
                }
                let mut selected = None;
                ui.add_enabled_ui(manual, |ui| {
                    for device in &self.devices {
                        let active = self.host == device.address.ip().to_string()
                            && self.port == device.address.port();
                        let id = if device.id.len() > 12 {
                            format!("{}…{}", &device.id[..4], &device.id[device.id.len() - 6..])
                        } else {
                            device.id.clone()
                        };
                        if ui
                            .add_sized(
                                [ui.available_width(), 51.0],
                                egui::Button::new(format!("Pico {id}\n{}", device.address))
                                    .selected(active),
                            )
                            .on_hover_text(&device.id)
                            .clicked()
                        {
                            selected = Some(device.clone());
                        }
                    }
                    if let Some(device) = selected {
                        self.host = device.address.ip().to_string();
                        self.port = device.address.port();
                    }
                    ui.add_space(10.0);
                    ui.label(RichText::new("IP or hostname").small().color(MUTED));
                    ui.add_sized(
                        [ui.available_width(), 31.0],
                        egui::TextEdit::singleline(&mut self.host),
                    );
                    ui.horizontal(|ui| {
                        ui.label("Port");
                        ui.add(egui::DragValue::new(&mut self.port).range(1..=65535));
                    });
                    if ui
                        .add_sized([ui.available_width(), 34.0], egui::Button::new("Connect"))
                        .clicked()
                    {
                        self.connect();
                    }
                });
            }
            if !connected {
                ui.add_enabled_ui(manual, |ui| {
                    ui.collapsing("Network settings", |ui| {
                        ui.label(RichText::new("Subnet broadcast").small().color(MUTED));
                        ui.add_sized(
                            [ui.available_width(), 28.0],
                            egui::TextEdit::singleline(&mut self.broadcast),
                        );
                    });
                });
            }
        });
        ui.add_space(12.0);
        section(ui, "All channels", |ui| {
            ui.columns(2, |columns| {
                for (i, label, operation) in [
                    (0, "Open all", Operation::Open),
                    (1, "Close all", Operation::Close),
                ] {
                    if columns[i]
                        .add_enabled(
                            connected && manual && !self.status.is_empty(),
                            egui::Button::new(label)
                                .fill(if i == 0 { BLUE } else { BUTTON })
                                .min_size(Vec2::new(columns[i].available_width(), 30.0)),
                        )
                        .clicked()
                    {
                        self.operate(operation, self.status.keys().copied().collect());
                    }
                }
            });
        });
        ui.add_space(12.0);
        section(ui, "Automation", |ui| {
            let mut enabled = self.api.is_some();
            if ui
                .add_enabled(
                    !self.control.owned() && self.pending_api_job.is_none(),
                    egui::Checkbox::new(&mut enabled, "Local control API"),
                )
                .changed()
            {
                if enabled {
                    match remote::Server::start(None) {
                        Ok(server) => {
                            self.api = Some(server);
                            self.record("Local API enabled");
                        }
                        Err(error) => {
                            self.error = true;
                            self.message = error;
                        }
                    }
                } else {
                    self.api = None;
                    self.control.revoke();
                }
            }
            if let Some(label) = self.control.label() {
                ui.add_space(8.0);
                badge(ui, &format!("Controlled by {label}"), ORANGE);
                if ui
                    .add_enabled(self.pending.is_none(), egui::Button::new("Take control"))
                    .clicked()
                {
                    self.control.revoke();
                    self.record("External control revoked by operator");
                }
            }
        });
        ui.add_space(24.0);
        ui.separator();
        ui.add_space(10.0);
        ui.collapsing("Activity", |ui| {
            if let Some(last) = &self.last_command {
                ui.label(last);
            }
            egui::ScrollArea::vertical()
                .id_salt("activity")
                .max_height(150.0)
                .stick_to_bottom(true)
                .show(ui, |ui| {
                    for event in &self.log {
                        ui.label(RichText::new(event).small().color(MUTED));
                    }
                });
        });
    }

    fn channels_panel(&mut self, ui: &mut egui::Ui) {
        let manual = self.connected() && self.pending.is_none() && !self.control.owned();
        ui.horizontal(|ui| {
            ui.label(RichText::new("Shutters").size(20.0));
            ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                ui.label(
                    RichText::new(format!("{} channels", self.status.len()))
                        .small()
                        .color(MUTED),
                );
            });
        });
        ui.add_space(24.0);
        ui.horizontal(|ui| {
            ui.add_enabled_ui(!self.control.owned(), |ui| {
                segmented_frame(ui, |ui| {
                    segment(ui, &mut self.layout, Layout::Horizontal, "Horizontal");
                    segment(ui, &mut self.layout, Layout::Vertical, "Vertical");
                });
                ui.add_space(10.0);
                segmented_frame(ui, |ui| {
                    segment(ui, &mut self.order, Order::Ascending, "CH ↑")
                        .on_hover_text("Ascending channel order");
                    segment(ui, &mut self.order, Order::Descending, "CH ↓")
                        .on_hover_text("Descending channel order");
                });
            });
            if self.pending.is_some() {
                ui.spinner();
            }
        });
        if self.error || self.pending.is_some() || !self.connected() {
            ui.add_space(14.0);
            ui.label(RichText::new(&self.message).small().color(if self.error {
                RED
            } else {
                MUTED
            }));
        }
        ui.add_space(24.0);
        if self.status.is_empty() {
            ui.add_space(80.0);
            ui.vertical_centered(|ui| {
                ui.label(RichText::new("No controller connected").color(MUTED));
            });
            return;
        }
        let channels = self.ordered_channels();
        let mut action = None;
        egui::ScrollArea::both().id_salt("shutters").show(ui, |ui| {
            if self.layout == Layout::Horizontal {
                let total = channels.len() as f32 * 228.0
                    + (channels.len().saturating_sub(1)) as f32 * 16.0;
                let inset = ((ui.available_width() - total) * 0.5).max(0.0);
                ui.horizontal_top(|ui| {
                    ui.spacing_mut().item_spacing.x = 16.0;
                    if inset > 0.0 {
                        ui.add_space(inset);
                    }
                    for channel in channels {
                        let name = self
                            .state
                            .channels
                            .get(&channel)
                            .map_or("Unknown", |state| state.name());
                        let detail = self.state.channels.get(&channel).map_or(
                            "Update Pico firmware for calibrated state names".into(),
                            |state| {
                                format!(
                                    "Position {}° · target {:?} · close {:?} · open {:?}",
                                    state.position,
                                    state.target,
                                    state.close_angle,
                                    state.open_angle
                                )
                            },
                        );
                        ui.push_id(("channel", self.host.as_str(), self.port, channel), |ui| {
                            card_frame().show(ui, |ui| {
                                ui.vertical(|ui| {
                                    ui.set_width(188.0);
                                    ui.horizontal(|ui| {
                                        ui.label(
                                            RichText::new(format!("CH{channel:02}"))
                                                .size(14.0)
                                                .strong(),
                                        );
                                    });
                                    ui.add_space(22.0);
                                    ui.vertical_centered(|ui| {
                                        shutter_window(ui, name, 1.0).on_hover_text(detail);
                                        ui.add_space(10.0);
                                        ui.label(RichText::new(name).size(22.0).color(TEXT));
                                    });
                                    ui.add_space(24.0);
                                    if let Some(operation) = channel_actions(ui, name, manual) {
                                        action = Some((operation, channel));
                                    }
                                });
                            });
                        });
                    }
                });
            } else {
                for channel in channels {
                    let name = self
                        .state
                        .channels
                        .get(&channel)
                        .map_or("Unknown", |state| state.name());
                    ui.push_id(("channel", self.host.as_str(), self.port, channel), |ui| {
                        card_frame().inner_margin(12).show(ui, |ui| {
                            ui.set_min_width(ui.available_width().max(620.0));
                            ui.horizontal(|ui| {
                                ui.label(
                                    RichText::new(format!("CH{channel:02}")).strong().size(15.0),
                                );
                                ui.add_space(8.0);
                                shutter_window(ui, name, 0.48)
                                    .on_hover_text("Commanded state; no position sensor");
                                ui.add_space(8.0);
                                status_dot(ui, state_color(name));
                                ui.label(RichText::new(name).size(21.0));
                                ui.with_layout(
                                    egui::Layout::right_to_left(egui::Align::Center),
                                    |ui| {
                                        ui.allocate_ui_with_layout(
                                            Vec2::new(176.0, 36.0),
                                            egui::Layout::left_to_right(egui::Align::Center),
                                            |ui| {
                                                if let Some(operation) =
                                                    channel_actions(ui, name, manual)
                                                {
                                                    action = Some((operation, channel));
                                                }
                                            },
                                        );
                                    },
                                );
                            });
                        });
                    });
                    ui.add_space(8.0);
                }
            }
        });
        if let Some((operation, channel)) = action {
            self.operate(operation, vec![channel]);
        }
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
    fn clear_color(&self, _visuals: &egui::Visuals) -> [f32; 4] {
        BG.to_normalized_gamma_f32()
    }

    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        self.receive();
        self.process_api();
        if self.connected() && self.pending.is_none() && Instant::now() >= self.next_refresh {
            self.refresh();
        }
        egui::TopBottomPanel::top("header")
            .show_separator_line(false)
            .resizable(false)
            .exact_height(52.0)
            .frame(
                egui::Frame::new()
                    .fill(PANEL)
                    .inner_margin(egui::Margin::symmetric(22, 13)),
            )
            .show(ctx, |ui| {
                ui.horizontal(|ui| {
                    ui.label(RichText::new("KohdaLab Shutter").size(16.0).strong());
                    ui.label(
                        RichText::new(format!("v{}", env!("CARGO_PKG_VERSION")))
                            .size(13.0)
                            .color(MUTED),
                    );
                    ui.add_space(10.0);
                    if self.demo {
                        badge(ui, "Demo", ORANGE);
                    }
                    if self.control.owned() {
                        badge(ui, "External control", ORANGE);
                    }
                });
            });
        egui::SidePanel::left("connection")
            .exact_width(240.0)
            .resizable(false)
            .frame(egui::Frame::new().fill(SIDEBAR).inner_margin(18))
            .show(ctx, |ui| {
                ui.add_space(8.0);
                egui::ScrollArea::vertical()
                    .id_salt("connection-scroll")
                    .show(ui, |ui| self.connection_panel(ui));
            });
        egui::CentralPanel::default()
            .frame(egui::Frame::new().fill(BG).inner_margin(30))
            .show(ctx, |ui| self.channels_panel(ui));
        self.capture(ctx);
        ctx.request_repaint_after(Duration::from_millis(100));
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

fn section(ui: &mut egui::Ui, title: &str, content: impl FnOnce(&mut egui::Ui)) {
    card_frame().inner_margin(12).show(ui, |ui| {
        ui.set_min_width(ui.available_width());
        ui.label(RichText::new(title).size(12.0).color(MUTED));
        ui.add_space(8.0);
        content(ui);
    });
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
fn badge(ui: &mut egui::Ui, text: &str, color: Color32) {
    let tint = if color == TEAL {
        Color32::from_rgb(30, 61, 56)
    } else {
        Color32::from_rgb(65, 51, 30)
    };
    egui::Frame::new()
        .fill(tint)
        .corner_radius(7)
        .inner_margin(egui::Margin::symmetric(8, 3))
        .show(ui, |ui| {
            ui.label(RichText::new(text).size(11.0).color(color));
        });
}
fn segmented_frame(ui: &mut egui::Ui, content: impl FnOnce(&mut egui::Ui)) {
    egui::Frame::new()
        .fill(SURFACE)
        .corner_radius(6)
        .inner_margin(3)
        .show(ui, |ui| {
            ui.horizontal(|ui| {
                ui.spacing_mut().item_spacing.x = 3.0;
                content(ui);
            });
        });
}
fn segment<T: PartialEq + Copy>(
    ui: &mut egui::Ui,
    current: &mut T,
    value: T,
    label: &str,
) -> egui::Response {
    let selected = *current == value;
    let response = ui.add(
        egui::Button::new(RichText::new(label).color(if selected { TEXT } else { MUTED }))
            .fill(if selected { BLUE } else { BUTTON })
            .stroke(Stroke::NONE)
            .corner_radius(6)
            .min_size(Vec2::new(64.0, 30.0)),
    );
    if response.clicked() {
        *current = value;
    }
    response
}
fn channel_actions(ui: &mut egui::Ui, state: &str, enabled: bool) -> Option<Operation> {
    let mut action = None;
    ui.add_enabled_ui(enabled, |ui| {
        ui.columns(2, |columns| {
            for (i, label, operation) in
                [(0, "Open", Operation::Open), (1, "Close", Operation::Close)]
            {
                if columns[i]
                    .add_sized(
                        [columns[i].available_width(), 30.0],
                        egui::Button::new(label)
                            .fill(if state == label { BLUE } else { BUTTON })
                            .corner_radius(6),
                    )
                    .clicked()
                {
                    action = Some(operation);
                }
            }
        });
    });
    action
}

// Front-facing schematic of commanded state, not a measurement of transmitted light.
fn shutter_window(ui: &mut egui::Ui, state: &str, scale: f32) -> egui::Response {
    let (rect, response) =
        ui.allocate_exact_size(Vec2::new(174.0, 132.0) * scale, egui::Sense::hover());
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
    response.on_hover_text("Commanded state; no position sensor")
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
            .with_inner_size([1320.0, 700.0])
            .with_min_inner_size([720.0, 520.0]),
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
            app.layout = args.layout;
            app.order = args.order;
            app.api = api;
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
            Ok(Reply::Devices(vec![Device {
                id: "aa".into(),
                address: "127.0.0.1:12345".parse().unwrap(),
            }])),
        );
        assert!(app.host.is_empty());
        assert!(app.client.is_none());
        assert_eq!(app.devices.len(), 1);
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
