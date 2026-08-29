#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void unsafe_function(char *input) {
    char buffer[100];
    strcpy(buffer, input);  // Buffer overflow risk
    printf(input);  // Format string vulnerability
}

int main() {
    char *ptr = malloc(100);
    strcpy(ptr, "hello");
    // Missing free(ptr) - memory leak
    return 0;
}