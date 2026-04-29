use std::time::Duration;

use pipewire as pw;

pub(crate) const VIDEO_SOURCE_MEDIA_CLASS: &str = "Video/Source";

pub fn is_camera_node<P>(global: &pw::registry::GlobalObject<P>) -> bool
where
    P: AsRef<pw::spa::utils::dict::DictRef>,
{
    if global.type_ != pw::types::ObjectType::Node {
        return false;
    }

    global.props.as_ref().is_some_and(|props| {
        props.as_ref().get(&pw::keys::MEDIA_CLASS) == Some(VIDEO_SOURCE_MEDIA_CLASS)
    })
}

#[derive(Debug)]
pub(crate) struct FibonacciBackoff {
    current: Duration,
    next: Duration,
    max_delay: Duration,
}

impl FibonacciBackoff {
    pub(crate) fn new(initial_delay: Duration, max_delay: Duration) -> Self {
        Self {
            current: initial_delay,
            next: initial_delay,
            max_delay,
        }
    }

    pub(crate) fn next_delay(&mut self) -> Duration {
        let delay = self.current.min(self.max_delay);
        let next = self.current.saturating_add(self.next);
        self.current = self.next;
        self.next = next;

        delay
    }
}
