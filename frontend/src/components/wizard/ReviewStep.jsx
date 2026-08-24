import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import Paper from "@mui/material/Paper";
import Divider from "@mui/material/Divider";

function formatWorkload(workload) {
  const names = {
    "sentiment-analysis": "Sentiment Analysis",
    "named-entity-recognition": "Named Entity Recognition",
  };

  return names[workload] || workload || "Not selected";
}

function StatusRow({ label, enabled }) {
  return (
    <Box
      sx={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        py: 1,
      }}
    >
      <Typography>{label}</Typography>

      <Typography
        sx={{
          fontWeight: 600,
          color: enabled ? "success.main" : "text.secondary",
        }}
      >
        {enabled ? "✓ Enabled" : "Disabled"}
      </Typography>
    </Box>
  );
}

function ReviewStep({ deploymentRequest }) {
  const cloudName =
    deploymentRequest.cloud === "azure"
      ? "Microsoft Azure"
      : deploymentRequest.cloud === "aws"
        ? "Amazon Web Services"
        : deploymentRequest.cloud || "Not selected";

  const aiService =
  deploymentRequest.cloud?.toLowerCase() === "azure"
    ? "Azure Machine Learning"
    : deploymentRequest.cloud?.toLowerCase() === "aws"
      ? "Amazon SageMaker"
      : "Not selected";

  return (
    <Box>
      {/* Page Heading */}

      <Typography
        variant="h4"
        gutterBottom
        align="center"
      >
        AI Deployment & Governance Review
      </Typography>

      <Typography
        variant="body1"
        align="center"
        color="text.secondary"
        sx={{ mb: 4 }}
      >
        Review the AI workload, model, environment and security
        configuration before deployment.
      </Typography>

      {/* AI Deployment Summary */}

      <Paper
        elevation={2}
        sx={{
          p: 3,
          borderRadius: 2,
          mb: 3,
        }}
      >
        <Typography
          variant="h5"
          gutterBottom
        >
          AI Deployment Summary
        </Typography>

        <Divider sx={{ mb: 2 }} />

        <Box
          sx={{
            display: "grid",
            gridTemplateColumns: {
              xs: "1fr",
              md: "1fr 1fr",
            },
            gap: 2,
          }}
        >
          <Box>
            <Typography
              variant="body2"
              color="text.secondary"
            >
              Cloud
            </Typography>

            <Typography variant="h6">
              {cloudName}
            </Typography>
          </Box>

          <Box>
            <Typography variant="body2" color="text.secondary">Landing Zone</Typography>
            <Typography variant="h6">{deploymentRequest.deploymentName}</Typography>
          </Box>

          <Box>
            <Typography variant="body2" color="text.secondary">Network Address Spaces</Typography>
            <Typography variant="body1">
              Hub {deploymentRequest.hubAddressSpace} • General {deploymentRequest.generalSpokeAddressSpace} • AI {deploymentRequest.aiSpokeAddressSpace}
            </Typography>
          </Box>

          <Box>
            <Typography variant="body2" color="text.secondary">AI Compute Size</Typography>
            <Typography variant="h6">{deploymentRequest.vmSize || "Not selected"}</Typography>
          </Box>

          <Box>
            <Typography
              variant="body2"
              color="text.secondary"
            >
              AI Service
            </Typography>

            <Typography variant="h6">
              {aiService}
            </Typography>
          </Box>

          <Box>
            <Typography
              variant="body2"
              color="text.secondary"
            >
              AI Workload
            </Typography>

            <Typography variant="h6">
              {formatWorkload(deploymentRequest.workload)}
            </Typography>
          </Box>

          <Box>
            <Typography
              variant="body2"
              color="text.secondary"
            >
              Environment
            </Typography>

            <Typography variant="h6">
              {deploymentRequest.environment || "Not selected"}
            </Typography>
          </Box>

          <Box
            sx={{
              gridColumn: {
                xs: "auto",
                md: "1 / -1",
              },
            }}
          >
            <Typography
              variant="body2"
              color="text.secondary"
            >
              AI Model
            </Typography>

            <Typography variant="h6">
              {deploymentRequest.modelName || "Not selected"}
            </Typography>
          </Box>
        </Box>
      </Paper>

      {/* Security & Governance */}

      <Paper
        elevation={2}
        sx={{
          p: 3,
          borderRadius: 2,
          mb: 3,
        }}
      >
        <Typography
          variant="h5"
          gutterBottom
        >
          Security & Governance Configuration
        </Typography>

        <Divider sx={{ mb: 2 }} />

        <StatusRow
          label="Identity & Access Governance"
          enabled={deploymentRequest.enableIdentityGovernance}
        />

        <Divider />

        <StatusRow
          label="Private Network Access"
          enabled={deploymentRequest.enablePrivateEndpoint}
        />

        <Divider />

        <StatusRow
          label="Public Network Exposure Disabled"
          enabled={!deploymentRequest.enablePublicIP}
        />

        <Divider />

        <StatusRow
          label="Data & Workload Protection"
          enabled={deploymentRequest.enableBackup}
        />

        <Divider />

        <StatusRow
          label="Model Governance"
          enabled={deploymentRequest.enableModelGovernance}
        />

        <Divider />

        <StatusRow
          label="AI Workload Monitoring"
          enabled={deploymentRequest.enableMonitoring}
        />
      </Paper>

      {/* Governance Readiness */}

      <Paper
        elevation={2}
        sx={{
          p: 3,
          borderRadius: 2,
          mb: 2,
        }}
      >
        <Typography
          variant="h5"
          gutterBottom
        >
          Governance Readiness
        </Typography>

        <Divider sx={{ mb: 2 }} />

        <Typography
          variant="body1"
          sx={{ mb: 2 }}
        >
          The selected AI workload will be submitted through the
          landing zone governance controls before deployment.
        </Typography>

        <Typography
          variant="body2"
          color="text.secondary"
        >
          Policy compliance is evaluated during deployment by the
          platform governance layer.
        </Typography>
      </Paper>

      {/* Deployment Target */}

      <Paper
        elevation={1}
        sx={{
          p: 3,
          borderRadius: 2,
          backgroundColor: "action.hover",
        }}
      >
        <Typography
          variant="h6"
          gutterBottom
        >
          Deployment Target
        </Typography>

        <Typography variant="body1">
          {cloudName} — {aiService}
        </Typography>

        <Typography
          variant="body2"
          color="text.secondary"
          sx={{ mt: 1 }}
        >
          The selected AI workload and model will be deployed
          through the configured AI platform environment.
        </Typography>
      </Paper>
    </Box>
  );
}

export default ReviewStep;
