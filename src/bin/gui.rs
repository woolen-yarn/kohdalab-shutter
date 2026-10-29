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
const PANEL: Color32 = Color32::from_rgb(26, 27, 32);
const BORDER: Color32 = Color32::from_rgb(56, 58, 67);
const TEXT: Color32 = Color32::from_rgb(235, 236, 241);
const MUTED: Color32 = Color32::from_rgb(160, 163, 176);
const TEAL: Color32 = Color32::from_rgb(63, 215, 194);
const ORANGE: Color32 = Color32::from_rgb(245, 183, 82);
const RED: Color32 = Color32::from_rgb(255, 123, 130);

#[derive(Clone, Copy, PartialEq, Eq, clap::ValueEnum, serde::Serialize)]
#[serde(rename_all = "lowercase")]
enum Layout {
    Horizontal,
    Vertical,
}

#[derive(Parser)]
#[command(version, about = "KohdaLab Shutter desktop controller")]
struct Args {
    /// Explore simulated shutters without opening network connections
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
            "layout":self.layout,"host":self.host,"port":self.port,"busy":self.pending.is_some(),
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
                "actions":["capabilities","status","config","acquire","heartbeat","release","result","discover","connect","disconnect","open","close","toggle","open_all","close_all","set_layout"],
                "lease_timeout_s":10,"release_policy":"hold_last_state","job_completion":"command_acknowledgement",
                "state_semantics":"commanded_not_sensor_verified","receipt_limit":64,"action_id_limit":4096}),
                );
            }
            "status" => return Ok(self.snapshot_json()),
            "config" => {
                return Ok(
                    json!({"host":self.host,"port":self.port,"broadcast":self.broadcast,"layout":self.layout,"demo":self.demo}),
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
            | "close_all" | "set_layout" => {}
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
        let idle = self.pending.is_none();
        let connected = self.connected();
        let manual = idle && !self.control.owned();
        section(ui, "Controller", |ui| {
            ui.horizontal(|ui| {
                badge(
                    ui,
                    if connected { "CONNECTED" } else { "OFFLINE" },
                    if connected { TEAL } else { MUTED },
                );
                if self.demo {
                    badge(ui, "SIM", ORANGE);
                }
            });
            ui.add_space(8.0);
            ui.add_enabled_ui(manual && !connected, |ui| {
                if ui
                    .add_sized(
                        [ui.available_width(), 30.0],
                        egui::Button::new("Find Pico W"),
                    )
                    .clicked()
                {
                    self.find();
                }
                let mut selected = None;
                for device in &self.devices {
                    let active = self.host == device.address.ip().to_string()
                        && self.port == device.address.port();
                    if ui
                        .add_sized(
                            [ui.available_width(), 42.0],
                            egui::Button::new(format!("Pico {}\n{}", device.id, device.address))
                                .selected(active),
                        )
                        .clicked()
                    {
                        selected = Some(device.clone());
                    }
                }
                if let Some(device) = selected {
                    self.host = device.address.ip().to_string();
                    self.port = device.address.port();
                }
            });
            ui.add_space(6.0);
            if connected {
                ui.label(RichText::new(format!("{}:{}", self.host, self.port)).color(MUTED));
                if ui
                    .add_enabled(manual, egui::Button::new("Disconnect"))
                    .clicked()
                {
                    self.disconnect();
                }
            } else {
                ui.add_enabled_ui(manual, |ui| {
                    ui.label(RichText::new("IP / hostname").small().color(MUTED));
                    ui.add_sized(
                        [ui.available_width(), 26.0],
                        egui::TextEdit::singleline(&mut self.host),
                    );
                    ui.horizontal(|ui| {
                        ui.label("Port");
                        ui.add(egui::DragValue::new(&mut self.port).range(1..=65535));
                    });
                    if ui
                        .add_sized(
                            [ui.available_width(), 29.0],
                            egui::Button::new("Connect").fill(Color32::from_rgb(48, 107, 214)),
                        )
                        .clicked()
                    {
                        self.connect();
                    }
                });
            }
            ui.add_space(6.0);
            ui.add_enabled_ui(manual && !connected, |ui| {
                ui.collapsing("Network settings", |ui| {
                    ui.label("Subnet broadcast");
                    ui.add_sized(
                        [ui.available_width(), 26.0],
                        egui::TextEdit::singleline(&mut self.broadcast),
                    );
                });
            });
        });
        ui.add_space(10.0);
        section(ui, "External control", |ui| {
            let mut enabled = self.api.is_some();
            if ui
                .add_enabled(
                    !self.control.owned() && self.pending_api_job.is_none(),
                    egui::Checkbox::new(&mut enabled, "Enable local API"),
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
                ui.colored_label(ORANGE, format!("Control: {label}"));
            }
            if self.control.owned()
                && ui
                    .add_enabled(idle, egui::Button::new("Take control"))
                    .clicked()
            {
                self.control.revoke();
                self.record("External control revoked by operator");
            }
            if let Some(api) = &self.api {
                ui.label(
                    RichText::new("Python / Jupyter · localhost")
                        .small()
                        .color(MUTED),
                )
                .on_hover_text(api.descriptor.display().to_string());
            }
        });
        ui.add_space(8.0);
        ui.collapsing("Details & activity", |ui| {
            if let Some(last) = &self.last_command {
                ui.label(last);
            }
            if let Some(updated) = self.last_update {
                ui.label(format!(
                    "Updated {:.1} s ago",
                    updated.elapsed().as_secs_f32()
                ));
            }
            ui.add_space(6.0);
            egui::ScrollArea::vertical()
                .id_salt("activity")
                .max_height(170.0)
                .stick_to_bottom(true)
                .show(ui, |ui| {
                    for event in &self.log {
                        ui.label(RichText::new(event).small().color(MUTED));
                    }
                });
        });
        ui.add_space(12.0);
        ui.label(
            RichText::new("Open / Close show the commanded state, not a position sensor.")
                .small()
                .color(MUTED),
        );
    }

    fn channels_panel(&mut self, ui: &mut egui::Ui) {
        let manual = self.connected() && self.pending.is_none() && !self.control.owned();
        ui.horizontal(|ui| {
            ui.label(RichText::new("Shutters").size(20.0));
            ui.label(RichText::new(format!("{} channels", self.status.len())).color(MUTED));
            ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                if ui
                    .add_enabled(
                        manual && !self.status.is_empty(),
                        egui::Button::new("Close all").min_size(Vec2::new(90.0, 29.0)),
                    )
                    .clicked()
                {
                    self.operate(Operation::Close, self.status.keys().copied().collect());
                }
                if ui
                    .add_enabled(
                        manual && !self.status.is_empty(),
                        egui::Button::new("Open all").min_size(Vec2::new(90.0, 29.0)),
                    )
                    .clicked()
                {
                    self.operate(Operation::Open, self.status.keys().copied().collect());
                }
            });
        });
        ui.add_space(4.0);
        ui.horizontal(|ui| {
            ui.add_enabled_ui(!self.control.owned(), |ui| {
                ui.selectable_value(&mut self.layout, Layout::Horizontal, "Horizontal");
                ui.selectable_value(&mut self.layout, Layout::Vertical, "Vertical");
            });
            if self.pending.is_some() {
                ui.spinner();
            }
        });
        ui.add_space(8.0);
        ui.label(
            RichText::new(&self.message)
                .small()
                .color(if self.error { RED } else { MUTED }),
        );
        ui.add_space(20.0);
        if self.status.is_empty() {
            ui.label(RichText::new("Find Pico W → select a device → Connect").color(MUTED));
            return;
        }
        let values: Vec<_> = self.status.iter().map(|(&ch, _)| ch).collect();
        let mut action = None;
        if self.layout == Layout::Vertical {
            self.vertical_cards(ui, &values, manual, &mut action);
        } else {
            egui::ScrollArea::both().id_salt("shutters").show(ui,|ui| {
            let cards=|ui:&mut egui::Ui| {
                for channel in values {
                    let state=self.state.channels.get(&channel);
                    let name=state.map_or("Unknown",|state|state.name());
                    let tooltip=state.map_or("No calibrated state available".into(),|state|format!("Commanded position: {}°. Target: {:?}. Open: {:?}, close: {:?}. No position sensor.",state.position,state.target,state.open_angle,state.close_angle));
                    let width=194.0;
                    egui::Frame::new().fill(PANEL).corner_radius(12).stroke(Stroke::new(1.0_f32,BORDER)).inner_margin(16).show(ui,|ui| {
                        ui.set_width(width);
                        ui.vertical_centered(|ui| {
                            egui::Frame::new().fill(Color32::from_rgb(42,153,134)).corner_radius(3).inner_margin(egui::Margin::symmetric(16,3)).show(ui,|ui| {
                                ui.label(RichText::new(format!("CH{channel:02}")).size(24.0).monospace().strong().color(Color32::from_rgb(8,30,27)));
                            });
                            ui.add_space(17.0);
                            let response=controller_switch(ui,name,manual,1.0);
                            if response.clicked() {action=Some((Operation::Toggle,channel));}
                            response.on_hover_text(format!("Push to toggle CH{channel:02}. {tooltip}"));
                            ui.add_space(12.0);
                            let color=match name {"Open"=>TEAL,"Close"=>RED,"Moving"=>ORANGE,_=>MUTED};
                            ui.label(RichText::new(name.to_uppercase()).size(26.0).strong().color(color)).on_hover_text(tooltip);
                            ui.label(RichText::new(if self.demo {"SIMULATED STATE"} else {"COMMANDED STATE"}).size(10.0).color(MUTED));
                            ui.add_space(15.0);
                            ui.add_enabled_ui(manual,|ui| {
                                ui.columns(2,|buttons| {
                                    if buttons[0].add_sized([buttons[0].available_width(),31.0],egui::Button::new("Open")).clicked() {action=Some((Operation::Open,channel));}
                                    if buttons[1].add_sized([buttons[1].available_width(),31.0],egui::Button::new("Close")).clicked() {action=Some((Operation::Close,channel));}
                                });
                            });
                        });
                    });
                    ui.add_space(14.0);
                }
            };
            ui.horizontal_top(cards);
        });
        }
        if let Some((operation, channel)) = action {
            self.operate(operation, vec![channel]);
        }
    }

    fn vertical_cards(
        &self,
        ui: &mut egui::Ui,
        channels: &[u8],
        manual: bool,
        action: &mut Option<(Operation, u8)>,
    ) {
        egui::ScrollArea::both()
            .id_salt("vertical-shutters")
            .show(ui, |ui| {
                for channel in channels {
                    let name = self
                        .state
                        .channels
                        .get(channel)
                        .map_or("Unknown", |state| state.name());
                    let color = match name {
                        "Open" => TEAL,
                        "Close" => RED,
                        "Moving" => ORANGE,
                        _ => MUTED,
                    };
                    egui::Frame::new()
                        .fill(PANEL)
                        .corner_radius(10)
                        .stroke(Stroke::new(1.0_f32, BORDER))
                        .inner_margin(12)
                        .show(ui, |ui| {
                            ui.set_min_width((ui.available_width() - 24.0).max(620.0));
                            ui.horizontal(|ui| {
                                ui.label(
                                    RichText::new(format!("CH{channel:02}"))
                                        .monospace()
                                        .size(24.0)
                                        .color(TEAL),
                                );
                                ui.add_space(18.0);
                                let response = controller_switch(ui, name, manual, 0.55);
                                if response.clicked() {
                                    *action = Some((Operation::Toggle, *channel));
                                }
                                response.on_hover_text(
                                    "Push to toggle. Commanded state, not sensor feedback.",
                                );
                                ui.add_space(18.0);
                                ui.allocate_ui(Vec2::new(150.0, 65.0), |ui| {
                                    ui.label(
                                        RichText::new(name.to_uppercase()).size(23.0).color(color),
                                    );
                                    ui.label(
                                        RichText::new(if self.demo {
                                            "SIMULATED STATE"
                                        } else {
                                            "COMMANDED STATE"
                                        })
                                        .size(10.0)
                                        .color(MUTED),
                                    );
                                });
                                ui.add_enabled_ui(manual, |ui| {
                                    if ui
                                        .add_sized([90.0, 32.0], egui::Button::new("Open"))
                                        .clicked()
                                    {
                                        *action = Some((Operation::Open, *channel));
                                    }
                                    if ui
                                        .add_sized([90.0, 32.0], egui::Button::new("Close"))
                                        .clicked()
                                    {
                                        *action = Some((Operation::Close, *channel));
                                    }
                                });
                            });
                        });
                    ui.add_space(10.0);
                }
            });
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
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        self.receive();
        self.process_api();
        if self.connected() && self.pending.is_none() && Instant::now() >= self.next_refresh {
            self.refresh();
        }
        egui::TopBottomPanel::top("header")
            .exact_height(48.0)
            .frame(
                egui::Frame::new()
                    .fill(BG)
                    .inner_margin(egui::Margin::symmetric(16, 10)),
            )
            .show(ctx, |ui| {
                ui.horizontal(|ui| {
                    ui.label(RichText::new("KohdaLab Shutter").size(21.0).strong());
                    if self.demo {
                        badge(ui, "DEMO · NO HARDWARE", ORANGE);
                    }
                    if self.control.owned() {
                        badge(ui, "EXTERNAL CONTROL", ORANGE);
                    }
                    ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                        ui.label(
                            RichText::new(format!("v{}", env!("CARGO_PKG_VERSION"))).color(MUTED),
                        );
                    });
                });
            });
        egui::SidePanel::left("connection")
            .exact_width(266.0)
            .resizable(false)
            .frame(egui::Frame::new().fill(BG).inner_margin(12))
            .show(ctx, |ui| {
                egui::ScrollArea::vertical()
                    .id_salt("connection-scroll")
                    .show(ui, |ui| self.connection_panel(ui));
            });
        egui::CentralPanel::default()
            .frame(egui::Frame::new().fill(BG).inner_margin(20))
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
    egui::Frame::new()
        .fill(PANEL)
        .corner_radius(10)
        .stroke(Stroke::new(1.0_f32, BORDER))
        .inner_margin(12)
        .show(ui, |ui| {
            ui.set_min_width(ui.available_width());
            ui.label(RichText::new(title).size(14.0));
            ui.add_space(10.0);
            content(ui);
        });
}

fn badge(ui: &mut egui::Ui, text: &str, color: Color32) {
    egui::Frame::new()
        .fill(color.gamma_multiply(0.12))
        .corner_radius(4)
        .inner_margin(egui::Margin::symmetric(5, 2))
        .show(ui, |ui| {
            ui.label(RichText::new(text).size(10.0).color(color));
        });
}

fn controller_switch(ui: &mut egui::Ui, state: &str, enabled: bool, scale: f32) -> egui::Response {
    let (rect, response) = ui.allocate_exact_size(
        Vec2::new(174.0, 122.0) * scale,
        if enabled {
            egui::Sense::click()
        } else {
            egui::Sense::hover()
        },
    );
    let painter = ui.painter();
    let centre = rect.center() + Vec2::new(0.0, 12.0) * scale;
    for (dx, color, on) in [
        (-65.0, RED, state == "Close"),
        (65.0, TEAL, state == "Open"),
    ] {
        let pos = egui::pos2(rect.center().x + dx * scale, rect.top() + 18.0 * scale);
        painter.circle_filled(pos, 12.0 * scale, Color32::from_rgb(38, 41, 44));
        if on {
            painter.circle_filled(pos, 15.0 * scale, color.gamma_multiply(0.15));
        }
        painter.circle_filled(
            pos,
            8.0 * scale,
            if on {
                color
            } else {
                Color32::from_rgb(65, 69, 74)
            },
        );
        painter.circle_stroke(pos, 12.0 * scale, Stroke::new(1.0_f32, BORDER));
        painter.circle_filled(
            pos + Vec2::new(-2.5, -3.0) * scale,
            2.5 * scale,
            Color32::from_white_alpha(if on { 190 } else { 40 }),
        );
    }
    let switch = egui::Rect::from_center_size(centre, Vec2::splat(94.0) * scale);
    painter.rect_filled(switch, 8, Color32::from_rgb(87, 99, 103));
    painter.rect_stroke(
        switch,
        8,
        Stroke::new(1.0_f32, Color32::from_rgb(130, 144, 146)),
        egui::StrokeKind::Inside,
    );
    let pressed = response.is_pointer_button_down_on();
    let fill = if enabled && response.hovered() {
        Color32::from_rgb(37, 68, 67)
    } else {
        Color32::from_rgb(25, 44, 46)
    };
    painter.rect_filled(
        switch.shrink((if pressed { 8.0 } else { 6.0 }) * scale),
        5,
        fill,
    );
    painter.line_segment(
        [
            switch.left_top() + Vec2::new(12.0, 10.0) * scale,
            switch.right_top() + Vec2::new(-12.0, 10.0) * scale,
        ],
        Stroke::new(1.0_f32, Color32::from_rgb(67, 89, 90)),
    );
    painter.text(
        centre,
        egui::Align2::CENTER_CENTER,
        "PUSH",
        egui::FontId::proportional((12.0 * scale).max(9.0)),
        MUTED,
    );
    response
}

fn style(ctx: &egui::Context) {
    ctx.set_theme(egui::ThemePreference::Dark);
    let mut visuals = egui::Visuals::dark();
    visuals.panel_fill = BG;
    visuals.window_fill = PANEL;
    visuals.extreme_bg_color = Color32::from_rgb(20, 21, 25);
    visuals.text_edit_bg_color = Some(visuals.extreme_bg_color);
    visuals.override_text_color = Some(TEXT);
    visuals.selection.bg_fill = Color32::from_rgb(48, 91, 158);
    visuals.window_stroke = Stroke::new(1.0_f32, BORDER);
    for widget in [
        &mut visuals.widgets.inactive,
        &mut visuals.widgets.hovered,
        &mut visuals.widgets.active,
    ] {
        widget.bg_stroke = Stroke::new(0.7_f32, BORDER);
        widget.corner_radius = egui::CornerRadius::same(6);
        widget.fg_stroke = Stroke::new(1.0_f32, TEXT);
    }
    visuals.widgets.inactive.bg_fill = Color32::from_rgb(45, 46, 53);
    visuals.widgets.inactive.weak_bg_fill = Color32::from_rgb(20, 21, 25);
    visuals.widgets.hovered.bg_fill = Color32::from_rgb(62, 64, 74);
    visuals.widgets.active.bg_fill = Color32::from_rgb(48, 91, 158);
    ctx.set_visuals(visuals);
    ctx.style_mut(|style| {
        style.spacing.item_spacing = Vec2::new(8.0, 6.0);
        style.spacing.button_padding = Vec2::new(8.0, 5.0);
        for text in [egui::TextStyle::Body, egui::TextStyle::Button] {
            style
                .text_styles
                .insert(text, egui::FontId::proportional(13.0));
        }
        style
            .text_styles
            .insert(egui::TextStyle::Small, egui::FontId::proportional(11.0));
    });
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
            .with_inner_size([1280.0, 640.0])
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
}
