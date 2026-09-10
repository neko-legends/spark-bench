"""dsv41-port patch: make the DSML parameter `string=` attribute optional.

Observed on GB10 TP4 (2026-09-10, temp 0, deterministic over 3 runs): the
DeepSeek-V4.1-Flash model emits
    <｜DSML｜ parameter name="key">alpha</｜DSML｜ parameter>
without the string="true" attribute. Upstream deepseekv32_detector requires the
attribute in its regexes, so the parameter is silently dropped and tool calls
parse with empty arguments ({}).

A missing attribute routes into the existing non-string branch of
_parse_parameters_from_xml (JSON attempt, raw-string fallback) — identical
handling to string="false".
"""
from pathlib import Path

TARGET = Path("/sgl-workspace/sglang/python/sglang/srt/function_call/deepseekv32_detector.py")

OLD_1 = 'rf\'<{parameter}\\s+name="([^"]+)"\\s+string="([^"]+)"\\s*>(.*?)</{parameter}>\''
NEW_1 = 'rf\'<{parameter}\\s+name="([^"]+)"(?:\\s+string="([^"]+)")?\\s*>(.*?)</{parameter}>\''
OLD_2 = 'rf\'<{parameter}\\s+name="([^"]+)"\\s+string="([^"]+)"\\s*>(.*)$\''
NEW_2 = 'rf\'<{parameter}\\s+name="([^"]+)"(?:\\s+string="([^"]+)")?\\s*>(.*)$\''

t = TARGET.read_text()
assert OLD_1 in t, "parameter_regex pattern not found"
assert OLD_2 in t, "partial_parameter_regex pattern not found"
t = t.replace(OLD_1, NEW_1).replace(OLD_2, NEW_2)
TARGET.write_text(t)
print("deepseekv32_detector.py patched: string= attribute now optional")
