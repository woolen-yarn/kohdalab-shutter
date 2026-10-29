use std::collections::BTreeMap;
use std::io::{Error, ErrorKind, Result};

pub type Status = BTreeMap<u8, u16>;

pub fn parse_status(raw: &str) -> Result<Status> {
    let mut channels = Status::new();
    for field in raw.trim().split(',') {
        let (name, angle) = field.trim().split_once('=').ok_or_else(invalid_status)?;
        let channel: u8 = name
            .trim()
            .to_ascii_uppercase()
            .strip_prefix("CH")
            .ok_or_else(invalid_status)?
            .parse()
            .map_err(|_| invalid_status())?;
        let angle: u16 = angle.trim().parse().map_err(|_| invalid_status())?;
        if channel > 15 || angle > 180 || channels.insert(channel, angle).is_some() {
            return Err(invalid_status());
        }
    }
    Ok(channels)
}

fn invalid_status() -> Error {
    Error::new(
        ErrorKind::InvalidData,
        "Invalid STATUS response from Pico W",
    )
}

pub fn format_status(status: &Status) -> String {
    status
        .iter()
        .map(|(ch, angle)| format!("CH{ch}={angle}"))
        .collect::<Vec<_>>()
        .join(", ")
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Operation {
    Open,
    Close,
    Toggle,
}

impl Operation {
    pub fn command(self, channel: u8) -> Result<String> {
        if channel > 15 {
            return Err(Error::new(
                ErrorKind::InvalidInput,
                "Channel must be in 0..15",
            ));
        }
        let op = match self {
            Self::Open => "OPEN",
            Self::Close => "CLOSE",
            Self::Toggle => "TOGGLE",
        };
        Ok(format!("{op} {channel}"))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn status_validation() {
        let status = parse_status(" CH1=90, ch0=3 ").unwrap();
        assert_eq!(format_status(&status), "CH0=3, CH1=90");
        for invalid in [
            "",
            "ERR",
            "CH0=0,",
            "CH0=0,CH0=90",
            "CH16=0",
            "CH-1=0",
            "CH0=181",
            "CH0=-1",
            "CH0=foo",
            "X0=0",
            "CH0=0=1",
        ] {
            assert!(parse_status(invalid).is_err(), "{invalid}");
        }
    }
    #[test]
    fn commands_validate_channel() {
        assert_eq!(Operation::Open.command(0).unwrap(), "OPEN 0");
        assert_eq!(Operation::Close.command(15).unwrap(), "CLOSE 15");
        assert_eq!(Operation::Toggle.command(2).unwrap(), "TOGGLE 2");
        assert!(Operation::Open.command(16).is_err());
    }
}
