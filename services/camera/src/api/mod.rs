mod camera_node_watch;
mod config;
mod parameters;
mod server;
mod service;
mod snapshot;

#[cfg(test)]
mod contract_tests;

pub use server::api_listen_addr;
pub use server::serve;

#[cfg(test)]
mod config_test;
#[cfg(test)]
mod parameters_test;
#[cfg(test)]
mod service_test;
#[cfg(test)]
mod snapshot_test;
