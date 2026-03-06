#include "client.h"

#include <pipewire/pipewire.h>
#include <spa/utils/list.h>
#include <spa/utils/string.h>

#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

const char PWC_MEDIA_CLASS_VIDEO_SOURCE[] = "Video/Source";

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
};

struct pwc_client {
    struct pw_main_loop *loop;
    struct pw_context *context;
    struct pw_core *core;
    struct pw_registry *registry;
    struct spa_hook registry_listener;
    struct spa_hook core_listener;
    struct spa_list nodes;
    struct spa_list links;
    int pending_sync;
    int has_error;
    int registry_listener_added;
    int core_listener_added;
};

static void pwc_destroy_client(struct pwc_client *client);

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
    spa_list_append(&client->links, &link->link);
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

static void on_core_done(void *data, uint32_t id, int seq)
{
    struct pwc_client *client = data;
    if (!client || !client->loop)
        return;

    if (id == PW_ID_CORE && seq == client->pending_sync)
        pw_main_loop_quit(client->loop);
}

static void on_core_error(void *data, uint32_t id, int seq, int res, const char *message)
{
    struct pwc_client *client = data;
    (void)id;
    (void)seq;
    (void)res;
    (void)message;
    if (!client || !client->loop)
        return;

    client->has_error = 1;
    pw_main_loop_quit(client->loop);
}

static const struct pw_core_events core_events = {
    PW_VERSION_CORE_EVENTS,
    .done = on_core_done,
    .error = on_core_error,
};

static struct pwc_client *pwc_create_internal(void)
{
    struct pwc_client *client = calloc(1, sizeof(*client));
    if (!client)
        return NULL;

    client->pending_sync = -1;
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
    client->registry_listener_added = 1;
    return client;

fail:
    pwc_destroy_client(client);
    return NULL;
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

static int pwc_list_cameras(const struct pwc_client *client,
                            struct pwc_camera_info **out_items,
                            size_t *out_count)
{
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

    *out_count = fill_cameras(client, items, count);
    *out_items = items;
    return 0;
}

static int pwc_list_streams(const struct pwc_client *client,
                            struct pwc_stream_info **out_items,
                            size_t *out_count)
{
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

    *out_count = fill_streams(client, items, count);
    *out_items = items;
    return 0;
}

static int build_snapshot_from_client(const struct pwc_client *client,
                                      struct pwc_snapshot *out_snapshot)
{
    if (!client || !out_snapshot)
        return -1;

    if (pwc_list_cameras(client, &out_snapshot->cameras, &out_snapshot->camera_count) != 0)
        goto fail;

    if (pwc_list_streams(client, &out_snapshot->streams, &out_snapshot->stream_count) != 0) {
        goto fail;
    }

    return 0;

fail:
    free(out_snapshot->cameras);
    free(out_snapshot->streams);
    out_snapshot->cameras = NULL;
    out_snapshot->streams = NULL;
    out_snapshot->camera_count = 0;
    out_snapshot->stream_count = 0;
    return -1;
}

struct pwc_snapshot *pwc_create_snapshot(void)
{
    struct pwc_snapshot *snapshot = calloc(1, sizeof(*snapshot));
    if (!snapshot)
        return NULL;

    struct pwc_client *client = pwc_create_internal();
    if (!client || !client->core) {
        pwc_snapshot_destroy(snapshot);
        return NULL;
    }

    pw_core_add_listener(client->core, &client->core_listener, &core_events, client);
    client->core_listener_added = 1;
    client->pending_sync = pw_core_sync(client->core, PW_ID_CORE, 0);
    if (client->pending_sync < 0) {
        pwc_destroy_client(client);
        pwc_snapshot_destroy(snapshot);
        return NULL;
    }

    pw_main_loop_run(client->loop);
    if (client->has_error) {
        pwc_destroy_client(client);
        pwc_snapshot_destroy(snapshot);
        return NULL;
    }

    int result = build_snapshot_from_client(client, snapshot);
    pwc_destroy_client(client);
    if (result != 0) {
        pwc_snapshot_destroy(snapshot);
        return NULL;
    }
    return snapshot;
}

void pwc_snapshot_destroy(struct pwc_snapshot *snapshot)
{
    if (!snapshot)
        return;
    free(snapshot->cameras);
    free(snapshot->streams);
    free(snapshot);
}

static void pwc_destroy_client(struct pwc_client *client)
{
    if (client == NULL)
        return;

    if (client->core_listener_added) {
        spa_hook_remove(&client->core_listener);
        client->core_listener_added = 0;
    }
    if (client->registry_listener_added) {
        spa_hook_remove(&client->registry_listener);
        client->registry_listener_added = 0;
    }

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
