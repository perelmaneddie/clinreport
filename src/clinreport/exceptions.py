class ClinReportError(Exception):
    """Base exception for clinreport."""


class ExternalToolError(ClinReportError):
    """Raised when an external tool (bcftools/igv/fastp) fails."""


class InputValidationError(ClinReportError):
    """Raised when inputs are missing or inconsistent."""
