use crate::config::parse_listen_addr_arg;

#[test]
fn parse_listen_addr_arg_accepts_no_args() {
    let args = vec![];

    let listen_addr = parse_listen_addr_arg(&args).expect("parse should succeed");

    assert_eq!(listen_addr, None);
}

#[test]
fn parse_listen_addr_arg_accepts_listen_addr_flag() {
    let args = vec!["--listen-addr".to_string(), "127.0.0.1:50052".to_string()];

    let listen_addr = parse_listen_addr_arg(&args).expect("parse should succeed");

    assert_eq!(listen_addr.as_deref(), Some("127.0.0.1:50052"));
}

#[test]
fn parse_listen_addr_arg_rejects_missing_listen_addr_value() {
    let args = vec!["--listen-addr".to_string()];

    let error = parse_listen_addr_arg(&args).expect_err("parse should fail");

    assert_eq!(error.to_string(), "missing value for --listen-addr");
}

#[test]
fn parse_listen_addr_arg_rejects_unexpected_flag() {
    let args = vec!["--port".to_string(), "50052".to_string()];

    let error = parse_listen_addr_arg(&args).expect_err("parse should fail");

    assert_eq!(error.to_string(), "unexpected argument: --port");
}

#[test]
fn parse_listen_addr_arg_rejects_extra_args() {
    let args = vec![
        "--listen-addr".to_string(),
        "127.0.0.1:50052".to_string(),
        "--extra".to_string(),
    ];

    let error = parse_listen_addr_arg(&args).expect_err("parse should fail");

    assert_eq!(error.to_string(), "unexpected argument: --extra");
}
