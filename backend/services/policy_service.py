# ==========================================
# Multi-Cloud Governance Policy Engine
# ==========================================

from config.settings import (
    ALLOWED_CLOUDS,
    ALLOWED_ENVIRONMENTS,
    ALLOWED_REGIONS,
)

from config.governance_policies import GOVERNANCE_POLICIES


# ==========================================
# AI Workloads
# ==========================================

AI_WORKLOADS = [
    "sentiment-analysis",
    "named-entity-recognition",
]

AI_COMPUTE_SIZES = {
    "Azure": {
        "Development": {"Standard_DS2_v2", "Standard_NC4as_T4_v3"},
        "Testing": {"Standard_DS2_v2", "Standard_NC4as_T4_v3", "Standard_NC8as_T4_v3"},
        "Production": {"Standard_DS2_v2", "Standard_NC4as_T4_v3", "Standard_NC8as_T4_v3", "Standard_NC16as_T4_v3"},
    },
    "AWS": {
        "Development": {"ml.m5.xlarge", "ml.c6i.xlarge"},
        "Testing": {"ml.m5.xlarge", "ml.c6i.xlarge", "ml.g5.xlarge"},
        "Production": {"ml.m5.xlarge", "ml.c6i.xlarge", "ml.g5.xlarge", "ml.g6.xlarge"},
    },
}


# ==========================================
# Cloud Validation
# ==========================================

def validate_cloud(deployment):

    if deployment.cloud not in ALLOWED_CLOUDS:

        return {
            "allowed": False,
            "policy": "Cloud Policy",
            "reason": "Cloud provider is not allowed.",
        }

    return {"allowed": True}


# ==========================================
# Environment Validation
# ==========================================

def validate_environment(deployment):

    if deployment.environment not in ALLOWED_ENVIRONMENTS:

        return {
            "allowed": False,
            "policy": "Environment Policy",
            "reason": "Environment is not allowed.",
        }

    return {"allowed": True}


# ==========================================
# Region Validation
# ==========================================

def validate_region(deployment):

    if deployment.region not in ALLOWED_REGIONS.get(
        deployment.cloud,
        [],
    ):

        return {
            "allowed": False,
            "policy": "Region Policy",
            "reason": (
                f"{deployment.region} is not an approved "
                f"region for {deployment.cloud}."
            ),
        }

    return {"allowed": True}


# ==========================================
# AI Workload Validation
# ==========================================

def validate_ai_workload(deployment):

    if deployment.workload not in AI_WORKLOADS:

        return {
            "allowed": False,
            "policy": "AI Workload Policy",
            "reason": (
                f"{deployment.workload} is not an approved "
                "AI workload."
            ),
        }

    return {"allowed": True}


# ==========================================
# AI Model Validation
# ==========================================

def validate_ai_model(deployment):

    if not deployment.modelId:

        return {
            "allowed": False,
            "policy": "AI Model Policy",
            "reason": "A validated AI model must be selected.",
        }

    if not deployment.modelName:

        return {
            "allowed": False,
            "policy": "AI Model Policy",
            "reason": "AI model name is required.",
        }

    return {"allowed": True}


def validate_ai_compute_size(deployment):
    allowed = (
        AI_COMPUTE_SIZES
        .get(deployment.cloud, {})
        .get(deployment.environment, set())
    )
    if deployment.vmSize not in allowed:
        return {
            "allowed": False,
            "policy": "AI Compute Size Policy",
            "reason": (
                f"{deployment.vmSize or 'No compute size'} is not approved for "
                f"{deployment.cloud} {deployment.environment}. Approved sizes: "
                f"{', '.join(sorted(allowed)) or 'none configured'}."
            ),
        }
    return {"allowed": True}


# ==========================================
# Identity & Access Governance
# ==========================================

def validate_identity_governance(deployment):

    policy = get_ai_governance_policy(
        deployment.cloud,
        deployment.environment,
        "identity_governance",
    )

    required = policy["required"]

    if required and not deployment.enableIdentityGovernance:

        return {
            "allowed": False,
            "policy": policy["name"],
            "reason": (
                "Identity and access governance is mandatory "
                "for this environment."
            ),
        }

    return {"allowed": True}


# ==========================================
# AI Model Governance
# ==========================================

def validate_model_governance(deployment):

    policy = get_ai_governance_policy(
        deployment.cloud,
        deployment.environment,
        "model_governance",
    )

    required = policy["required"]

    if required and not deployment.enableModelGovernance:

        return {
            "allowed": False,
            "policy": policy["name"],
            "reason": (
                "AI model governance is mandatory "
                "for this environment."
            ),
        }

    return {"allowed": True}


# ==========================================
# AI Data & Workload Protection
# ==========================================

def validate_ai_data_protection(deployment):

    policy = get_ai_governance_policy(
        deployment.cloud,
        deployment.environment,
        "data_protection",
    )

    required = policy["required"]

    if required and not deployment.enableBackup:

        return {
            "allowed": False,
            "policy": policy["name"],
            "reason": (
                "AI data and workload protection must be "
                "enabled for this environment."
            ),
        }

    # Optional means both ON and OFF are acceptable.

    return {"allowed": True}


# ==========================================
# AI Workload Monitoring
# ==========================================

def validate_ai_monitoring(deployment):

    policy = get_ai_governance_policy(
        deployment.cloud,
        deployment.environment,
        "monitoring",
    )

    required = policy["required"]

    if required and not deployment.enableMonitoring:

        return {
            "allowed": False,
            "policy": policy["name"],
            "reason": (
                "AI workload monitoring must be enabled "
                "for this environment."
            ),
        }

    return {"allowed": True}


# ==========================================
# AI Network Isolation
# ==========================================

def validate_ai_network(deployment):

    private_policy = get_ai_governance_policy(
        deployment.cloud,
        deployment.environment,
        "private_endpoint",
    )

    public_policy = get_ai_governance_policy(
        deployment.cloud,
        deployment.environment,
        "public_ip",
    )

    # ------------------------------------------
    # Private Endpoint
    # ------------------------------------------

    if (
        private_policy["required"]
        and not deployment.enablePrivateEndpoint
    ):

        return {
            "allowed": False,
            "policy": private_policy["name"],
            "reason": (
                "Private network access is mandatory "
                "for this environment."
            ),
        }

    # ------------------------------------------
    # Public Network Exposure
    # ------------------------------------------

    if (
        not public_policy["allowed"]
        and deployment.enablePublicIP
    ):

        return {
            "allowed": False,
            "policy": public_policy["name"],
            "reason": (
                "Public network exposure is not allowed "
                "for this environment."
            ),
        }

    return {"allowed": True}


# ==========================================
# Availability Zone Validation
# ==========================================

def validate_availability_zone(deployment):

    policy = get_ai_governance_policy(
        deployment.cloud,
        deployment.environment,
        "availability_zone",
    )

    required = policy["required"]

    if required and not deployment.enableAvailabilityZone:

        return {
            "allowed": False,
            "policy": policy["name"],
            "reason": (
                "Availability Zone deployment is required "
                "for this environment."
            ),
        }

    return {"allowed": True}


# ==========================================
# Existing IaaS Workload Validation
# ==========================================

def validate_workload(deployment):

    if deployment.workload not in ["General", "AI"]:

        return {
            "allowed": False,
            "policy": "Workload Policy",
            "reason": "Workload type is not allowed.",
        }

    return {"allowed": True}


# ==========================================
# VM Size Validation
# ==========================================

def validate_vm_size(deployment):

    policy = get_environment_policy(
        deployment.cloud,
        deployment.environment,
    )

    if not policy:

        return {
            "allowed": False,
            "policy": "Environment Governance Policy",
            "reason": (
                "No governance policy exists for the selected "
                "cloud and environment."
            ),
        }

    allowed_vm_sizes = policy["vm_size"]["allowed"]

    if deployment.vmSize not in allowed_vm_sizes:

        return {
            "allowed": False,
            "policy": policy["vm_size"]["name"],
            "reason": (
                f"{deployment.vmSize} is not allowed "
                f"in {deployment.environment}."
            ),
        }

    return {"allowed": True}


# ==========================================
# Storage Validation
# ==========================================

def validate_storage(deployment):

    policy = get_environment_policy(
        deployment.cloud,
        deployment.environment,
    )

    if not policy:

        return {
            "allowed": False,
            "policy": "Environment Governance Policy",
            "reason": (
                "No governance policy exists for the selected "
                "cloud and environment."
            ),
        }

    allowed_storage = policy["storage"]["allowed"]

    if deployment.storageType not in allowed_storage:

        return {
            "allowed": False,
            "policy": policy["storage"]["name"],
            "reason": (
                f"{deployment.storageType} is not allowed "
                f"in {deployment.environment}."
            ),
        }

    return {"allowed": True}


# ==========================================
# Backup Validation
# ==========================================

def validate_backup(deployment):

    policy = get_environment_policy(
        deployment.cloud,
        deployment.environment,
    )

    if not policy:

        return {
            "allowed": False,
            "policy": "Environment Governance Policy",
            "reason": (
                "No governance policy exists for the selected "
                "cloud and environment."
            ),
        }

    required = policy["backup"]["required"]

    if required and not deployment.enableBackup:

        return {
            "allowed": False,
            "policy": policy["backup"]["name"],
            "reason": "Backup must be enabled.",
        }

    # If backup is optional, both ON and OFF are valid.

    return {"allowed": True}


# ==========================================
# Monitoring Validation
# ==========================================

def validate_monitoring(deployment):

    policy = get_environment_policy(
        deployment.cloud,
        deployment.environment,
    )

    if not policy:

        return {
            "allowed": False,
            "policy": "Environment Governance Policy",
            "reason": (
                "No governance policy exists for the selected "
                "cloud and environment."
            ),
        }

    required = policy["monitoring"]["required"]

    if required and not deployment.enableMonitoring:

        return {
            "allowed": False,
            "policy": policy["monitoring"]["name"],
            "reason": "Monitoring must be enabled.",
        }

    return {"allowed": True}


# ==========================================
# Private Endpoint Validation
# ==========================================

def validate_private_endpoint(deployment):

    policy = get_environment_policy(
        deployment.cloud,
        deployment.environment,
    )

    if not policy:

        return {
            "allowed": False,
            "policy": "Environment Governance Policy",
            "reason": (
                "No governance policy exists for the selected "
                "cloud and environment."
            ),
        }

    required = policy["private_endpoint"]["required"]

    if required and not deployment.enablePrivateEndpoint:

        return {
            "allowed": False,
            "policy": policy["private_endpoint"]["name"],
            "reason": "Private Endpoint is mandatory.",
        }

    return {"allowed": True}


# ==========================================
# Public IP Validation
# ==========================================

def validate_public_ip(deployment):

    policy = get_environment_policy(
        deployment.cloud,
        deployment.environment,
    )

    if not policy:

        return {
            "allowed": False,
            "policy": "Environment Governance Policy",
            "reason": (
                "No governance policy exists for the selected "
                "cloud and environment."
            ),
        }

    allowed = policy["public_ip"]["allowed"]

    if not allowed and deployment.enablePublicIP:

        return {
            "allowed": False,
            "policy": policy["public_ip"]["name"],
            "reason": "Public IP is not allowed.",
        }

    return {"allowed": True}


# ==========================================
# Load Environment Policy
# ==========================================

def get_environment_policy(cloud, environment):

    return (
        GOVERNANCE_POLICIES
        .get(cloud, {})
        .get(environment)
    )


# ==========================================
# Load AI Governance Policy
# ==========================================

def get_ai_governance_policy(
    cloud,
    environment,
    control,
):

    environment_policy = get_environment_policy(
        cloud,
        environment,
    )

    if not environment_policy:

        return {
            "id": "UNKNOWN",
            "name": "AI Governance Policy",
            "required": True,
        }

    ai_policy = environment_policy.get(
        "ai_governance",
        {},
    )

    return ai_policy.get(
        control,
        {
            "id": "UNKNOWN",
            "name": "AI Governance Policy",
            "required": True,
        },
    )


# ==========================================
# Main Governance Validation
# ==========================================

def validate_policy(deployment):

    # --------------------------------------
    # AI Deployment Governance
    # --------------------------------------

    if deployment.workload in AI_WORKLOADS:

        validations = [

            validate_cloud,

            validate_environment,

            # Region validation must apply to AI
            # deployments as well.
            validate_region,

            validate_ai_workload,

            validate_ai_model,

            validate_ai_compute_size,

            validate_identity_governance,

            validate_model_governance,

            validate_ai_network,

            validate_ai_data_protection,

            validate_ai_monitoring,

            validate_availability_zone,
        ]

    # --------------------------------------
    # Existing IaaS Governance
    # --------------------------------------

    else:

        validations = [

            validate_cloud,

            validate_environment,

            validate_region,

            validate_workload,

            validate_vm_size,

            validate_storage,

            validate_backup,

            validate_monitoring,

            validate_private_endpoint,

            validate_public_ip,

        ]

    # --------------------------------------
    # Execute all policies
    # --------------------------------------

    results = []

    passed = 0

    failed = 0

    for validation in validations:

        result = validation(deployment)

        if result["allowed"]:

            results.append({

                "status": "PASS",

                "policy": (
                    validation.__name__
                    .replace("validate_", "")
                    .replace("_", " ")
                    .title()
                ),

            })

            passed += 1

        else:

            results.append({

                "status": "FAIL",

                "policy": result["policy"],

                "reason": result["reason"],

            })

            failed += 1

    # --------------------------------------
    # Compliance Score
    # --------------------------------------

    compliance_score = round(
        (passed / len(validations)) * 100
    )

    # --------------------------------------
    # Final Governance Decision
    # --------------------------------------

    return {

        "allowed": failed == 0,

        "passed": passed,

        "failed": failed,

        "compliance_score": compliance_score,

        "results": results,

    }
