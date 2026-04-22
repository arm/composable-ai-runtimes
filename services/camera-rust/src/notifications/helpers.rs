use pipewire as pw;

pub(crate) const VIDEO_SOURCE_MEDIA_CLASS: &str = "Video/Source";

pub(crate) fn is_camera_node<P>(global: &pw::registry::GlobalObject<P>) -> bool
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
