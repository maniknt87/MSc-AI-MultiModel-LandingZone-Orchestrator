import { useEffect, useState } from "react";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Paper from "@mui/material/Paper";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Typography from "@mui/material/Typography";
import AutoAwesomeRoundedIcon from "@mui/icons-material/AutoAwesomeRounded";
import CheckCircleRoundedIcon from "@mui/icons-material/CheckCircleRounded";
import CloudQueueRoundedIcon from "@mui/icons-material/CloudQueueRounded";
import GppGoodRoundedIcon from "@mui/icons-material/GppGoodRounded";
import HubRoundedIcon from "@mui/icons-material/HubRounded";
import PublicRoundedIcon from "@mui/icons-material/PublicRounded";
import SettingsSuggestRoundedIcon from "@mui/icons-material/SettingsSuggestRounded";
import { aiWorkloads } from "../constants/aiWorkloads";
import { getGovernanceSettings } from "../services/api";
import { approvedComputeSizes } from "../constants/computeSizes";

const governancePolicies = [
  { id: "IAM-01", domain: "Identity", control: "Least-privilege RBAC and managed identity", enforcement: "API gate", development: "Required", testing: "Required", production: "Mandatory" },
  { id: "IAM-02", domain: "Identity", control: "Privileged access review and separation of duties", enforcement: "Roadmap", development: "Recommended", testing: "Required", production: "Mandatory" },
  { id: "NET-01", domain: "Network", control: "Private endpoints for AI platform services", enforcement: "Terraform", development: "Optional", testing: "Required", production: "Mandatory" },
  { id: "NET-02", domain: "Network", control: "Public network exposure", enforcement: "API gate", development: "Allowed", testing: "Restricted", production: "Disabled" },
  { id: "DAT-01", domain: "Data", control: "Encryption at rest and in transit", enforcement: "Terraform", development: "Required", testing: "Required", production: "Mandatory" },
  { id: "DAT-02", domain: "Data", control: "Data classification and workload protection", enforcement: "API gate", development: "Recommended", testing: "Required", production: "Mandatory" },
  { id: "AI-01", domain: "Responsible AI", control: "Approved model registry and version traceability", enforcement: "API gate", development: "Recommended", testing: "Required", production: "Mandatory" },
  { id: "AI-02", domain: "Responsible AI", control: "Safety, quality and bias evaluation evidence", enforcement: "Roadmap", development: "Recommended", testing: "Required", production: "Mandatory" },
  { id: "SEC-01", domain: "Security", control: "Security posture and vulnerability assessment", enforcement: "Roadmap", development: "Recommended", testing: "Required", production: "Mandatory" },
  { id: "OPS-01", domain: "Operations", control: "Centralized logging, metrics and alerting", enforcement: "Terraform", development: "Recommended", testing: "Required", production: "Mandatory" },
  { id: "OPS-02", domain: "Operations", control: "Immutable audit trail and deployment evidence", enforcement: "Pipeline", development: "Required", testing: "Required", production: "Mandatory" },
  { id: "BCM-01", domain: "Resilience", control: "Backup, recovery and retention policy", enforcement: "Terraform", development: "Optional", testing: "Required", production: "Mandatory" },
  { id: "BCM-02", domain: "Resilience", control: "Zone-redundant deployment", enforcement: "Terraform", development: "Optional", testing: "Recommended", production: "Required" },
  { id: "FIN-01", domain: "FinOps", control: "Mandatory tags, budgets and cost ownership", enforcement: "Terraform", development: "Required", testing: "Required", production: "Mandatory" },
  { id: "FIN-02", domain: "FinOps", control: "Environment-scoped AI compute size allowlist", enforcement: "API gate", development: "Required", testing: "Required", production: "Required" },
];

const chipStyles = {
  Mandatory: { color: "#b42318", bgcolor: "#fef3f2", borderColor: "#fecdca" },
  Disabled: { color: "#b42318", bgcolor: "#fef3f2", borderColor: "#fecdca" },
  Required: { color: "#175cd3", bgcolor: "#eff8ff", borderColor: "#b2ddff" },
  Recommended: { color: "#027a48", bgcolor: "#ecfdf3", borderColor: "#abefc6" },
  Allowed: { color: "#027a48", bgcolor: "#ecfdf3", borderColor: "#abefc6" },
  Restricted: { color: "#b54708", bgcolor: "#fffaeb", borderColor: "#fedf89" },
  Optional: { color: "#475467", bgcolor: "#f9fafb", borderColor: "#d0d5dd" },
};

function PolicyChip({ value }) {
  return <Chip label={value} size="small" variant="outlined" sx={{ minWidth: 92, fontWeight: 600, ...chipStyles[value] }} />;
}

function MetricCard({ icon: Icon, label, value, accent, details }) {
  return (
    <Paper elevation={0} sx={{ p: 2.5, border: "1px solid", borderColor: "divider", display: "flex", alignItems: "center", gap: 2 }}>
      <Box sx={{ width: 44, height: 44, borderRadius: 2.5, display: "grid", placeItems: "center", color: accent, bgcolor: `${accent}12` }}><Icon /></Box>
      <Box sx={{ minWidth: 0, flex: 1 }}>
        <Box sx={{ display: "flex", alignItems: "baseline", gap: 1 }}><Typography variant="h5" sx={{ lineHeight: 1 }}>{value}</Typography><Typography variant="body2" color="text.secondary">{label}</Typography></Box>
        {details && <Box sx={{ display: "flex", gap: .75, flexWrap: "wrap", mt: 1 }}>{details}</Box>}
      </Box>
    </Paper>
  );
}

function SectionCard({ icon: Icon, title, subtitle, children }) {
  return (
    <Paper elevation={0} sx={{ border: "1px solid", borderColor: "divider", height: "100%", overflow: "hidden" }}>
      <Box sx={{ p: 2.5, display: "flex", gap: 1.5, alignItems: "center", borderBottom: "1px solid", borderColor: "divider", bgcolor: "#fbfcfe" }}>
        <Box sx={{ width: 38, height: 38, display: "grid", placeItems: "center", borderRadius: 2, color: "primary.main", bgcolor: "primary.light" }}><Icon fontSize="small" /></Box>
        <Box><Typography variant="h6" fontSize={17}>{title}</Typography>{subtitle && <Typography variant="caption" color="text.secondary">{subtitle}</Typography>}</Box>
      </Box>
      <Box sx={{ p: 2.5 }}>{children}</Box>
    </Paper>
  );
}

function GovernanceCenter() {
  const [settings, setSettings] = useState({ clouds: [], environments: [], workloads: [], regions: {}, compute_sizes: approvedComputeSizes });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let active = true;
    getGovernanceSettings().then((response) => active && setSettings(response)).catch(() => active && setError(true)).finally(() => active && setLoading(false));
    return () => { active = false; };
  }, []);

  const regionCount = Object.values(settings.regions).reduce((total, regions) => total + regions.length, 0);

  if (loading) return <Box sx={{ minHeight: 420, display: "grid", placeItems: "center" }}><CircularProgress /></Box>;

  return (
    <Box>
      <Box sx={{ display: "flex", alignItems: { xs: "flex-start", sm: "center" }, justifyContent: "space-between", gap: 2, flexDirection: { xs: "column", sm: "row" }, mb: 3.5 }}>
        <Box><Typography variant="overline" color="primary.main" fontWeight={700} letterSpacing=".12em">Policy management</Typography><Typography variant="h4" sx={{ mt: .25 }}>Governance center</Typography><Typography color="text.secondary" sx={{ mt: .8 }}>Approved services, regional boundaries and environment-specific controls in one view.</Typography></Box>
        <Chip icon={<CheckCircleRoundedIcon />} label="Policy engine active" color="success" variant="outlined" sx={{ bgcolor: "#ecfdf3", borderColor: "#abefc6", fontWeight: 600 }} />
      </Box>

      {error && <Alert severity="warning" sx={{ mb: 3 }}>Live governance settings are unavailable. The baseline matrix remains visible.</Alert>}

      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr", xl: "repeat(4,1fr)" }, gap: 2, mb: 3 }}>
        <MetricCard
          icon={CloudQueueRoundedIcon}
          label="Approved clouds"
          value={settings.clouds.length}
          accent="#2563eb"
          details={settings.clouds.map((cloud) => (
            <Chip key={cloud} label={cloud} size="small" variant="outlined" sx={{ height: 22, color: "#175cd3", bgcolor: "#eff8ff", borderColor: "#b2ddff", fontWeight: 600 }} />
          ))}
        />
        <MetricCard
          icon={HubRoundedIcon}
          label="AI workloads"
          value={aiWorkloads.length}
          accent="#7c3aed"
          details={aiWorkloads.map((workload) => (
            <Chip key={workload.id} label={workload.name} size="small" variant="outlined" sx={{ height: 22, color: "#6941c6", bgcolor: "#f9f5ff", borderColor: "#d6bbfb", fontWeight: 600 }} />
          ))}
        />
        <MetricCard
          icon={SettingsSuggestRoundedIcon}
          label="Environments"
          value={settings.environments.length}
          accent="#0891b2"
          details={settings.environments.map((environment) => (
            <Chip key={environment} label={environment} size="small" variant="outlined" sx={{ height: 22, color: "#0e7090", bgcolor: "#ecfdff", borderColor: "#a5f0fc", fontWeight: 600 }} />
          ))}
        />
        <MetricCard icon={PublicRoundedIcon} label="Approved regions" value={regionCount} accent="#039855" />
      </Box>

      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", lg: "1.25fr .75fr" }, gap: 2, mb: 3 }}>
        <SectionCard icon={AutoAwesomeRoundedIcon} title="Approved AI workloads" subtitle="Validated workload catalogue">
          <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "repeat(3,1fr)" }, gap: 1.5 }}>
            {aiWorkloads.map((workload) => <Box key={workload.id} sx={{ p: 2, border: "1px solid", borderColor: "divider", borderRadius: 2, bgcolor: "#fff" }}><Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1 }}><CheckCircleRoundedIcon sx={{ fontSize: 18, color: "success.main" }} /><Typography fontWeight={600} fontSize={14}>{workload.name}</Typography></Box><Typography variant="caption" color="text.secondary" sx={{ lineHeight: 1.55 }}>{workload.description}</Typography></Box>)}
          </Box>
        </SectionCard>
        <SectionCard icon={PublicRoundedIcon} title="Regional boundaries" subtitle="Permitted deployment locations">
          <Box sx={{ display: "grid", gap: 2 }}>{Object.entries(settings.regions).map(([cloud, regions]) => <Box key={cloud}><Box sx={{ display: "flex", justifyContent: "space-between", mb: 1 }}><Typography fontWeight={600} fontSize={14}>{cloud}</Typography><Chip label={`${regions.length} regions`} size="small" /></Box><Box sx={{ display: "flex", flexWrap: "wrap", gap: .75 }}>{regions.map((region) => <Chip key={region} label={region} size="small" variant="outlined" sx={{ bgcolor: "#fff" }} />)}</Box></Box>)}</Box>
        </SectionCard>
      </Box>

      <Paper elevation={0} sx={{ border: "1px solid", borderColor: "divider", overflow: "hidden", mb: 3 }}>
        <Box sx={{ p: 3, borderBottom: "1px solid", borderColor: "divider" }}><Typography variant="h6">Approved AI compute sizes</Typography><Typography variant="body2" color="text.secondary" sx={{ mt: .5 }}>Cost-conscious guardrails restrict Development, while Production permits the broadest approved capacity range.</Typography></Box>
        <TableContainer>
          <Table sx={{ minWidth: 900 }}>
            <TableHead><TableRow sx={{ bgcolor: "#f8fafc" }}><TableCell sx={{ fontWeight: 700 }}>Cloud</TableCell><TableCell sx={{ fontWeight: 700 }}>Development</TableCell><TableCell sx={{ fontWeight: 700 }}>Testing</TableCell><TableCell sx={{ fontWeight: 700 }}>Production</TableCell></TableRow></TableHead>
            <TableBody>{Object.entries(settings.compute_sizes || approvedComputeSizes).map(([cloud, environments]) => <TableRow key={cloud}><TableCell><Typography fontWeight={700}>{cloud}</Typography><Typography variant="caption" color="text.secondary">{cloud === "Azure" ? "Azure ML compute" : "SageMaker inference"}</Typography></TableCell>{["Development", "Testing", "Production"].map((environment) => <TableCell key={environment}><Box sx={{ display: "flex", flexWrap: "wrap", gap: .75 }}>{environments[environment].map((size) => <Chip key={size} label={size} size="small" variant="outlined" sx={{ fontFamily: "monospace", bgcolor: "#fff" }} />)}</Box></TableCell>)}</TableRow>)}</TableBody>
          </Table>
        </TableContainer>
      </Paper>

      <Paper elevation={0} sx={{ border: "1px solid", borderColor: "divider", overflow: "hidden", mb: 3 }}>
        <Box sx={{ p: 3, display: "flex", justifyContent: "space-between", gap: 2, alignItems: { xs: "flex-start", lg: "center" }, flexDirection: { xs: "column", lg: "row" }, borderBottom: "1px solid", borderColor: "divider" }}><Box><Typography variant="h6">Enterprise governance control baseline</Typography><Typography variant="body2" color="text.secondary" sx={{ mt: .5 }}>Control catalogue aligned to Zero Trust, cloud adoption and responsible AI operating principles.</Typography></Box><Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}><Chip label={`${governancePolicies.length} controls`} color="primary" size="small" /><Chip label="8 control domains" size="small" variant="outlined" /><Chip label="Environment scoped" size="small" variant="outlined" /></Box></Box>
        <Box sx={{ px: 3, py: 1.5, display: "flex", alignItems: "center", gap: 1, flexWrap: "wrap", bgcolor: "#fbfcfe", borderBottom: "1px solid", borderColor: "divider" }}><Typography variant="caption" color="text.secondary" fontWeight={600} sx={{ mr: .5 }}>POLICY LEVELS</Typography>{["Mandatory", "Required", "Recommended", "Optional"].map((level) => <PolicyChip key={level} value={level} />)}<Typography variant="caption" color="text.secondary" sx={{ ml: { sm: "auto" } }}>Enforcement ownership is shown per control.</Typography></Box>
        <TableContainer>
          <Table sx={{ minWidth: 1060 }}>
            <TableHead><TableRow sx={{ bgcolor: "#f8fafc" }}><TableCell sx={{ width: "38%", fontWeight: 700 }}>Control</TableCell><TableCell sx={{ width: 120, fontWeight: 700 }}>Enforcement</TableCell><TableCell align="center" sx={{ fontWeight: 700 }}>Development</TableCell><TableCell align="center" sx={{ fontWeight: 700 }}>Testing</TableCell><TableCell align="center" sx={{ fontWeight: 700 }}>Production</TableCell></TableRow></TableHead>
            <TableBody>{governancePolicies.map((policy) => <TableRow key={policy.id} hover><TableCell><Box sx={{ display: "flex", gap: 1.5, alignItems: "flex-start" }}><Chip label={policy.id} size="small" sx={{ height: 22, minWidth: 62, fontFamily: "monospace", fontWeight: 700, color: "#344054", bgcolor: "#f2f4f7" }} /><Box><Typography variant="body2" fontWeight={600}>{policy.control}</Typography><Typography variant="caption" color="text.secondary">{policy.domain}</Typography></Box></Box></TableCell><TableCell><Chip label={policy.enforcement} size="small" variant="outlined" sx={{ height: 24, fontSize: 11, fontWeight: 600, color: policy.enforcement === "Roadmap" ? "#b54708" : "#475467", bgcolor: policy.enforcement === "Roadmap" ? "#fffaeb" : "#fff", borderColor: policy.enforcement === "Roadmap" ? "#fedf89" : "#d0d5dd" }} /></TableCell><TableCell align="center"><PolicyChip value={policy.development} /></TableCell><TableCell align="center"><PolicyChip value={policy.testing} /></TableCell><TableCell align="center"><PolicyChip value={policy.production} /></TableCell></TableRow>)}</TableBody>
          </Table>
        </TableContainer>
      </Paper>

      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" }, gap: 2 }}>
        <SectionCard icon={GppGoodRoundedIcon} title="Policy enforcement engine"><Box sx={{ display: "flex", gap: 1, mb: 1.5 }}><Chip label="Connected" color="success" size="small" /><Chip label="Pre-deployment gate" size="small" variant="outlined" /></Box><Typography variant="body2" color="text.secondary" lineHeight={1.7}>Every request is evaluated before pipeline execution. A failed mandatory control stops the deployment and returns an actionable compliance report.</Typography></SectionCard>
        <SectionCard icon={SettingsSuggestRoundedIcon} title="Policy-as-code roadmap"><Box sx={{ display: "flex", gap: 1, mb: 1.5 }}><Chip label="Planned" color="warning" size="small" /><Chip label="OPA integration" size="small" variant="outlined" /></Box><Typography variant="body2" color="text.secondary" lineHeight={1.7}>Open Policy Agent can extend the existing governance engine with versioned, testable policy bundles while keeping the same customer deployment experience.</Typography></SectionCard>
      </Box>
    </Box>
  );
}

export default GovernanceCenter;
