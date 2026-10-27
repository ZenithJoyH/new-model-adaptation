# {{MODEL_NAME}} on {{PLATFORM}} — {{FRAMEWORK}} Deployment Guide

> Documentation status: {{READY_OR_DRAFT_AND_LIMITATIONS}}
> Adaptation scope: {{MODEL_WEIGHT_ID_PLATFORM_FRAMEWORK_AND_HOST_SCOPE}}
> Evidence date: {{DATE}}. Image packaging / fresh-container validation: {{STATUS}}.

# Introduction

## Integrated Deployment

{{VERIFIED_SUPPORTED_CAPABILITIES_IMAGE_AND_TESTED_LAUNCHER}}

## Validation Scope

{{ACTUAL_ACCEPTANCE_SCOPE_EXECUTION_MODE_AND_UNTESTED_LIMITATIONS}}

# Evaluation Results

## Accuracy

| Dataset / split | Metric | Minimum threshold | Observed result | Samples | Status |
| --- | --- | --- | --- | --- | --- |
| {{DATASET}} | {{METRIC}} | {{THRESHOLD}} | {{RESULT}} | {{SAMPLE_COUNT}} | {{STATUS}} |

{{EVALUATOR_VERSION_CONFIGURATION_DATE_AND_EVIDENCE_REFERENCE}}
Prefix caching during service accuracy evaluation: enabled where supported.

## Performance

| Workload / input-output lengths | Concurrency | Metric | Value and unit | Baseline, if measured |
| --- | --- | --- | --- | --- |
| {{WORKLOAD}} | {{CONCURRENCY}} | {{METRIC}} | {{VALUE_AND_UNIT}} | {{BASELINE_OR_NOT_MEASURED}} |

{{GRAPH_MODE_TOPOLOGY_PRECISION_MEASUREMENT_CONDITIONS_AND_EVIDENCE_REFERENCE}}
Prefix caching during service performance evaluation: disabled where supported.
{{COMPARABILITY_LIMITATIONS_AND_UNMEASURED_ITEMS}}

# User Guide

## Environment Setup

| Item | Verified configuration / version |
| --- | --- |
| Hardware and device count | {{HARDWARE}} |
| Operating system | {{OS}} |
| Container runtime | {{CONTAINER_RUNTIME}} |
| Driver / accelerator runtime | {{DRIVER_RUNTIME}} |
| Python / PyTorch / inference framework | {{FRAMEWORK_VERSIONS}} |
| Used FlagOS components | {{COMPONENT_VERSIONS_OR_REVISIONS}} |
| Model weights / tokenizer / precision | {{WEIGHT_AND_TOKENIZER_IDENTITY}} |
| Required resources and topology | {{RESOURCE_REQUIREMENTS}} |

## Operation Steps

The commands below are user instructions. Document generation does not execute
downloads, installation, container startup, service startup or evaluation.

### Download FlagOS Image

Image identity and availability: {{IMAGE_REFERENCE_DIGEST_AND_RELEASE_STATUS}}

```bash
{{VERIFIED_IMAGE_PULL_COMMAND}}
```

### Download Open-source Model Weights

Source, revision, access conditions and license reference: {{VERIFIED_WEIGHT_SOURCE}}
Checkpoint/quantization required by this deployment: {{EXACT_CHECKPOINT}}

```bash
{{VERIFIED_WEIGHT_DOWNLOAD_INSTRUCTIONS_FOR_THE_READER_ONLY}}
```

{{HOST_WEIGHT_LOCATION_AND_CONTAINER_MOUNT_CONTRACT}}

### Start the Container

{{REQUIRED_DEVICES_MOUNTS_NETWORK_AND_PLATFORM_SPECIFIC_PREREQUISITES}}

```bash
{{VERIFIED_CONTAINER_LAUNCH_COMMAND}}
```

### Start the Server

Use the tested launcher included at the documented container-internal path.
Launcher SHA-256: {{LAUNCHER_SHA256}}.

```bash
{{VERIFIED_DEFAULT_LAUNCHER_INVOCATION}}
```

Normal and accuracy startup keep prefix caching enabled. For a separately
authorized performance run, use the same script with `--performance`, then return
to its default invocation before further non-performance work. This switch does
not run an evaluation or stop an existing service automatically.

{{VERIFIED_PERFORMANCE_INVOCATION_OR_PROFILE_NOT_APPLICABLE}}
{{IMAGE_INTERNAL_FILES_EXTERNAL_INPUTS_AND_PACKAGING_LIMITATIONS}}

## Service Invocation

Endpoint, served model name and supported request types: {{VERIFIED_API_CONTRACT}}
Example verification status: {{VERIFIED_OR_NOT_TESTED}}

```bash
{{MATCHING_CURL_OR_PROFILE_API_EXAMPLE_WITHOUT_CREDENTIALS}}
```

# Technical Overview

{{ONLY_USED_COMPONENTS_AND_THEIR_VERIFIED_ROLES}}

# Known Limitations

{{UNSUPPORTED_FEATURES_PENDING_CHECKS_AND_SCOPE_LIMITS}}

# Evidence References

{{CONCISE_ENVIRONMENT_ACCEPTANCE_LAUNCHER_AND_RESULT_REFERENCES}}

# Contributing

{{VERIFIED_PROJECT_SUPPORT_OR_CONTRIBUTION_CHANNELS_OR_OMIT_SECTION}}

# License

{{VERIFIED_MODEL_WEIGHT_AND_SOFTWARE_LICENSES_WITH_SOURCES_OR_PENDING_VERIFICATION}}
