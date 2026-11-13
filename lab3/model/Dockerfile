FROM ollama/ollama@sha256:910d0d8107b538fb0894e63163eb195de0cc7aefcbc666dc62d3b18f71124592 AS upstream
# Keep only CPU libraries from the official distribution; no CUDA/Vulkan payload.
RUN mkdir -p /cpu/lib && cp -a /usr/lib/ollama/*.so* /cpu/lib/ && cp /usr/lib/ollama/llama-server /cpu/lib/ && cp /usr/lib/ollama/*LICENSE* /cpu/lib/
FROM ubuntu@sha256:2198e4c65076e9cb0b3d695219df667c0e3b0072da64ca3c2648aca17dcecaf5
COPY --from=upstream /usr/bin/ollama /usr/bin/ollama
COPY --from=upstream /cpu/lib/ /usr/lib/ollama/
COPY --from=upstream /lib/x86_64-linux-gnu/libstdc++.so.6* /lib/x86_64-linux-gnu/
COPY --from=upstream /lib/x86_64-linux-gnu/libgcc_s.so.1 /lib/x86_64-linux-gnu/libgcc_s.so.1
COPY --from=upstream /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/ca-certificates.crt
ENV OLLAMA_HOST=0.0.0.0:11434 OLLAMA_MODELS=/models OLLAMA_NO_CLOUD=1 OLLAMA_NUM_PARALLEL=1 OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_MAX_QUEUE=1 OLLAMA_CONTEXT_LENGTH=2048 HOME=/tmp
USER 10001:10001
EXPOSE 11434
ENTRYPOINT ["/usr/bin/ollama"]
CMD ["serve"]
