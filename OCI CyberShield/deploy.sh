#!/bin/bash
echo "Deploying OCI CyberShield Pro..."

# Create Fn App
fn create app cybershield-pro --annotation "oracle.com/oci/subnetIds=['ocid1.subnet.oc1..xxxx']"

# Deploy Function
fn deploy -v --app cybershield-pro

echo "Deployed! Now create Event Rule via OCI Console or Terraform."