#include "client.h"

#include <pipewire/pipewire.h>
#include <spa/utils/list.h>
#include <spa/utils/string.h>

#include <stdbool.h>
#include <signal.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

const char PWC_MEDIA_CLASS_VIDEO_SOURCE[] = "Video/Source";
static struct pwc_client *g_client = NULL;

struct pwc_node {
    struct spa_list link;
    uint32_t id;
    char *name;
    char *media_class;
};

struct pwc_link {
    struct spa_list link;
    uint32_t id;
    uint32_t output_node_id;
    uint32_t input_node_id;
    uint32_t output_port_id;
    uint32_t input_port_id;
};

struct pwc_client {
    struct pw_main_loop *loop;
    struct pw_context *context;
    struct pw_core *core;
    struct pw_registry *registry;
    struct spa_hook registry_listener;
    struct spa_list nodes;
    struct spa_list links;
    pwc_event_cb event_cb;
    void *event_userdata;
};

static char *dup_prop(const struct spa_dict *props, const char *key)
{
    if (!props || !key)
        return NULL;

    const char *value = spa_dict_lookup(props, key);
    return value ? strdup(value) : NULL;
}

static struct pwc_node *find_node(const struct pwc_client *client, uint32_t id)
{
    struct pwc_node *node;
    spa_list_for_each(node, &client->nodes, link) {
        if (node->id == id)
            return node;
    }
    return NULL;
}

static void free_node(struct pwc_node *node)
{
    if (!node)
        return;
    free(node->name);
    free(node->media_class);
    free(node);
}

static void free_link(struct pwc_link *link)
{
    if (!link)
        return;
    free(link);
}

static void pwc_destroy_client(struct pwc_client *client);

static void copy_event_name(char out[PWC_MAX_NAME_LEN], const char *in)
{
    if (!in) {
        out[0] = '\0';
        return;
    }
    snprintf(out, PWC_MAX_NAME_LEN, "%s", in);
}

static void emit_camera_event(struct pwc_client *client, pwc_event_type_t type, uint32_t id, const char *name)
{
    if (!client->event_cb)
        return;

    struct pwc_event event = {0};
    event.type = type;
    event.id = id;
    copy_event_name(event.name, name);

    client->event_cb(&event, client->event_userdata);
}

static void emit_stream_event(struct pwc_client *client,
                              pwc_event_type_t type,
                              uint32_t link_id,
                              uint32_t camera_node_id,
                              uint32_t consumer_node_id,
                              const char *camera_name,
                              const char *consumer_name)
{
    if (!client->event_cb)
        return;

    struct pwc_event event = {0};
    event.type = type;
    event.id = link_id;
    event.camera_node_id = camera_node_id;
    event.consumer_node_id = consumer_node_id;
    copy_event_name(event.camera_name, camera_name);
    copy_event_name(event.consumer_name, consumer_name);

    client->event_cb(&event, client->event_userdata);
}

static bool node_is_video_source(const struct pwc_node *node)
{
    return node &&
           node->media_class &&
           strcmp(node->media_class, PWC_MEDIA_CLASS_VIDEO_SOURCE) == 0;
}

static void handle_global_node(struct pwc_client *client,
                               uint32_t id,
                               const struct spa_dict *props)
{
    struct pwc_node *node = calloc(1, sizeof(*node));
    if (!node)
        return;
    node->id = id;
    node->name = dup_prop(props, PW_KEY_NODE_DESCRIPTION);
    node->media_class = dup_prop(props, PW_KEY_MEDIA_CLASS);
    spa_list_append(&client->nodes, &node->link);

    const char *name = node->name ? node->name : "(unknown)";

    if (node_is_video_source(node))
        emit_camera_event(client, PWC_EVENT_CAMERA_ADDED, id, name);
}

static void handle_global_link(struct pwc_client *client,
                               uint32_t id,
                               const struct spa_dict *props)
{
    struct pwc_link *link = calloc(1, sizeof(*link));
    if (!link)
        return;
    link->id = id;

    const char *out_node = spa_dict_lookup(props, PW_KEY_LINK_OUTPUT_NODE);
    const char *in_node = spa_dict_lookup(props, PW_KEY_LINK_INPUT_NODE);
    const char *out_port = spa_dict_lookup(props, PW_KEY_LINK_OUTPUT_PORT);
    const char *in_port = spa_dict_lookup(props, PW_KEY_LINK_INPUT_PORT);

    if (out_node) {
        uint32_t value;
        if (spa_atou32(out_node, &value, 10))
            link->output_node_id = value;
    }
    if (in_node) {
        uint32_t value;
        if (spa_atou32(in_node, &value, 10))
            link->input_node_id = value;
    }
    if (out_port) {
        uint32_t value;
        if (spa_atou32(out_port, &value, 10))
            link->output_port_id = value;
    }
    if (in_port) {
        uint32_t value;
        if (spa_atou32(in_port, &value, 10))
            link->input_port_id = value;
    }

    spa_list_append(&client->links, &link->link);

    struct pwc_node *out_node_info = find_node(client, link->output_node_id);
    struct pwc_node *in_node_info = find_node(client, link->input_node_id);
    const char *camera_name = NULL;
    const char *consumer_name = NULL;
    uint32_t camera_id = 0;
    uint32_t consumer_id = 0;
    int emit = 0;

    if (node_is_video_source(out_node_info)) {
        emit = 1;
        camera_id = link->output_node_id;
        consumer_id = link->input_node_id;
        camera_name = out_node_info->name;
        consumer_name = in_node_info ? in_node_info->name : NULL;
    } else if (node_is_video_source(in_node_info)) {
        emit = 1;
        camera_id = link->input_node_id;
        consumer_id = link->output_node_id;
        camera_name = in_node_info->name;
        consumer_name = out_node_info ? out_node_info->name : NULL;
    }

    if (emit) {
        emit_stream_event(client, PWC_EVENT_STREAM_ADDED, link->id,
                          camera_id, consumer_id,
                          camera_name, consumer_name);
    }
}

static void on_global(void *data,
                      uint32_t id,
                      uint32_t permissions,
                      const char *type,
                      uint32_t version,
                      const struct spa_dict *props)
{
    struct pwc_client *client = data;
    (void)permissions;
    (void)version;

    if (!props)
        return;

    if (strcmp(type, PW_TYPE_INTERFACE_Node) == 0) {
        handle_global_node(client, id, props);
        return;
    }

    if (strcmp(type, PW_TYPE_INTERFACE_Link) == 0) {
        handle_global_link(client, id, props);
        return;
    }
}

static void handle_global_remove_node(struct pwc_client *client, uint32_t id)
{
    struct pwc_node *node;
    spa_list_for_each(node, &client->nodes, link) {
        if (node->id == id) {
            if (node_is_video_source(node)) {
                emit_camera_event(client, PWC_EVENT_CAMERA_REMOVED, id,
                                  node->name ? node->name : "(unknown)");
            }
            spa_list_remove(&node->link);
            free_node(node);
            return;
        }
    }
}

static void handle_global_remove_link(struct pwc_client *client, uint32_t id)
{
    struct pwc_link *link;
    spa_list_for_each(link, &client->links, link) {
        if (link->id == id) {
            struct pwc_node *out_node_info = find_node(client, link->output_node_id);
            struct pwc_node *in_node_info = find_node(client, link->input_node_id);
            if (node_is_video_source(out_node_info)) {
                emit_stream_event(client, PWC_EVENT_STREAM_REMOVED, link->id,
                                  link->output_node_id, link->input_node_id,
                                  out_node_info->name, in_node_info ? in_node_info->name : NULL);
            } else if (node_is_video_source(in_node_info)) {
                emit_stream_event(client, PWC_EVENT_STREAM_REMOVED, link->id,
                                  link->input_node_id, link->output_node_id,
                                  in_node_info->name, out_node_info ? out_node_info->name : NULL);
            }
            spa_list_remove(&link->link);
            free_link(link);
            return;
        }
    }
}

static void on_global_remove(void *data, uint32_t id)
{
    struct pwc_client *client = data;

    handle_global_remove_node(client, id);
    handle_global_remove_link(client, id);
}

static const struct pw_registry_events registry_events = {
    PW_VERSION_REGISTRY_EVENTS,
    .global = on_global,
    .global_remove = on_global_remove,
};

struct pwc_client *pwc_create(pwc_event_cb cb, void *userdata)
{
    if (g_client)
        return g_client;

    struct pwc_client *client = calloc(1, sizeof(*client));
    if (!client)
        return NULL;

    client->event_cb = cb;
    client->event_userdata = userdata;
    spa_list_init(&client->nodes);
    spa_list_init(&client->links);

    pw_init(NULL, NULL);

    client->loop = pw_main_loop_new(NULL);
    if (!client->loop)
        goto fail;

    client->context = pw_context_new(pw_main_loop_get_loop(client->loop), NULL, 0);
    if (!client->context)
        goto fail;

    client->core = pw_context_connect(client->context, NULL, 0);
    if (!client->core)
        goto fail;

    client->registry = pw_core_get_registry(client->core, PW_VERSION_REGISTRY, 0);
    if (!client->registry)
        goto fail;

    pw_registry_add_listener(client->registry, &client->registry_listener, &registry_events, client);

    g_client = client;
    return client;

fail:
    pwc_destroy_client(client);
    return NULL;
}

static void on_quit_signal(void *data, int signal_number)
{
    struct pwc_client *client = data;
    (void)signal_number;
    pw_main_loop_quit(client->loop);
}

int pwc_run(void)
{
    struct pwc_client *client = g_client;
    if (!client || !client->core)
        return -1;

    sigset_t mask;
    sigset_t prev_mask;
    sigemptyset(&mask);
    sigaddset(&mask, SIGINT);
    sigaddset(&mask, SIGTERM);
    if (sigprocmask(SIG_BLOCK, &mask, &prev_mask) != 0)
        return -1;

    pw_loop_add_signal(pw_main_loop_get_loop(client->loop), SIGINT, on_quit_signal, client);
    pw_loop_add_signal(pw_main_loop_get_loop(client->loop), SIGTERM, on_quit_signal, client);

    pw_main_loop_run(client->loop);
    sigprocmask(SIG_SETMASK, &prev_mask, NULL);
    return 0;
}

static size_t count_cameras(const struct pwc_client *client)
{
    size_t count = 0;
    struct pwc_node *node;
    spa_list_for_each(node, &client->nodes, link) {
        if (node_is_video_source(node))
            count++;
    }
    return count;
}

static size_t fill_cameras(const struct pwc_client *client,
                           struct pwc_camera_info *items,
                           size_t capacity)
{
    size_t idx = 0;
    struct pwc_node *node;
    spa_list_for_each(node, &client->nodes, link) {
        if (!node_is_video_source(node))
            continue;
        if (idx >= capacity)
            break;
        items[idx].id = node->id;
        if (node->name)
            snprintf(items[idx].name, sizeof(items[idx].name), "%s", node->name);
        else
            items[idx].name[0] = '\0';
        idx++;
    }
    return idx;
}

static bool stream_matches(const struct pwc_client *client,
                           const struct pwc_link *link,
                           struct pwc_stream_info *out)
{
    struct pwc_node *out_node = find_node(client, link->output_node_id);
    struct pwc_node *in_node = find_node(client, link->input_node_id);
    struct pwc_node *camera = node_is_video_source(out_node) ? out_node :
                              (node_is_video_source(in_node) ? in_node : NULL);
    struct pwc_node *consumer = (camera == out_node) ? in_node :
                                (camera == in_node ? out_node : NULL);
    if (!camera || !consumer)
        return false;
    if (out) {
        out->link_id = link->id;
        out->camera_node_id = camera->id;
        out->consumer_node_id = consumer->id;
        if (camera->name)
            snprintf(out->camera_name, sizeof(out->camera_name), "%s", camera->name);
        else
            out->camera_name[0] = '\0';
        if (consumer->name)
            snprintf(out->consumer_name, sizeof(out->consumer_name), "%s", consumer->name);
        else
            out->consumer_name[0] = '\0';
    }

    return true;
}

static size_t count_streams(const struct pwc_client *client)
{
    size_t count = 0;
    struct pwc_link *link;
    spa_list_for_each(link, &client->links, link) {
        if (stream_matches(client, link, NULL))
            count++;
    }
    return count;
}

static size_t fill_streams(const struct pwc_client *client,
                           struct pwc_stream_info *items,
                           size_t capacity)
{
    size_t idx = 0;
    struct pwc_link *link;
    spa_list_for_each(link, &client->links, link) {
        if (idx >= capacity)
            break;
        if (stream_matches(client, link, &items[idx]))
            idx++;
    }
    return idx;
}


int pwc_list_cameras(struct pwc_camera_info **out_items,
                     size_t *out_count)
{
    const struct pwc_client *client = g_client;
    if (!client || !out_items || !out_count)
        return -1;

    *out_items = NULL;
    *out_count = 0;

    size_t count = count_cameras(client);
    if (count == 0)
        return 0;

    struct pwc_camera_info *items = calloc(count, sizeof(*items));
    if (!items)
        return -1;

    size_t idx = fill_cameras(client, items, count);
    *out_items = items;
    *out_count = idx;
    return 0;
}

int pwc_list_streams(struct pwc_stream_info **out_items,
                     size_t *out_count)
{
    const struct pwc_client *client = g_client;
    if (!client || !out_items || !out_count)
        return -1;

    *out_items = NULL;
    *out_count = 0;

    size_t count = count_streams(client);
    if (count == 0)
        return 0;

    struct pwc_stream_info *items = calloc(count, sizeof(*items));
    if (!items)
        return -1;

    size_t idx = fill_streams(client, items, count);
    *out_items = items;
    *out_count = idx;
    return 0;
}

void pwc_free_cameras(struct pwc_camera_info *items, size_t count)
{
    (void)count;
    free(items);
}

void pwc_free_streams(struct pwc_stream_info *items, size_t count)
{
    (void)count;
    free(items);
}

static void pwc_destroy_client(struct pwc_client *client)
{
    if (client == NULL)
        return;

    struct pwc_node *node;
    while (!spa_list_is_empty(&client->nodes)) {
        node = spa_list_first(&client->nodes, struct pwc_node, link);
        spa_list_remove(&node->link);
        free_node(node);
    }

    struct pwc_link *link;
    while (!spa_list_is_empty(&client->links)) {
        link = spa_list_first(&client->links, struct pwc_link, link);
        spa_list_remove(&link->link);
        free_link(link);
    }

    if (client->core)
        pw_core_disconnect(client->core);
    if (client->context)
        pw_context_destroy(client->context);
    if (client->loop)
        pw_main_loop_destroy(client->loop);

    pw_deinit();
    free(client);
}

void pwc_destroy(void)
{
    if (!g_client)
        return;
    pwc_destroy_client(g_client);
    g_client = NULL;
}
