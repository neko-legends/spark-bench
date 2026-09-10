# Derived image for DeepSeek-V4.1-Flash NVMe-engram adapter on 4x GB10 (sm_120 aarch64).
# Based on 0xSero/deepseek-v4.1-flash-4x-rtx-pro-6000 (commit 5a7694d), re-based onto the
# LMSYS dev-dsv41 arm64 preview image. Patches vs upstream repo:
#   - adapter/engram_backend.py: sbsa-linux/aarch64-linux libcudart globs + loud failure (GB10 arm64)
#   - flash_mla_sm120.py overlay kept: 64-token page split for extra source + tagged scratch buffers
#   - sglang deepseekv32_detector.py: DSML parameter regex tolerates a missing string= attribute
#     (V4.1 model omits it; upstream drops the parameter -> tool calls parse with empty args)
FROM lmsysorg/sglang:dev-dsv41
WORKDIR /opt/dsv41
COPY adapter /opt/dsv41/adapter
RUN g++ -O2 -Wall -Wextra -Werror -std=c++17 -shared -fPIC -pthread \
    adapter/row_store.cpp -o adapter/librow_store.so
COPY runtime/flash_mla_sm120.py /sgl-workspace/sglang/python/sglang/kernels/ops/attention/flash_mla_sm120.py
COPY patch_detector.py /tmp/patch_detector.py
RUN python3 /tmp/patch_detector.py && rm /tmp/patch_detector.py
COPY boot.py /opt/dsv41/boot.py
COPY tests /opt/dsv41/tests
COPY benchmarks /opt/dsv41/benchmarks
COPY NOTICE /opt/dsv41/NOTICE
COPY LICENSE /opt/dsv41/LICENSE
COPY LICENSE.sglang /opt/dsv41/LICENSE.sglang
ENV PYTHONPATH=/opt/dsv41/adapter \
    MODEL_PATH=/models/DeepSeek-V4.1-Flash \
    STATE_PATH=/state OFFLOAD_MODE=nvme DSV41_CACHE_GIB=32
EXPOSE 8010
HEALTHCHECK --interval=30s --timeout=10s --start-period=30m --retries=3 \
    CMD ["python3", "/opt/dsv41/boot.py", "health"]
ENTRYPOINT ["python3", "-u", "/opt/dsv41/boot.py"]
CMD ["run"]
