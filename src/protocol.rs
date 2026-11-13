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

#[derive(Clone, Debug, serde::Serialize)]
pub struct ChannelState {
    pub position: u16,
    pub target: Option<u16>,
    pub close_angle: Option<u16>,
    pub open_angle: Option<u16>,
    pub busy: bool,
}

impl ChannelState {
    pub fn name(&self) -> &'static str {
        if self.close_angle.is_none() || self.open_angle.is_none() {
            "Unknown"
        } else if self.busy || self.target.is_some_and(|target| target != self.position) {
            "Moving"
        } else if self.close_angle == Some(self.position) {
            "Close"
        } else if self.open_angle == Some(self.position) {
            "Open"
        } else {
            "Unknown"
        }
    }
}

#[derive(Clone, Debug, Default, serde::Serialize)]
pub struct Snapshot {
    pub channels: BTreeMap<u8, ChannelState>,
}

impl Snapshot {
    pub fn legacy(status: Status) -> Self {
        Self {
            channels: status
                .into_iter()
                .map(|(channel, position)| {
                    (
                        channel,
                        ChannelState {
                            position,
                            target: None,
                            close_angle: None,
                            open_angle: None,
                            busy: false,
                        },
                    )
                })
                .collect(),
        }
    }
    pub fn positions(&self) -> Status {
        self.channels
            .iter()
            .map(|(&channel, state)| (channel, state.position))
            .collect()
    }
    pub fn demo(status: &Status) -> Self {
        Self {
            channels: status
                .iter()
                .map(|(&channel, &position)| {
                    (
                        channel,
                        ChannelState {
                            position,
                            target: Some(position),
                            close_angle: Some(0),
                            open_angle: Some(90),
                            busy: false,
                        },
                    )
                })
                .collect(),
        }
    }
}

pub fn parse_state(raw: &str) -> Result<Snapshot> {
    let mut channels = BTreeMap::new();
    for field in raw.trim().split(',') {
        let (name, value) = field.trim().split_once('=').ok_or_else(invalid_status)?;
        let channel: u8 = name
            .trim()
            .strip_prefix("CH")
            .ok_or_else(invalid_status)?
            .parse()
            .map_err(|_| invalid_status())?;
        let values: Vec<u16> = value
            .split('/')
            .map(str::parse)
            .collect::<std::result::Result<_, _>>()
            .map_err(|_| invalid_status())?;
        if channel > 15
            || values.len() != 5
            || values[..4].iter().any(|&value| value > 180)
            || values[2] == values[3]
            || values[4] > 1
        {
            return Err(invalid_status());
        }
        let state = ChannelState {
            position: values[0],
            target: Some(values[1]),
            close_angle: Some(values[2]),
            open_angle: Some(values[3]),
            busy: values[4] == 1,
        };
        if channels.insert(channel, state).is_some() {
            return Err(invalid_status());
        }
    }
    Ok(Snapshot { channels })
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
    #[test]
    fn state_uses_actual_calibration_and_queued_motion() {
        let state = parse_state("CH0=10/10/10/70/0,CH1=70/70/10/70/0,CH2=10/70/10/70/1").unwrap();
        assert_eq!(state.channels[&0].name(), "Close");
        assert_eq!(state.channels[&1].name(), "Open");
        assert_eq!(state.channels[&2].name(), "Moving");
        assert_eq!(
            Snapshot::legacy([(0, 0)].into()).channels[&0].name(),
            "Unknown"
        );
        for raw in [
            "",
            "CH0=0/0/0/0/0",
            "CH0=0/0/0/90/2",
            "CH0=0/0/0/90",
            "CH0=181/0/0/90/0",
            "CH16=0/0/0/90/0",
            "CH0=0/0/0/90/0,CH0=0/0/0/90/0",
        ] {
            assert!(parse_state(raw).is_err(), "{raw}");
        }
    }
}
