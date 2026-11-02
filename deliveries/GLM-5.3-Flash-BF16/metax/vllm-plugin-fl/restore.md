# Restore the GLM-5.3-Flash MetaX text deployment

Scope: mx-101 and mx-102, each with eight C550 64 GiB devices, host driver
3.8.1 and the tested in-image MACA3.8.2/PyTorch2.10 environment. Use the
adapted image digest from the external image-validation receipt. The intended
local tag is `local/glm5.3-flash:adapted-v14-20261028`; packaging and fresh
container verification must be checked in that receipt, not inferred here.

Required external input: mount the existing BF16 checkpoint directory read-only
at `/public-flash/models/GLM-5.3-Flash-BF16`, including its tokenizer and chat
template. See runtime-config.json for the exact metadata hashes. No weights are
included in this image. An optional read/write mount of the approved task
`04-runs` directory stores logs; it supplies no code or runtime configuration.

Use host networking, the tested MetaX device/privileged and host-IPC settings,
and access to all eight local devices. The accepted launcher is embedded at
`/opt/glm5.3-flash-delivery-v14/start-model.sh`. Start its no-argument invocation
on mx-102 first, then mx-101. It uses the verified inbond1 addresses and ports
29653/18530, TP8/PP2,65536 context and FULL_AND_PIECEWISE. This exact launcher
is scoped to those hosts; a changed topology requires revalidation. Keep the
container running independently of the inference process for task operations.

The no-argument launch enables prefix caching. Only its explicit --performance
branch disables caching; use identical bytes and base settings for evaluation,
and restore normal startup afterwards. Readiness is external to the launcher.
Do not run it alongside a conflicting task service or kill unrelated processes.

Installed components remain at /opt/vllm-plugin-FL, /opt/FlagGems and
/opt/FlagGems-vllm, with the read-only vLLM installation at /opt/vllm. No
PYTHONPATH override or host development checkout is required. Use the image
for binary dependency reproduction; dependency-lock.json records the exact
tested versions and the remaining FlagTree provenance limitation.

source-reference.json locks public base SHAs and the complete corresponding
patches under patches/. These adaptations are unpublished; the user explicitly
authorized this frozen-patch/image delivery instead of public publication.
Patch restoration is only for a fresh clean copy of each named public base,
after git apply --check succeeds. Do not reset or overwrite a user's dirty
installation. Reverse-apply checks on the actual installed task tree are
recorded separately; no second product checkout was created for packaging.

Image/video correctness, MTP, RDMA and other hardware are not validated.
Formal GPQA and performance outcomes are external acceptance evidence; this
restore file alone claims neither an accuracy pass nor business optimization.
