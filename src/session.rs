//! Typed responses for the Pico W multi-user shutter session protocol.

use serde::Deserialize;
use std::io::{Error, ErrorKind, Result};

#[derive(Clone, Debug, PartialEq, Eq, serde::Serialize, Deserialize)]
pub struct ChannelInfo {
    pub id: u8,
    pub label: String,
    pub locked: bool,
}

#[derive(Clone, Debug, PartialEq, Eq, serde::Serialize, Deserialize)]
pub struct ControllerInfo {
    pub protocol: u8,
    pub device_id: String,
    pub label: String,
    pub lease_ms: u32,
    pub channels: Vec<ChannelInfo>,
}

pub(crate) fn parse_info(value: serde_json::Value) -> Result<ControllerInfo> {
    let info: ControllerInfo = serde_json::from_value(value)
        .map_err(|_| invalid("Invalid controller information response from Pico W"))?;
    if info.protocol != 2
        || info.device_id.is_empty()
        || !info.device_id.bytes().all(|byte| byte.is_ascii_hexdigit())
        || info.label.is_empty()
        || info.lease_ms == 0
        || info.channels.is_empty()
        || info.channels.len() > 16
        || info
            .channels
            .iter()
            .any(|channel| channel.id > 15 || channel.label.is_empty())
    {
        return Err(invalid(
            "Invalid controller information response from Pico W",
        ));
    }
    let mut ids: Vec<_> = info.channels.iter().map(|channel| channel.id).collect();
    ids.sort_unstable();
    if ids.windows(2).any(|pair| pair[0] == pair[1]) {
        return Err(invalid(
            "Invalid controller information response from Pico W",
        ));
    }
    Ok(info)
}

pub(crate) fn invalid(message: &str) -> Error {
    Error::new(ErrorKind::InvalidData, message)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn controller_info_requires_unique_valid_channels() {
        let value = json!({"protocol":2,"device_id":"a0ff","label":"Bay A","lease_ms":15000,
            "channels":[{"id":0,"label":"CH00","locked":false}]});
        assert_eq!(parse_info(value).unwrap().label, "Bay A");
        for value in [
            json!({"protocol":1,"device_id":"a0","label":"x","lease_ms":1,"channels":[]}),
            json!({"protocol":2,"device_id":"z","label":"x","lease_ms":1,"channels":[{"id":0,"label":"x","locked":false}]}),
            json!({"protocol":2,"device_id":"a0","label":"x","lease_ms":1,"channels":[{"id":0,"label":"x","locked":false},{"id":0,"label":"x","locked":false}]}),
        ] {
            assert!(parse_info(value).is_err());
        }
    }
}
