from app.models.medical import IncapacitationSeverity

class FHIRIntegrationService:

    @staticmethod
    def parse_fhir_condition(fhir_bundle: dict) -> dict:
        """Parses HL7/FHIR Condition and Observation resources for incapacitation indicators."""
        icd10_codes = []
        severity = IncapacitationSeverity.NONE
        meets_threshold = False

        entries = fhir_bundle.get("entry", [])
        for entry in entries:
            resource = entry.get("resource", {})
            resource_type = resource.get("resourceType")

            if resource_type == "Condition":
                codeable_concept = resource.get("code", {})
                coding = codeable_concept.get("coding", [])
                for code_entry in coding:
                    system = code_entry.get("system", "")
                    if "sid/icd-10" in system or "icd-10" in system:
                        icd_code = code_entry.get("code")
                        if icd_code:
                            icd10_codes.append(icd_code)

            elif resource_type == "Observation":
                # Check Glasgow Coma Scale (GCS) or functional status
                value_quantity = resource.get("valueQuantity", {}).get("value")
                code_text = resource.get("code", {}).get("text", "").lower()
                
                if "glasgow coma scale" in code_text and value_quantity is not None:
                    if value_quantity <= 8:  # GCS <= 8 indicates severe coma
                        severity = IncapacitationSeverity.TOTAL_PERMANENT
                        meets_threshold = True

        return {
            "icd10_codes": list(set(icd10_codes)),
            "incapacitation_severity": severity,
            "meets_legal_threshold": meets_threshold
        }