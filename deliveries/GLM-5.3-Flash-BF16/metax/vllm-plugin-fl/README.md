# GLM-5.3-Flash-BF16 / MetaX / vllm-plugin-fl

Small, sanitized restoration material copied byte-for-byte from the clean image.
The local image is unpublished. Both hosts passed file/import/device checks;
fresh-image model startup and generation are still pending. Check
`delivery-state.json` and the final acceptance records before deployment.

`start-model.sh`, `runtime-config.json`, `source-reference.json`,
`dependency-lock.json` and `restore.md` are the five restoration roles. Complete
patches pin the three public component baselines without requiring publication.
No weights, evaluation data or logs are included here.

Use the image-internal launcher at
`/opt/glm5.3-flash-delivery-v14/start-model.sh`. Normal startup keeps prefix
caching enabled; only its explicit `--performance` branch disables it. The
launcher is scoped to the verified mx-101/mx-102 topology. Required weights
remain an external read-only mount. See `restore.md` for restoration steps.

See the [adaptation workspace](../../../../models/GLM-5.3-Flash-BF16/metax/frameworks/vllm-plugin-fl/README.md)
and [image packaging record](../../../../models/GLM-5.3-Flash-BF16/metax/frameworks/vllm-plugin-fl/adaptation/017-image-packaging-storage.md).
