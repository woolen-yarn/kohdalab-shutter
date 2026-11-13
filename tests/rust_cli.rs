use std::{
    io::{BufRead, BufReader, Write},
    net::TcpListener,
    process::Command,
};

fn cli() -> Command {
    Command::new(env!("CARGO_BIN_EXE_kohdalab-shutter"))
}

#[test]
fn cli_help_and_arguments_work_without_hardware() {
    let help = cli().arg("--help").output().unwrap();
    assert!(help.status.success());
    assert!(String::from_utf8_lossy(&help.stdout).contains("discover"));
    for args in [
        vec!["--port", "0", "status"],
        vec!["--timeout-ms", "0", "status"],
        vec!["--host", "127.0.0.1", "--device", "aa", "status"],
    ] {
        assert!(!cli().args(args).output().unwrap().status.success());
    }
}

#[test]
fn status_reaches_mock_pico_and_formats_response() {
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let port = listener.local_addr().unwrap().port().to_string();
    let server = std::thread::spawn(move || {
        let (mut stream, _) = listener.accept().unwrap();
        let mut line = String::new();
        BufReader::new(stream.try_clone().unwrap())
            .read_line(&mut line)
            .unwrap();
        assert_eq!(line, "STATUS\n");
        stream.write_all(b"CH1=90,CH0=0\n").unwrap();
    });
    let output = cli()
        .args(["--host", "127.0.0.1", "--port", &port, "status"])
        .output()
        .unwrap();
    server.join().unwrap();
    assert!(output.status.success());
    assert_eq!(String::from_utf8(output.stdout).unwrap(), "CH0=0, CH1=90\n");
}

#[test]
fn invalid_channel_fails_before_sending_anything() {
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    listener.set_nonblocking(true).unwrap();
    let port = listener.local_addr().unwrap().port().to_string();
    let output = cli()
        .args(["--host", "127.0.0.1", "--port", &port, "open", "16"])
        .output()
        .unwrap();
    assert!(!output.status.success());
    assert!(String::from_utf8_lossy(&output.stderr).contains("0..15"));
    assert_eq!(
        listener.accept().unwrap_err().kind(),
        std::io::ErrorKind::WouldBlock
    );
}
