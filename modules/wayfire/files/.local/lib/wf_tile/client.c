/* One request per connection. No shell evaluation, Python startup or Wayfire
 * reconnection on the hotkey path. Exit 75 asks the launcher to start the daemon. */
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/time.h>
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <errno.h>

int main(int argc, char **argv) {
    struct sockaddr_un address = {.sun_family = AF_UNIX};
    const char *override = getenv("WF_TILE_SOCKET"), *runtime = getenv("XDG_RUNTIME_DIR");
    int n;
    if (override) n = snprintf(address.sun_path, sizeof(address.sun_path), "%s", override);
    else if (runtime) n = snprintf(address.sun_path, sizeof(address.sun_path), "%s/wf-tile/control.sock", runtime);
    else n = snprintf(address.sun_path, sizeof(address.sun_path), "/run/user/%lu/wf-tile/control.sock", (unsigned long)getuid());
    if (n < 0 || (size_t)n >= sizeof(address.sun_path)) return 75;
    char request[2048]; size_t used = 0;
    if (argc < 2) { fputs("wf-tile-ctl: missing action\n", stderr); return 1; }
    for (int i = 1; i < argc; i++) {
        for (const unsigned char *p = (unsigned char *)argv[i]; *p; p++) {
            if (!(isalnum(*p) || strchr("_-.:/", *p))) {
                fputs("wf-tile-ctl: invalid argument\n", stderr); return 1;
            }
        }
        size_t size = strlen(argv[i]);
        if (!size || used + size + 2 >= sizeof(request)) return 1;
        if (used) request[used++] = ' ';
        memcpy(request + used, argv[i], size); used += size;
    }
    request[used++] = '\n';
    int fd = socket(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0);
    if (fd < 0) return 75;
    struct timeval timeout = {.tv_sec = 5};
    setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
    setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout));
    if (connect(fd, (struct sockaddr *)&address, sizeof(address))) { close(fd); return 75; }
    for (size_t sent = 0; sent < used;) {
        ssize_t count = send(fd, request + sent, used - sent, MSG_NOSIGNAL);
        if (count < 0 && errno == EINTR) continue;
        if (count <= 0) { close(fd); return 1; } /* Never retry an ambiguous mutation. */
        sent += count;
    }
    char reply[65536]; size_t count = 0;
    while (count < sizeof(reply) - 1) {
        ssize_t got = read(fd, reply + count, sizeof(reply) - count - 1);
        if (got < 0 && errno == EINTR) continue;
        if (got <= 0) break;
        count += got;
        if (memchr(reply, '\n', count)) break;
    }
    close(fd); reply[count] = 0;
    if (count >= 3 && !strncmp(reply, "OK ", 3)) {
        if (count > 4) fputs(reply + 3, stdout);
        return 0;
    }
    fputs(count ? reply : "wf-tile: service did not reply\n", stderr);
    return 1;
}
