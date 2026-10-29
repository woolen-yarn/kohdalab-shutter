use clap::{Parser, Subcommand};
use kohdalab_shutter::{
    DEFAULT_PORT,
    discovery::{self, Device},
    protocol::{Operation, format_status},
    transport::Client,
};
use std::{
    io::{self, Write},
    net::{Ipv4Addr, SocketAddrV4},
    time::Duration,
};

#[derive(Parser)]
#[command(
    version,
    about = "Control a Pico W shutter; automatically discover its IP"
)]
struct Args {
    /// IP or hostname; omit to discover the Pico W automatically
    #[arg(long, alias = "ip", global = true, conflicts_with = "device")]
    host: Option<String>,
    /// TCP port override (otherwise use discovered port or 12345)
    #[arg(long, global = true, value_parser = clap::value_parser!(u16).range(1..))]
    port: Option<u16>,
    /// Select a Pico by its unique ID (see discover)
    #[arg(long, global = true)]
    device: Option<String>,
    /// UDP discovery destination; use your subnet broadcast for multiple adapters
    #[arg(long, global = true, default_value = "255.255.255.255")]
    broadcast: Ipv4Addr,
    /// Per-attempt TCP timeout and discovery window, in milliseconds
    #[arg(long, global = true, default_value_t = 2000, value_parser = clap::value_parser!(u32).range(1..=60000))]
    timeout_ms: u32,
    #[arg(long, global = true, default_value_t = 3, value_parser = clap::value_parser!(u8).range(1..=10))]
    retries: u8,
    #[command(subcommand)]
    command: Option<Command>,
}

#[derive(Subcommand)]
enum Command {
    Discover,
    Status,
    Info,
    Label { label: String },
    Open { channel: u8 },
    Close { channel: u8 },
    Toggle { channel: u8 },
}

fn main() {
    if let Err(error) = run(Args::parse()) {
        eprintln!("ERROR: {error}");
        std::process::exit(1);
    }
}

fn run(args: Args) -> io::Result<()> {
    let timeout = Duration::from_millis(args.timeout_ms.into());
    let find = || {
        discovery::discover(
            SocketAddrV4::new(args.broadcast, discovery::DISCOVERY_PORT),
            timeout,
        )
    };
    if matches!(args.command, Some(Command::Discover)) {
        let devices = find()?;
        if devices.is_empty() {
            return Err(discovery::select_device(&[], None).unwrap_err());
        }
        for Device { id, address } in devices {
            println!("{id}\t{address}");
        }
        return Ok(());
    }
    let (host, port) = if let Some(host) = args.host {
        (host, args.port.unwrap_or(DEFAULT_PORT))
    } else {
        let device = discovery::select_device(&find()?, args.device.as_deref())?;
        eprintln!("Pico W {} at {}", device.id, device.address);
        (
            device.address.ip().to_string(),
            args.port.unwrap_or(device.address.port()),
        )
    };
    let client = Client::new(host, port, timeout, args.retries)?;
    match args.command {
        Some(command) => execute(&client, command),
        None => shell(&client),
    }
}

fn execute(client: &Client, command: Command) -> io::Result<()> {
    match command {
        Command::Status => {
            println!("{}", format_status(&client.status()?));
            return Ok(());
        }
        Command::Info => {
            let info = client.info().map_err(firmware_error)?;
            println!("{}\t{}\t{} ms", info.label, info.device_id, info.lease_ms);
            for channel in info.channels {
                println!(
                    "CH{:02}\t{}\t{}",
                    channel.id,
                    channel.label,
                    if channel.locked {
                        "in use"
                    } else {
                        "available"
                    }
                );
            }
            return Ok(());
        }
        Command::Label { label } => {
            client.set_label(&label).map_err(firmware_error)?;
            println!("OK (label saved)");
            return Ok(());
        }
        Command::Open { channel } => session_operate(client, Operation::Open, channel)?,
        Command::Close { channel } => session_operate(client, Operation::Close, channel)?,
        Command::Toggle { channel } => session_operate(client, Operation::Toggle, channel)?,
        Command::Discover => unreachable!(),
    }
    println!("OK (motion accepted)");
    Ok(())
}

fn session_operate(client: &Client, operation: Operation, channel: u8) -> io::Result<()> {
    let leased = client.claim(&[channel]).map_err(firmware_error)?;
    let result = leased.operate_many(operation, &[channel]);
    // Release is attempted even after an operation failure; its error only
    // replaces a successful operation because the operation result is more
    // useful when physical state might be ambiguous.
    let release = leased.release();
    result.map_err(firmware_error)?;
    release.map_err(firmware_error)
}

fn firmware_error(error: io::Error) -> io::Error {
    if error.kind() == io::ErrorKind::InvalidData {
        io::Error::new(
            io::ErrorKind::Unsupported,
            "This Pico W needs the multi-user firmware update before it can be controlled. Upload server/sessions.py and the updated server/main.py.",
        )
    } else {
        error
    }
}

fn shell(client: &Client) -> io::Result<()> {
    println!(
        "Target {}:{}. status | open n | close n | toggle n | quit",
        client.host, client.port
    );
    loop {
        print!("> ");
        io::stdout().flush()?;
        let mut line = String::new();
        if io::stdin().read_line(&mut line)? == 0 {
            return Ok(());
        }
        let words: Vec<_> = line.split_whitespace().collect();
        if words.is_empty() {
            continue;
        }
        if words == ["quit"] || words == ["exit"] {
            return Ok(());
        }
        let parse = Args::try_parse_from(std::iter::once("shutter").chain(words.iter().copied()));
        match parse {
            Ok(Args {
                command: Some(command),
                ..
            }) if !matches!(command, Command::Discover) => {
                if let Err(error) = execute(client, command) {
                    eprintln!("ERROR: {error}");
                }
            }
            _ => eprintln!("Use status | info | label NAME | open n | close n | toggle n | quit"),
        }
    }
}
