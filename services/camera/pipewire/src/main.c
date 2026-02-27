#include "client.h"

#include <stdio.h>

static void on_event(const struct pwc_event *event, void *userdata)
{
    (void)userdata;

    const char *type = "unknown";
    switch (event->type) {
    case PWC_EVENT_CAMERA_ADDED:
        type = "camera-added";
        printf("event=%s id=%u name=%s\n", type, event->id, event->name[0] ? event->name : "(unknown)");
        break;
    case PWC_EVENT_CAMERA_REMOVED:
        type = "camera-removed";
        printf("event=%s id=%u name=%s\n", type, event->id, event->name[0] ? event->name : "(unknown)");
        break;
    case PWC_EVENT_STREAM_ADDED:
        type = "stream-added";
        printf("event=%s link_id=%u camera_node_id=%u consumer_node_id=%u camera_name=%s consumer_name=%s\n",
               type,
               event->id,
               event->camera_node_id,
               event->consumer_node_id,
               event->camera_name[0] ? event->camera_name : "(unknown)",
               event->consumer_name[0] ? event->consumer_name : "(unknown)");
        break;
    case PWC_EVENT_STREAM_REMOVED:
        type = "stream-removed";
        printf("event=%s link_id=%u camera_node_id=%u consumer_node_id=%u camera_name=%s consumer_name=%s\n",
               type,
               event->id,
               event->camera_node_id,
               event->consumer_node_id,
               event->camera_name[0] ? event->camera_name : "(unknown)",
               event->consumer_name[0] ? event->consumer_name : "(unknown)");
        break;
    }
    fflush(stdout);
}

int main(void)
{
    if (!pwc_create(on_event, NULL)) {
        fprintf(stderr, "failed to create pipewire client\n");
        return 1;
    }

    if (pwc_run() != 0) {
        fprintf(stderr, "failed to run pipewire client\n");
        pwc_destroy();
        return 1;
    }

    pwc_destroy();

    return 0;
}
