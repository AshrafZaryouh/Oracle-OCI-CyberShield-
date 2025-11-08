provider "oci" {
  config_file_profile = "DEFAULT"
}

resource "oci_functions_application" "cybershield" {
  compartment_id = var.compartment_id
  display_name   = "CyberShield-Pro"
  subnet_ids     = [var.subnet_id]
}

resource "oci_functions_function" "shield_fn" {
  application_id = oci_functions_application.cybershield.id
  display_name   = "shield-fn"
  image          = "${var.region}-ocir.io/${var.tenancy}/cybershield-fn:latest"
  memory_in_mbs  = 256
}

resource "oci_events_rule" "log_trigger" {
  actions {
    actions {
      action_type = "FAAS"
      is_enabled  = true
      function_id = oci_functions_function.shield_fn.id
    }
  }
  condition = jsonencode({
    eventType = "com.oraclecloud.logging.log.entry"
    data = {
      compartmentId = var.compartment_id
      logGroupId    = var.log_group_id
    }
  })
  display_name = "CyberShield-Log-Trigger"
  is_enabled   = true
  compartment_id = var.compartment_id
}