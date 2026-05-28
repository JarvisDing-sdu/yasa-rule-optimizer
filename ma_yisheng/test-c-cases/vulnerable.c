#include <stdio.h>
#include <stdlib.h>

int main() {
    char *cmd = getenv("USER_CMD");
    system(cmd);
    return 0;
}
