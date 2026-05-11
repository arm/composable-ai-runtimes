use std::env;
use std::error::Error;
use std::net::SocketAddr;

pub(crate) const DEFAULT_API_LISTEN_ADDR: &str = "0.0.0.0:50051";
pub(crate) const API_LISTEN_ADDR_ENV: &str = "CAMERA_API_LISTEN_ADDR";

pub(crate) fn api_listen_addr() -> Result<SocketAddr, Box<dyn Error>> {
    let args = env::args().skip(1).collect::<Vec<String>>();
    let listen_addr = parse_listen_addr_arg(&args)?
        .or_else(|| env::var(API_LISTEN_ADDR_ENV).ok())
        .unwrap_or_else(|| DEFAULT_API_LISTEN_ADDR.to_string());

    Ok(listen_addr.parse()?)
}

pub(crate) fn parse_listen_addr_arg(args: &[String]) -> Result<Option<String>, Box<dyn Error>> {
    match args {
        [] => Ok(None),
        [flag] if flag == "--listen-addr" => Err("missing value for --listen-addr".into()),
        [flag, listen_addr] if flag == "--listen-addr" => Ok(Some(listen_addr.clone())),
        [flag, _, unexpected_arg, ..] if flag == "--listen-addr" => {
            Err(format!("unexpected argument: {unexpected_arg}").into())
        }
        [unexpected_arg, ..] => Err(format!("unexpected argument: {unexpected_arg}").into()),
    }
}
