#![cfg_attr(target_os = "windows", windows_subsystem = "windows")]

use clap::Parser;
use eframe::egui::{self, Color32, RichText, Stroke, Vec2};
use kohdalab_shutter::{
    DEFAULT_PORT,
    discovery::{self, Device},
    protocol::{Operation, Status},
    transport::Client,
};
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
const BLUE: Color32 = Color32::from_rgb(102, 174, 255);
const TEAL: Color32 = Color32::from_rgb(63, 215, 194);
const ORANGE: Color32 = Color32::from_rgb(245, 183, 82);
const RED: Color32 = Color32::from_rgb(255, 123, 130);

#[derive(Parser)]
#[command(version, about = "KohdaLab Shutter desktop controller")]
struct Args {
    /// Explore simulated shutters without opening network connections
    #[arg(long)]
    demo: bool,
    /// Save a real GUI screenshot and exit (demo mode only)
    #[arg(long, requires = "demo")]
    screenshot: Option<PathBuf>,
}

enum Reply {
    Devices(Vec<Device>),
    Status(Status),
    Accepted(String),
}
struct App {
    host: String,
    port: u16,
    broadcast: String,
    devices: Vec<Device>,
    client: Option<Client>,
    status: Status,
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
        app.demo_status = [(0, 0), (1, 90), (2, 0), (3, 45)].into();
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
                self.message = "Connecting and reading channel positions...".into();
                self.record(format!("Connecting to {}:{}", self.host.trim(), self.port));
                self.task(move || client.status().map(Reply::Status));
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
        self.last_update = None;
        self.message = "Disconnected. Select a Pico W to connect.".into();
        self.record("Disconnected");
    }

    fn refresh(&mut self) {
        if self.demo {
            self.status = self.demo_status.clone();
            self.last_update = Some(Instant::now());
            self.next_refresh = Instant::now() + Duration::from_secs(1);
        } else if let Some(client) = self.client.clone() {
            self.task(move || client.status().map(Reply::Status));
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
                self.status = status;
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
                self.client = None;
                self.last_update = None;
            }
        }
    }

    fn connection_panel(&mut self, ui: &mut egui::Ui) {
        let idle = self.pending.is_none();
        let connected = self.connected();
        section(ui, "Pico W", |ui| {
            ui.horizontal(|ui| {
                ui.label(RichText::new("Connection").strong());
                badge(
                    ui,
                    if connected { "CONNECTED" } else { "OFFLINE" },
                    if connected { TEAL } else { MUTED },
                );
            });
            ui.add_space(8.0);
            ui.add_enabled_ui(idle && !connected, |ui| {
                if ui
                    .add_sized(
                        [ui.available_width(), 30.0],
                        egui::Button::new("Find Pico W"),
                    )
                    .clicked()
                {
                    self.find();
                }
                ui.add_space(4.0);
                let mut selected = None;
                for device in &self.devices {
                    let active = self.host == device.address.ip().to_string()
                        && self.port == device.address.port();
                    let text = format!("Pico {}\n{}", device.id, device.address);
                    if ui
                        .add_sized(
                            [ui.available_width(), 45.0],
                            egui::Button::new(text).selected(active),
                        )
                        .clicked()
                    {
                        selected = Some(device.clone());
                    }
                }
                if let Some(device) = selected {
                    self.host = device.address.ip().to_string();
                    self.port = device.address.port();
                    self.message = format!("Selected Pico {}. Press Connect.", device.id);
                    self.record(format!("Selected Pico {}", device.id));
                }
                ui.add_space(10.0);
                ui.label(RichText::new("IP / hostname").color(MUTED));
                ui.add_sized(
                    [ui.available_width(), 28.0],
                    egui::TextEdit::singleline(&mut self.host)
                        .hint_text("Select a device or enter an IP"),
                );
                ui.horizontal(|ui| {
                    ui.label("TCP port");
                    ui.add(egui::DragValue::new(&mut self.port).range(1..=65535));
                });
            });
            ui.add_space(8.0);
            ui.columns(2, |columns| {
                if columns[0]
                    .add_enabled(
                        idle && !connected,
                        egui::Button::new("Connect")
                            .min_size(Vec2::new(100.0, 28.0))
                            .fill(Color32::from_rgb(48, 107, 214)),
                    )
                    .clicked()
                {
                    self.connect();
                }
                if columns[1]
                    .add_enabled(
                        idle && connected,
                        egui::Button::new("Disconnect").min_size(Vec2::new(100.0, 28.0)),
                    )
                    .clicked()
                {
                    self.disconnect();
                }
            });
        });
        ui.add_space(10.0);
        section(ui, "Network", |ui| {
            ui.label(RichText::new("Same LAN discovery").color(BLUE));
            ui.label("Find devices without knowing their IP. Select by the unique hardware ID.");
            ui.add_space(8.0);
            ui.add_enabled_ui(idle && !connected, |ui| {
                ui.collapsing("Search settings", |ui| {
                    ui.label("Subnet broadcast");
                    ui.add_sized(
                        [ui.available_width(), 28.0],
                        egui::TextEdit::singleline(&mut self.broadcast),
                    );
                });
            });
            ui.add_space(8.0);
            ui.label(
                RichText::new("TCP 12345 · UDP 12346 (defaults)")
                    .small()
                    .color(MUTED),
            );
        });
    }

    fn detail_panel(&self, ui: &mut egui::Ui) {
        section(ui, "Activity", |ui| {
            ui.label(
                RichText::new(if self.demo {
                    "SIMULATION · no hardware"
                } else {
                    "Connection and command events"
                })
                .color(if self.demo { ORANGE } else { MUTED }),
            );
            ui.add_space(8.0);
            egui::ScrollArea::vertical()
                .id_salt("activity")
                .max_height(210.0)
                .stick_to_bottom(true)
                .show(ui, |ui| {
                    ui.set_min_height(180.0);
                    for event in &self.log {
                        ui.label(event);
                        ui.add_space(4.0);
                    }
                });
        });
        ui.add_space(10.0);
        section(ui, "Device details", |ui| {
            egui::Grid::new("details")
                .num_columns(2)
                .spacing([16.0, 10.0])
                .show(ui, |ui| {
                    for (key, value) in [
                        (
                            "Mode",
                            if self.demo {
                                "Simulation".into()
                            } else {
                                "Hardware".into()
                            },
                        ),
                        (
                            "Endpoint",
                            if self.host.is_empty() {
                                "—".into()
                            } else {
                                format!("{}:{}", self.host, self.port)
                            },
                        ),
                        ("Channels", self.status.len().to_string()),
                        ("Refresh", "1 s".into()),
                        (
                            "Last update",
                            self.last_update.map_or("—".into(), |t| {
                                format!("{:.1} s ago", t.elapsed().as_secs_f32())
                            }),
                        ),
                    ] {
                        ui.label(RichText::new(key).color(MUTED));
                        ui.label(value);
                        ui.end_row();
                    }
                });
        });
        ui.add_space(10.0);
        section(ui, "Commanded positions", |ui| {
            ui.label("Angles are the last commanded servo steps.");
            ui.add_space(4.0);
            ui.label(
                RichText::new(
                    "No position sensor feedback. An angle does not confirm physical closure.",
                )
                .small()
                .color(MUTED),
            );
        });
    }

    fn channels_panel(&mut self, ui: &mut egui::Ui) {
        let enabled = self.connected() && self.pending.is_none() && !self.status.is_empty();
        section(ui, "Shutter control", |ui| {
            ui.horizontal(|ui| {
                badge(
                    ui,
                    if self.demo {
                        "SIM"
                    } else if self.connected() {
                        "LIVE"
                    } else {
                        "OFFLINE"
                    },
                    if self.demo { ORANGE } else { TEAL },
                );
                ui.label(format!("{} channels", self.status.len()));
                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                    if ui
                        .add_enabled(
                            enabled,
                            egui::Button::new("Close all").min_size(Vec2::new(100.0, 30.0)),
                        )
                        .clicked()
                    {
                        self.operate(Operation::Close, self.status.keys().copied().collect());
                    }
                    if ui
                        .add_enabled(
                            enabled,
                            egui::Button::new("Open all")
                                .min_size(Vec2::new(100.0, 30.0))
                                .fill(Color32::from_rgb(48, 107, 214)),
                        )
                        .clicked()
                    {
                        self.operate(Operation::Open, self.status.keys().copied().collect());
                    }
                });
            });
            ui.add_space(8.0);
            ui.horizontal_wrapped(|ui| {
                if self.pending.is_some() {
                    ui.spinner();
                }
                ui.label(RichText::new(&self.message).color(if self.error { RED } else { MUTED }));
            });
        });
        ui.add_space(12.0);
        if self.status.is_empty() {
            ui.add_space(60.0);
            ui.vertical_centered(|ui| {
                ui.label(RichText::new("Select your shutter controller").size(22.0));
                ui.add_space(10.0);
                ui.label(RichText::new("Find Pico W → select a device → Connect").color(MUTED));
                ui.label(
                    RichText::new("Channels appear after the first successful status read.")
                        .color(MUTED),
                );
            });
            return;
        }
        let values: Vec<_> = self
            .status
            .iter()
            .map(|(&ch, &angle)| (ch, angle))
            .collect();
        let columns = if ui.available_width() >= 460.0 { 2 } else { 1 };
        let mut action = None;
        egui::ScrollArea::vertical()
            .id_salt("channels")
            .show(ui, |ui| {
                for row in values.chunks(columns) {
                    ui.columns(columns, |cells| {
                        for (cell, &(channel, angle)) in cells.iter_mut().zip(row) {
                            section(cell, &format!("CH{channel:02}"), |ui| {
                                ui.horizontal(|ui| {
                                    ui.label(RichText::new("Commanded position").color(MUTED));
                                    badge(
                                        ui,
                                        if self.demo { "SIM" } else { "COMMAND" },
                                        if self.demo { ORANGE } else { BLUE },
                                    );
                                });
                                ui.add_space(10.0);
                                ui.horizontal(|ui| {
                                    ui.label(
                                        RichText::new(format!("{angle:.0}°"))
                                            .monospace()
                                            .size(36.0)
                                            .color(TEAL),
                                    );
                                    ui.with_layout(
                                        egui::Layout::right_to_left(egui::Align::Center),
                                        |ui| {
                                            shutter_symbol(ui, angle);
                                        },
                                    );
                                });
                                ui.add_space(10.0);
                                ui.add(
                                    egui::ProgressBar::new(angle as f32 / 180.0)
                                        .fill(TEAL)
                                        .desired_height(4.0),
                                );
                                ui.horizontal(|ui| {
                                    ui.small(RichText::new("0°").color(MUTED));
                                    ui.with_layout(
                                        egui::Layout::right_to_left(egui::Align::Center),
                                        |ui| {
                                            ui.small(RichText::new("180°").color(MUTED));
                                        },
                                    );
                                });
                                ui.add_space(8.0);
                                ui.add_enabled_ui(enabled, |ui| {
                                    ui.columns(3, |buttons| {
                                        for (index, label, operation) in [
                                            (0, "Close", Operation::Close),
                                            (1, "Open", Operation::Open),
                                            (2, "Toggle", Operation::Toggle),
                                        ] {
                                            if buttons[index]
                                                .add_sized(
                                                    [buttons[index].available_width(), 29.0],
                                                    egui::Button::new(label),
                                                )
                                                .clicked()
                                            {
                                                action = Some((operation, channel));
                                            }
                                        }
                                    });
                                });
                            });
                        }
                    });
                    ui.add_space(12.0);
                }
                if let Some(last) = &self.last_command {
                    ui.label(RichText::new("Last acknowledged action").color(MUTED));
                    ui.label(last);
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
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        self.receive();
        if self.connected() && self.pending.is_none() && Instant::now() >= self.next_refresh {
            self.refresh();
        }
        egui::TopBottomPanel::top("header")
            .exact_height(49.0)
            .frame(
                egui::Frame::new()
                    .fill(BG)
                    .inner_margin(egui::Margin::symmetric(16, 10)),
            )
            .show(ctx, |ui| {
                ui.horizontal(|ui| {
                    ui.label(RichText::new("KohdaLab Shutter").size(21.0).strong());
                    ui.add_space(8.0);
                    badge(
                        ui,
                        if self.demo {
                            "DEMO · NO HARDWARE"
                        } else {
                            "PICO W"
                        },
                        if self.demo { ORANGE } else { BLUE },
                    );
                    ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                        ui.label(
                            RichText::new(format!("v{}", env!("CARGO_PKG_VERSION"))).color(MUTED),
                        );
                    });
                });
            });
        egui::TopBottomPanel::bottom("footer")
            .exact_height(28.0)
            .show(ctx, |ui| {
                ui.horizontal(|ui| {
                    ui.label(
                        RichText::new(if self.demo {
                            "Simulation only · network disabled"
                        } else {
                            "Pico W · MicroPython firmware"
                        })
                        .small()
                        .color(MUTED),
                    );
                    ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                        ui.label(
                            RichText::new("Commanded angles ≠ measured shutter position")
                                .small()
                                .color(MUTED),
                        );
                    });
                });
            });
        egui::SidePanel::left("connection")
            .exact_width(278.0)
            .resizable(false)
            .frame(egui::Frame::new().fill(BG).inner_margin(12))
            .show(ctx, |ui| {
                egui::ScrollArea::vertical()
                    .id_salt("connection-scroll")
                    .show(ui, |ui| self.connection_panel(ui));
            });
        egui::SidePanel::right("details")
            .exact_width(270.0)
            .resizable(false)
            .frame(egui::Frame::new().fill(BG).inner_margin(12))
            .show(ctx, |ui| {
                egui::ScrollArea::vertical()
                    .id_salt("detail-scroll")
                    .show(ui, |ui| self.detail_panel(ui));
            });
        egui::CentralPanel::default()
            .frame(egui::Frame::new().fill(BG).inner_margin(12))
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

fn shutter_symbol(ui: &mut egui::Ui, angle: u16) {
    let (rect, _) = ui.allocate_exact_size(Vec2::splat(48.0), egui::Sense::hover());
    let centre = rect.center();
    ui.painter()
        .circle_stroke(centre, 21.0, Stroke::new(1.0_f32, BORDER));
    let direction = Vec2::angled((angle as f32 - 90.0).to_radians()) * 16.0;
    ui.painter().line_segment(
        [centre - direction, centre + direction],
        Stroke::new(3.0_f32, TEAL),
    );
    ui.painter().circle_filled(centre, 3.0, TEXT);
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
    let success = Arc::new(AtomicBool::new(false));
    let flag = success.clone();
    let expected_screenshot = args.screenshot.is_some();
    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_inner_size([1240.0, 740.0])
            .with_min_inner_size([1120.0, 650.0]),
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
}
