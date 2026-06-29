use super::config::{DEFAULT_API_LISTEN_ADDR, parse_listen_addr_arg, resolve_listen_addr};

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

#[test]
fn resolve_listen_addr_uses_default_when_cli_and_env_are_absent() {
    let args = vec![];

    let listen_addr = resolve_listen_addr(&args, None).expect("resolve should succeed");

    assert_eq!(
        listen_addr,
        DEFAULT_API_LISTEN_ADDR
            .parse()
            .expect("default address should parse")
    );
}

#[test]
fn resolve_listen_addr_uses_env_when_cli_flag_is_absent() {
    let args = vec![];

    let listen_addr =
        resolve_listen_addr(&args, Some("127.0.0.1:50052")).expect("resolve should succeed");

    assert_eq!(
        listen_addr,
        "127.0.0.1:50052".parse().expect("address should parse")
    );
}

#[test]
fn resolve_listen_addr_prefers_cli_flag_over_env() {
    let args = vec!["--listen-addr".to_string(), "127.0.0.1:50053".to_string()];

    let listen_addr =
        resolve_listen_addr(&args, Some("127.0.0.1:50052")).expect("resolve should succeed");

    assert_eq!(
        listen_addr,
        "127.0.0.1:50053".parse().expect("address should parse")
    );
}

#[test]
fn resolve_listen_addr_rejects_invalid_listen_addr_values() {
    let args = vec![];

    let error =
        resolve_listen_addr(&args, Some("not-a-socket-address")).expect_err("resolve should fail");

    assert_eq!(error.to_string(), "invalid socket address syntax");
}
